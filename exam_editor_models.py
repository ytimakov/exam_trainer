"""
Модели данных для редактора вопросов экзамена 1С:Руководитель проекта
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
import json
import os
from datetime import datetime

@dataclass
class Answer:
    """Вариант ответа на вопрос"""
    id: str
    text: str
    is_correct: bool = False
    is_suggested: bool = False  # Предположительно правильный ответ
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "text": self.text,
            "is_correct": self.is_correct,
            "is_suggested": self.is_suggested
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Answer':
        return cls(
            id=data["id"],
            text=data["text"],
            is_correct=data.get("is_correct", False),
            is_suggested=data.get("is_suggested", False)
        )

@dataclass
class Question:
    """Вопрос экзамена"""
    id: str
    text: str
    type: str = "single"  # "single" или "multiple"
    answers: List[Answer] = field(default_factory=list)
    note: Optional[str] = None  # Заметка к вопросу
    suggested_answer_id: Optional[str] = None  # ID предположительно правильного ответа
    is_verified: bool = False  # Ответ проверен
    question_number: Optional[str] = None  # Номер вопроса вида "1.16"
    section_number: Optional[int] = None  # Номер раздела (1-14)
    question_number_in_section: Optional[int] = None  # Номер вопроса в разделе
    exam_name: Optional[str] = None  # Название экзамена (например, "1С:Руководитель проекта" или "Основы менеджмента")
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "text": self.text,
            "type": self.type,
            "answers": [a.to_dict() for a in self.answers],
            "note": self.note,
            "suggested_answer_id": self.suggested_answer_id,
            "is_verified": self.is_verified,
            "question_number": self.question_number,
            "section_number": self.section_number,
            "question_number_in_section": self.question_number_in_section,
            "exam_name": self.exam_name
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Question':
        answers = [Answer.from_dict(a) for a in data.get("answers", [])]
        return cls(
            id=data["id"],
            text=data["text"],
            type=data.get("type", "single"),
            answers=answers,
            note=data.get("note"),
            suggested_answer_id=data.get("suggested_answer_id"),
            is_verified=data.get("is_verified", False),
            question_number=data.get("question_number"),
            section_number=data.get("section_number"),
            question_number_in_section=data.get("question_number_in_section"),
            exam_name=data.get("exam_name")
        )
    
    def get_status(self) -> str:
        """Возвращает статус вопроса"""
        if self.is_verified:
            return "verified"
        elif self.suggested_answer_id:
            return "suggested"
        else:
            return "pending"
    
    def requires_confirmation(self) -> bool:
        """Требует ли вопрос подтверждения"""
        return self.suggested_answer_id and not self.is_verified
    
    def requires_answer(self) -> bool:
        """Требует ли вопрос ответа"""
        return not self.suggested_answer_id and not self.is_verified


class QuestionBank:
    """Банк вопросов для редактирования"""
    
    # Определяем базовую директорию проекта
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    CONFIG_FILE = os.path.join(BASE_DIR, "sources", "exam_config.json")
    _exam_config = None  # Кэш конфигурации
    
    def __init__(self, exam_name: str = "1С:Руководитель проекта"):
        self.questions: List[Question] = []
        self.exam_name = exam_name
        self.data_file = self._get_exam_file(exam_name)
        self.load_questions()
    
    @classmethod
    def _load_config(cls) -> Dict:
        """Загрузка конфигурации экзаменов из JSON файла"""
        if cls._exam_config is None:
            try:
                with open(cls.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    cls._exam_config = json.load(f)
            except FileNotFoundError:
                print(f"Файл конфигурации {cls.CONFIG_FILE} не найден. Используются значения по умолчанию.")
                # Значения по умолчанию
                cls._exam_config = {
                    "exams": [
                        {
                            "name": "1С:Руководитель проекта",
                            "file": "sources/1c_exam_questions.json",
                            "description": "Экзамен по управлению проектами в 1С"
                        }
                    ]
                }
            except Exception as e:
                print(f"Ошибка при загрузке конфигурации: {e}")
                cls._exam_config = {"exams": []}
        return cls._exam_config
    
    @classmethod
    def _get_exam_file(cls, exam_name: str) -> str:
        """Получение пути к файлу данных для экзамена"""
        config = cls._load_config()
        for exam in config.get("exams", []):
            if exam.get("name") == exam_name:
                file_path = exam.get("file", "")
                # Если путь относительный, делаем его абсолютным
                if not os.path.isabs(file_path):
                    return os.path.join(cls.BASE_DIR, file_path)
                return file_path
        # Если экзамен не найден, возвращаем первый доступный или значение по умолчанию
        exams = config.get("exams", [])
        if exams:
            file_path = exams[0].get("file", "sources/1c_exam_questions.json")
            if not os.path.isabs(file_path):
                return os.path.join(cls.BASE_DIR, file_path)
            return file_path
        default_path = os.path.join(cls.BASE_DIR, "sources", "1c_exam_questions.json")
        return default_path
    
    def load_questions(self):
        """Загрузка вопросов текущего экзамена из файла"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Очищаем список вопросов перед загрузкой нового экзамена
            # Это гарантирует, что вопросы разных экзаменов не смешиваются
            self.questions = []
            
            if isinstance(data, list):
                # Если это список вопросов
                for q_data in data:
                    question = Question.from_dict(q_data)
                    # Устанавливаем exam_name если его нет
                    if not question.exam_name:
                        question.exam_name = self.exam_name
                    # Добавляем только если exam_name совпадает (на случай если в файле смешаны экзамены)
                    if question.exam_name == self.exam_name:
                        self.questions.append(question)
            elif isinstance(data, dict):
                # Если это словарь с курсами (например, из all_courses_data.json)
                # Ищем курс по названию экзамена
                course_key = None
                for key in data.keys():
                    course_data = data[key]
                    if isinstance(course_data, dict):
                        course_name = course_data.get("course_name", key)
                        if course_name == self.exam_name or key == self.exam_name:
                            course_key = key
                            break
                
                if course_key:
                    course_data = data[course_key]
                    for q_data in course_data.get("questions", []):
                        question = Question.from_dict(q_data)
                        if not question.exam_name:
                            question.exam_name = self.exam_name
                        self.questions.append(question)
            
            print(f"Загружено {len(self.questions)} вопросов для экзамена '{self.exam_name}' из файла {self.data_file}")
        except FileNotFoundError:
            print(f"Файл {self.data_file} не найден")
            self.questions = []
        except Exception as e:
            print(f"Ошибка при загрузке вопросов: {e}")
            self.questions = []
    
    def switch_exam(self, exam_name: str):
        """Переключение на другой экзамен"""
        config = self._load_config()
        exam_names = [exam.get("name") for exam in config.get("exams", [])]
        
        if exam_name in exam_names:
            self.exam_name = exam_name
            self.data_file = self._get_exam_file(exam_name)
            self.load_questions()
        else:
            raise ValueError(f"Экзамен '{exam_name}' не найден в конфигурации")
    
    @classmethod
    def get_available_exams(cls) -> List[str]:
        """Получение списка доступных экзаменов"""
        config = cls._load_config()
        return [exam.get("name") for exam in config.get("exams", [])]
    
    @classmethod
    def get_exam_info(cls, exam_name: str) -> Optional[Dict]:
        """Получение информации об экзамене"""
        config = cls._load_config()
        for exam in config.get("exams", []):
            if exam.get("name") == exam_name:
                return exam
        return None
    
    @classmethod
    def get_all_exams_info(cls) -> List[Dict]:
        """Получение информации обо всех экзаменах"""
        config = cls._load_config()
        return config.get("exams", [])
    
    def save_questions(self):
        """Сохранение вопросов текущего экзамена в файл"""
        try:
            # Фильтруем вопросы только текущего экзамена
            exam_questions = [q for q in self.questions if q.exam_name == self.exam_name]
            
            # Создаем резервную копию перед сохранением
            backup_file = self.data_file + ".backup"
            if os.path.exists(self.data_file):
                import shutil
                shutil.copy2(self.data_file, backup_file)
            
            # Сохраняем только вопросы текущего экзамена
            data = [q.to_dict() for q in exam_questions]
            
            # Сохраняем во временный файл сначала
            temp_file = self.data_file + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # Если сохранение успешно, заменяем оригинальный файл
            import shutil
            shutil.move(temp_file, self.data_file)
            
            print(f"Сохранено {len(exam_questions)} вопросов для экзамена '{self.exam_name}' в файл {self.data_file}")
        except Exception as e:
            print(f"Ошибка при сохранении вопросов: {e}")
            # Восстанавливаем из резервной копии при ошибке
            if os.path.exists(backup_file):
                import shutil
                shutil.copy2(backup_file, self.data_file)
            raise
    
    def get_question_by_id(self, question_id: str) -> Optional[Question]:
        """Получение вопроса по ID"""
        for q in self.questions:
            if q.id == question_id:
                return q
        return None
    
    def search_questions(self, query: str) -> List[Question]:
        """Поиск вопросов по тексту"""
        query_lower = query.lower()
        results = []
        
        for q in self.questions:
            # Поиск в тексте вопроса
            if query_lower in q.text.lower():
                results.append(q)
                continue
            
            # Поиск в вариантах ответов
            for a in q.answers:
                if query_lower in a.text.lower():
                    results.append(q)
                    break
            
            # Поиск в заметках
            if q.note and query_lower in q.note.lower():
                results.append(q)
        
        return results
    
    def filter_by_status(self, status: str) -> List[Question]:
        """Фильтрация вопросов по статусу"""
        if status == "pending":
            return [q for q in self.questions if q.requires_answer()]
        elif status == "suggested":
            return [q for q in self.questions if q.requires_confirmation()]
        elif status == "verified":
            return [q for q in self.questions if q.is_verified]
        else:
            return self.questions
    
    def filter_by_section(self, section_number: Optional[int]) -> List[Question]:
        """Фильтрация вопросов по номеру раздела"""
        if section_number is None:
            return self.questions
        return [q for q in self.questions if q.section_number == section_number]
    
    def get_sections(self) -> List[Dict]:
        """Получение списка разделов с количеством вопросов"""
        sections = {}
        for q in self.questions:
            if q.section_number:
                if q.section_number not in sections:
                    sections[q.section_number] = {
                        "number": q.section_number,
                        "name": self.get_section_name(q.section_number, self.exam_name),
                        "count": 0
                    }
                sections[q.section_number]["count"] += 1
        
        return sorted(sections.values(), key=lambda x: x["number"])
    
    def get_section_name(self, section_number: int, exam_name: Optional[str] = None) -> str:
        """Получение названия раздела по номеру для конкретного экзамена"""
        if exam_name is None:
            exam_name = self.exam_name
        
        # Темы для экзамена "1С:Руководитель проекта"
        rp_section_names = {
            1: "Определения, деятельность, цели, ценности",
            2: "Организационная структура",
            3: "Жизненный цикл проекта, процессы проекта",
            4: "Принципы управления проектом",
            5: "Домен «Заинтересованные стороны»",
            6: "Домен «Команда»",
            7: "Домен «Подход к разработке и жизненный цикл»",
            8: "Домен «Планирование»",
            9: "Домен «Работа проекта»",
            10: "Домен «Поставка»",
            11: "Домен «Измерение»",
            12: "Домен «Неопределенность»",
            13: "Адаптация",
            14: "Модели, методы, артефакты"
        }
        
        # Темы для экзамена "Основы менеджмента"
        # TODO: Заменить на правильные темы из osnovy_new.xlsx
        osnovy_section_names = {
            1: "Управление и менеджмент",
            2: "Организационная структура",
            3: "Функции управления",
            4: "Стили управления",
            5: "Мотивация",
            6: "Коммуникации в организации",
            7: "Конфликты в организации",
            8: "Управление изменениями",
            9: "Лидерство",
            10: "Принятие решений",
            11: "Контроль и оценка",
            12: "Управление качеством",
            13: "Стратегическое управление"
        }
        
        # Выбираем словарь тем в зависимости от экзамена
        if exam_name == "Основы менеджмента":
            section_names = osnovy_section_names
        else:
            # По умолчанию используем темы для "1С:Руководитель проекта"
            section_names = rp_section_names
        
        return section_names.get(section_number, f"Раздел {section_number}")
    
    def get_statistics(self) -> Dict:
        """Получение статистики"""
        total = len(self.questions)
        pending = len(self.filter_by_status("pending"))
        suggested = len(self.filter_by_status("suggested"))
        verified = len(self.filter_by_status("verified"))
        
        return {
            "total": total,
            "pending": pending,
            "suggested": suggested,
            "verified": verified
        }

