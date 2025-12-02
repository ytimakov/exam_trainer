"""
Скрипт для генерации Secret строк для авторизации пользователей
"""
import secrets
import string
import os
import json

def generate_secret(length=32):
    """Генерация случайной Secret строки"""
    alphabet = string.ascii_letters + string.digits
    secret = ''.join(secrets.choice(alphabet) for _ in range(length))
    return secret

def create_secret_folder(secret):
    """Создание папки для Secret и инициализация файла прогресса"""
    secret_dir = f"secrets/{secret}"
    os.makedirs(secret_dir, exist_ok=True)
    
    # Создаём пустой файл прогресса
    progress_file = os.path.join(secret_dir, "trainer_progress.json")
    if not os.path.exists(progress_file):
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        print(f"Создан файл прогресса: {progress_file}")
    
    return secret_dir

def register_secret(secret):
    """Регистрация Secret в конфигурационном файле"""
    config_file = "secrets_config.json"
    
    # Загружаем существующие секреты
    secrets_list = []
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                secrets_list = data.get("secrets", [])
        except Exception as e:
            print(f"Ошибка чтения конфигурации: {e}")
            secrets_list = []
    
    # Проверяем, не существует ли уже такой Secret
    if secret in secrets_list:
        print(f"Предупреждение: Secret '{secret}' уже существует")
        return
    
    # Добавляем новый Secret
    secrets_list.append(secret)
    
    # Сохраняем обновлённую конфигурацию
    config_data = {
        "secrets": secrets_list
    }
    
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        print(f"Secret зарегистрирован в {config_file}")
    except Exception as e:
        print(f"Ошибка сохранения конфигурации: {e}")

if __name__ == "__main__":
    # Генерируем новый Secret
    secret = generate_secret()
    
    print("=" * 60)
    print("НОВЫЙ SECRET СГЕНЕРИРОВАН")
    print("=" * 60)
    print(f"\nSecret: {secret}\n")
    print("=" * 60)
    print("\nВАЖНО: Сохраните этот Secret в безопасном месте!")
    print("Этот Secret будет использоваться для авторизации в приложении.\n")
    
    # Создаём папку для Secret
    secret_dir = create_secret_folder(secret)
    print(f"Создана папка: {secret_dir}")
    
    # Регистрируем Secret
    register_secret(secret)
    
    print("\n" + "=" * 60)
    print("Используйте этот Secret для входа в приложение.")
    print("=" * 60)

