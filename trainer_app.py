"""
Веб-приложение тренажёр для подготовки к экзаменам
"""
from flask import Flask, render_template, jsonify, request, session
from flask_cors import CORS
from functools import wraps
from exam_editor_models import QuestionBank, Question
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
# Настройка постоянных сессий (30 дней)
app.permanent_session_lifetime = timedelta(days=30)
CORS(app, supports_credentials=True)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Конфигурация Secret
# Определяем базовую директорию проекта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECRETS_CONFIG_FILE = os.path.join(BASE_DIR, "secrets_config.json")
SECRETS_DIR = os.path.join(BASE_DIR, "secrets")

# Инициализация банка вопросов
current_exam_name = "1С:Руководитель проекта"
question_bank = QuestionBank(current_exam_name)

# Глобальный словарь для хранения экземпляров UserProgress по Secret
user_progress_cache: Dict[str, 'UserProgress'] = {}


def load_secrets():
    """Загрузка списка зарегистрированных Secret"""
    if not os.path.exists(SECRETS_CONFIG_FILE):
        return []
    
    try:
        with open(SECRETS_CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("secrets", [])
    except Exception as e:
        logging.error(f"Ошибка загрузки конфигурации Secret: {e}")
        return []


def is_valid_secret(secret: str) -> bool:
    """Проверка валидности Secret"""
    if not secret:
        return False
    
    # Проверяем, существует ли папка для этого Secret
    secret_dir = os.path.join(SECRETS_DIR, secret)
    if not os.path.exists(secret_dir):
        return False
    
    # Проверяем, зарегистрирован ли Secret
    registered_secrets = load_secrets()
    return secret in registered_secrets


def get_user_progress(secret: str) -> 'UserProgress':
    """Получение или создание экземпляра UserProgress для Secret"""
    if secret not in user_progress_cache:
        progress_file = os.path.join(SECRETS_DIR, secret, "trainer_progress.json")
        user_progress_cache[secret] = UserProgress(progress_file)
    return user_progress_cache[secret]


def require_auth(f):
    """Декоратор для защиты маршрутов от неавторизованного доступа"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Убеждаемся, что сессия постоянная
        session.permanent = True
        secret = session.get('secret')
        if not secret or not is_valid_secret(secret):
            return jsonify({"error": "Требуется авторизация", "authenticated": False}), 401
        return f(*args, **kwargs)
    return decorated_function


class UserProgress:
    """Класс для управления прогрессом пользователя"""
    
    def __init__(self, progress_file: str):
        self.progress_file = progress_file
        self.data: Dict[str, Dict] = {}  # exam_name -> {question_id -> progress}
        # Создаём директорию, если её нет
        progress_dir = os.path.dirname(progress_file)
        if progress_dir:
            os.makedirs(progress_dir, exist_ok=True)
        self.load()
    
    def load(self):
        """Загрузка прогресса из файла"""
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            else:
                self.data = {}
        except Exception as e:
            logging.error(f"Ошибка загрузки прогресса: {e}")
            self.data = {}
    
    def save(self):
        """Сохранение прогресса в файл"""
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Ошибка сохранения прогресса: {e}")
    
    def get_question_progress(self, exam_name: str, question_id: str) -> Dict:
        """Получение прогресса по вопросу"""
        exam_progress = self.data.get(exam_name, {})
        return exam_progress.get(question_id, {
            "attempts": 0,
            "correct_streak": 0,
            "total_correct": 0,
            "mastered": False,
            "last_attempt": None
        })
    
    def update_question_progress(self, exam_name: str, question_id: str, is_correct: bool, dont_know: bool = False):
        """Обновление прогресса по вопросу"""
        if exam_name not in self.data:
            self.data[exam_name] = {}
        
        if question_id not in self.data[exam_name]:
            self.data[exam_name][question_id] = {
                "attempts": 0,
                "correct_streak": 0,
                "total_correct": 0,
                "mastered": False,
                "last_attempt": None
            }
        
        progress = self.data[exam_name][question_id]
        progress["attempts"] += 1
        progress["last_attempt"] = datetime.now().isoformat()
        
        if dont_know:
            # Не знаю ответ - сбрасываем серию правильных ответов
            progress["correct_streak"] = 0
        elif is_correct:
            progress["correct_streak"] += 1
            progress["total_correct"] += 1
            # Если 3 правильных подряд - усвоено
            if progress["correct_streak"] >= 3:
                progress["mastered"] = True
        else:
            progress["correct_streak"] = 0
        
        self.save()
        return progress
    
    def set_mastered(self, exam_name: str, question_id: str, mastered: bool):
        """Установка/снятие отметки "Усвоен" """
        if exam_name not in self.data:
            self.data[exam_name] = {}
        
        if question_id not in self.data[exam_name]:
            self.data[exam_name][question_id] = {
                "attempts": 0,
                "correct_streak": 0,
                "total_correct": 0,
                "mastered": mastered,
                "last_attempt": None
            }
        else:
            self.data[exam_name][question_id]["mastered"] = mastered
            if not mastered:
                # При снятии отметки сбрасываем серию
                self.data[exam_name][question_id]["correct_streak"] = 0
        
        self.save()
        return self.data[exam_name][question_id]
    
    def get_exam_statistics(self, exam_name: str, verified_question_ids: List[str]) -> Dict:
        """Получение статистики по экзамену"""
        exam_progress = self.data.get(exam_name, {})
        
        total_verified = len(verified_question_ids)
        mastered = 0
        attempted = 0
        total_attempts = 0
        total_correct = 0
        
        for q_id in verified_question_ids:
            progress = exam_progress.get(q_id, {})
            if progress.get("mastered", False):
                mastered += 1
            if progress.get("attempts", 0) > 0:
                attempted += 1
                total_attempts += progress.get("attempts", 0)
                total_correct += progress.get("total_correct", 0)
        
        return {
            "total_verified": total_verified,
            "mastered": mastered,
            "attempted": attempted,
            "not_attempted": total_verified - attempted,
            "total_attempts": total_attempts,
            "total_correct": total_correct,
            "mastered_percent": round(mastered / total_verified * 100, 1) if total_verified > 0 else 0,
            "attempted_percent": round(attempted / total_verified * 100, 1) if total_verified > 0 else 0,
            "accuracy": round(total_correct / total_attempts * 100, 1) if total_attempts > 0 else 0
        }
    
    def get_section_statistics(self, exam_name: str, questions: List[Question]) -> List[Dict]:
        """Получение статистики по разделам"""
        exam_progress = self.data.get(exam_name, {})
        
        sections: Dict[int, Dict] = {}
        
        for q in questions:
            if not q.is_verified:
                continue
            
            section_num = q.section_number or 0
            if section_num not in sections:
                sections[section_num] = {
                    "section_number": section_num,
                    "total": 0,
                    "mastered": 0,
                    "attempted": 0,
                    "total_correct": 0,
                    "total_attempts": 0
                }
            
            sections[section_num]["total"] += 1
            
            progress = exam_progress.get(q.id, {})
            if progress.get("mastered", False):
                sections[section_num]["mastered"] += 1
            if progress.get("attempts", 0) > 0:
                sections[section_num]["attempted"] += 1
                sections[section_num]["total_attempts"] += progress.get("attempts", 0)
                sections[section_num]["total_correct"] += progress.get("total_correct", 0)
        
        # Добавляем проценты
        result = []
        for section_num in sorted(sections.keys()):
            section = sections[section_num]
            section["mastered_percent"] = round(section["mastered"] / section["total"] * 100, 1) if section["total"] > 0 else 0
            section["attempted_percent"] = round(section["attempted"] / section["total"] * 100, 1) if section["total"] > 0 else 0
            section["accuracy"] = round(section["total_correct"] / section["total_attempts"] * 100, 1) if section["total_attempts"] > 0 else 0
            result.append(section)
        
        return result


# Функция для получения текущего user_progress из сессии
def get_current_user_progress() -> UserProgress:
    """Получение UserProgress для текущего авторизованного пользователя"""
    secret = session.get('secret')
    if not secret:
        raise ValueError("Пользователь не авторизован")
    return get_user_progress(secret)


@app.route('/')
def index():
    """Главная страница тренажёра"""
    return render_template('trainer.html')


@app.route('/telegram')
def telegram_app():
    """Telegram Mini App"""
    return render_template('telegram_trainer.html')


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Авторизация по Secret"""
    data = request.get_json()
    secret = data.get('secret', '').strip()
    
    if not secret:
        return jsonify({"error": "Secret не указан", "authenticated": False}), 400
    
    if not is_valid_secret(secret):
        return jsonify({"error": "Неверный Secret", "authenticated": False}), 401
    
    # Сохраняем Secret в сессии и делаем сессию постоянной
    session['secret'] = secret
    session.permanent = True
    
    return jsonify({
        "success": True,
        "authenticated": True,
        "message": "Авторизация успешна"
    })


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Выход из системы"""
    session.pop('secret', None)
    return jsonify({
        "success": True,
        "authenticated": False,
        "message": "Выход выполнен"
    })


@app.route('/api/auth/status')
def auth_status():
    """Проверка статуса авторизации"""
    # Убеждаемся, что сессия постоянная
    session.permanent = True
    secret = session.get('secret')
    authenticated = secret and is_valid_secret(secret)
    
    return jsonify({
        "authenticated": authenticated,
        "has_secret": bool(secret)
    })


@app.route('/api/exams')
@require_auth
def get_exams():
    """Получение списка доступных экзаменов"""
    exams_info = QuestionBank.get_all_exams_info()
    exams = QuestionBank.get_available_exams()
    return jsonify({
        "exams": exams,
        "exams_info": exams_info,
        "current_exam": current_exam_name
    })


@app.route('/api/exam/switch', methods=['POST'])
@require_auth
def switch_exam():
    """Переключение на другой экзамен"""
    global question_bank, current_exam_name
    
    data = request.get_json()
    exam_name = data.get("exam_name")
    
    if not exam_name:
        return jsonify({"error": "Не указано название экзамена"}), 400
    
    if exam_name not in QuestionBank.get_available_exams():
        return jsonify({"error": f"Экзамен '{exam_name}' не найден"}), 404
    
    try:
        question_bank.switch_exam(exam_name)
        current_exam_name = exam_name
        
        return jsonify({
            "success": True,
            "exam_name": exam_name,
            "questions_count": len([q for q in question_bank.questions if q.is_verified])
        })
    except Exception as e:
        logging.error(f"Ошибка переключения экзамена: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/questions')
@require_auth
def get_questions():
    """Получение списка вопросов с подтверждёнными ответами"""
    user_progress = get_current_user_progress()
    
    hide_mastered = request.args.get('hide_mastered', 'true').lower() == 'true'
    section_filter = request.args.get('section', '').strip()
    status_filter = request.args.get('status', '').strip()
    search_query = request.args.get('search', '').strip()
    
    # Фильтруем только вопросы с подтверждёнными ответами
    questions = [q for q in question_bank.questions 
                 if q.exam_name == current_exam_name and q.is_verified]
    
    # Фильтр по разделу
    if section_filter:
        try:
            section_num = int(section_filter)
            questions = [q for q in questions if q.section_number == section_num]
        except ValueError:
            pass
    
    # Поиск
    if search_query:
        query_lower = search_query.lower()
        questions = [q for q in questions 
                    if query_lower in q.text.lower() or 
                    any(query_lower in a.text.lower() for a in q.answers)]
    
    # Добавляем прогресс к каждому вопросу и применяем фильтры
    result = []
    for q in questions:
        progress = user_progress.get_question_progress(current_exam_name, q.id)
        
        # Фильтр по статусу
        if status_filter:
            if status_filter == 'not_attempted':
                # Непройденные - нет попыток
                if progress.get("attempts", 0) > 0:
                    continue
            elif status_filter == 'with_errors':
                # С ошибками - есть попытки, но есть неправильные ответы
                attempts = progress.get("attempts", 0)
                correct = progress.get("total_correct", 0)
                if attempts == 0 or attempts == correct:
                    continue
            elif status_filter == 'mastered':
                # Только усвоенные
                if not progress.get("mastered", False):
                    continue
        
        # Скрываем усвоенные если нужно (применяется после фильтра по статусу)
        if hide_mastered and progress.get("mastered", False) and status_filter != 'mastered':
            continue
        
        q_dict = q.to_dict()
        q_dict["progress"] = progress
        result.append(q_dict)
    
    return jsonify({
        "questions": result,
        "total": len(result)
    })


@app.route('/api/sections')
@require_auth
def get_sections():
    """Получение списка разделов"""
    # Только вопросы с подтверждёнными ответами
    verified_questions = [q for q in question_bank.questions 
                         if q.exam_name == current_exam_name and q.is_verified]
    
    sections = {}
    for q in verified_questions:
        if q.section_number:
            if q.section_number not in sections:
                sections[q.section_number] = {
                    "number": q.section_number,
                    "name": question_bank.get_section_name(q.section_number, current_exam_name),
                    "count": 0
                }
            sections[q.section_number]["count"] += 1
    
    sections_list = sorted(sections.values(), key=lambda x: x["number"])
    return jsonify({"sections": sections_list})


@app.route('/api/question/<question_id>')
@require_auth
def get_question(question_id):
    """Получение конкретного вопроса"""
    user_progress = get_current_user_progress()
    
    question = question_bank.get_question_by_id(question_id)
    
    if not question:
        return jsonify({"error": "Вопрос не найден"}), 404
    
    if not question.is_verified:
        return jsonify({"error": "Вопрос не имеет подтверждённого ответа"}), 400
    
    # Параметр show_answers позволяет показать правильные ответы (после проверки)
    show_answers = request.args.get('show_answers', 'false').lower() == 'true'
    
    q_dict = question.to_dict()
    q_dict["progress"] = user_progress.get_question_progress(current_exam_name, question_id)
    
    # Если не нужно показывать ответы, скрываем is_correct флаги
    if not show_answers:
        for answer in q_dict["answers"]:
            answer["is_correct"] = False
            answer["is_suggested"] = False
    
    return jsonify({"question": q_dict})


@app.route('/api/question/<question_id>/check', methods=['POST'])
@require_auth
def check_answer(question_id):
    """Проверка ответа пользователя"""
    user_progress = get_current_user_progress()
    
    question = question_bank.get_question_by_id(question_id)
    
    if not question:
        return jsonify({"error": "Вопрос не найден"}), 404
    
    data = request.get_json()
    selected_answer_ids = data.get("selected_answers", [])
    dont_know = data.get("dont_know", False)
    
    # Находим правильные ответы
    correct_answer_ids = [a.id for a in question.answers if a.is_correct]
    
    if dont_know:
        # Пользователь не знает ответ
        is_correct = False
        progress = user_progress.update_question_progress(
            current_exam_name, question_id, is_correct=False, dont_know=True
        )
    else:
        # Проверяем ответ
        is_correct = set(selected_answer_ids) == set(correct_answer_ids)
        progress = user_progress.update_question_progress(
            current_exam_name, question_id, is_correct=is_correct, dont_know=False
        )
    
    return jsonify({
        "is_correct": is_correct,
        "correct_answers": correct_answer_ids,
        "progress": progress,
        "mastered": progress.get("mastered", False)
    })


@app.route('/api/question/<question_id>/mastered', methods=['POST'])
@require_auth
def set_question_mastered(question_id):
    """Установка/снятие отметки 'Усвоен'"""
    user_progress = get_current_user_progress()
    
    question = question_bank.get_question_by_id(question_id)
    
    if not question:
        return jsonify({"error": "Вопрос не найден"}), 404
    
    data = request.get_json()
    mastered = data.get("mastered", False)
    
    progress = user_progress.set_mastered(current_exam_name, question_id, mastered)
    
    return jsonify({
        "success": True,
        "progress": progress
    })


@app.route('/api/statistics')
@require_auth
def get_statistics():
    """Получение статистики по экзамену"""
    user_progress = get_current_user_progress()
    
    verified_questions = [q for q in question_bank.questions 
                         if q.exam_name == current_exam_name and q.is_verified]
    
    verified_ids = [q.id for q in verified_questions]
    
    stats = user_progress.get_exam_statistics(current_exam_name, verified_ids)
    section_stats = user_progress.get_section_statistics(current_exam_name, verified_questions)
    
    # Добавляем названия разделов
    for section in section_stats:
        section["name"] = question_bank.get_section_name(section["section_number"], current_exam_name)
    
    return jsonify({
        "overall": stats,
        "sections": section_stats
    })


@app.route('/api/session/start', methods=['POST'])
@require_auth
def start_session():
    """Начало сессии тестирования"""
    user_progress = get_current_user_progress()
    
    data = request.get_json()
    question_ids = data.get("question_ids", [])
    
    if not question_ids:
        return jsonify({"error": "Не выбраны вопросы"}), 400
    
    # Проверяем, что все вопросы существуют и имеют подтверждённые ответы
    session_questions = []
    for q_id in question_ids:
        q = question_bank.get_question_by_id(q_id)
        if q and q.is_verified:
            q_dict = q.to_dict()
            q_dict["progress"] = user_progress.get_question_progress(current_exam_name, q_id)
            # Скрываем правильные ответы для режима тестирования
            for answer in q_dict["answers"]:
                answer["is_correct"] = False
                answer["is_suggested"] = False
            session_questions.append(q_dict)
    
    return jsonify({
        "success": True,
        "questions": session_questions,
        "total": len(session_questions)
    })


@app.route('/api/session/results', methods=['POST'])
@require_auth
def get_session_results():
    """Получение результатов сессии тестирования"""
    user_progress = get_current_user_progress()
    
    data = request.get_json()
    answers = data.get("answers", {})  # {question_id: {selected: [], dont_know: bool}}
    
    results = []
    total_correct = 0
    total_answered = 0
    total_dont_know = 0
    
    for q_id, answer_data in answers.items():
        question = question_bank.get_question_by_id(q_id)
        if not question:
            continue
        
        selected = answer_data.get("selected", [])
        dont_know = answer_data.get("dont_know", False)
        
        correct_answer_ids = [a.id for a in question.answers if a.is_correct]
        
        if dont_know:
            is_correct = False
            total_dont_know += 1
            # Обновляем прогресс
            progress = user_progress.update_question_progress(
                current_exam_name, q_id, is_correct=False, dont_know=True
            )
        else:
            is_correct = set(selected) == set(correct_answer_ids)
            total_answered += 1
            if is_correct:
                total_correct += 1
            # Обновляем прогресс
            progress = user_progress.update_question_progress(
                current_exam_name, q_id, is_correct=is_correct, dont_know=False
            )
        
        # Формируем результат
        q_dict = question.to_dict()
        q_dict["progress"] = progress
        
        results.append({
            "question": q_dict,
            "selected_answers": selected,
            "correct_answers": correct_answer_ids,
            "is_correct": is_correct,
            "dont_know": dont_know,
            "progress": progress
        })
    
    return jsonify({
        "results": results,
        "summary": {
            "total_answered": total_answered,
            "total_correct": total_correct,
            "total_dont_know": total_dont_know,
            "accuracy": round(total_correct / total_answered * 100, 1) if total_answered > 0 else 0
        }
    })


if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs(SECRETS_DIR, exist_ok=True)
    
    # Запуск на всех интерфейсах (0.0.0.0) для доступа с мобильного устройства в локальной сети
    # Для безопасности можно использовать host='127.0.0.1' если нужен только локальный доступ
    app.run(debug=True, host='0.0.0.0', port=5002)

