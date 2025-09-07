# complete_fix.py - ПОЛНОЕ ИСПРАВЛЕНИЕ ВСЕХ ИМПОРТОВ
"""
Этот скрипт найдет и исправит ВСЕ проблемные импорты в проекте
"""
import os
import re
from pathlib import Path

def fix_all_imports():
    """Исправляет все импорты в проекте"""
    
    # Поиск всех .py файлов
    project_root = Path(".")
    python_files = []
    
    # Поиск в app/ и scripts/
    for pattern in ["app/**/*.py", "scripts/**/*.py", "*.py"]:
        python_files.extend(project_root.glob(pattern))
    
    # Паттерны для исправления (порядок важен!)
    patterns_to_fix = [
        # Основные модули без app.
        (r"^from database import", "from app.database import"),
        (r"^from config import", "from app.config import"),
        (r"^from models import", "r!from app.models import"),
        (r"^from dependencies import", "from app.dependencies import"),
        (r"^from startup import", "from app.startup import"),
        
        # Сервисы без app.
        (r"^from services\.(\w+) import", r"from app.services.\1 import"),
        (r"^from user_service import", "from app.services.user_service import"),
        (r"^from chat_service import", "from app.services.chat_service import"),
        (r"^from file_service import", "from app.services.file_service import"),
        (r"^from ai_service import", "from app.services.ai_service import"),
        
        # Репозитории без app.
        (r"^from repositories\.(\w+) import", r"from app.repositories.\1 import"),
        (r"^from user_repository import", "from app.repositories.user_repository import"),
        (r"^from chat_repository import", "from app.repositories.chat_repository import"),
        (r"^from message_repository import", "from app.repositories.message_repository import"),
        (r"^from attachment_repository import", "from app.repositories.attachment_repository import"),
        (r"^from base_repository import", "from app.repositories.base_repository import"),
        
        # Относительные импорты с точкой
        (r"^from \.database import", "from app.database import"),
        (r"^from \.config import", "from app.config import"),
        (r"^from \.models import", "from app.models import"),
        (r"^from \.services\.(\w+) import", r"from app.services.\1 import"),
        (r"^from \.repositories\.(\w+) import", r"from app.repositories.\1 import"),
    ]
    
    fixed_files = []
    
    for file_path in python_files:
        if not file_path.exists():
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            original_lines = lines.copy()
            
            # Применяем паттерны построчно
            for i, line in enumerate(lines):
                for pattern, replacement in patterns_to_fix:
                    lines[i] = re.sub(pattern, replacement, line)
            
            # Сохраняем только если были изменения
            if lines != original_lines:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                fixed_files.append(str(file_path))
                print(f"✅ Исправлен: {file_path}")
        
        except Exception as e:
            print(f"❌ Ошибка в файле {file_path}: {e}")
    
    return fixed_files

def create_missing_files():
    """Создает недостающие файлы"""
    
    # __init__.py файлы
    init_files = [
        "app/__init__.py",
        "app/services/__init__.py", 
        "app/repositories/__init__.py"
    ]
    
    for init_file in init_files:
        path = Path(init_file)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
            print(f"✅ Создан: {init_file}")
        else:
            print(f"✨ Уже существует: {init_file}")

def check_structure():
    """Проверяет структуру проекта"""
    print("\n🔍 Проверка структуры проекта:")
    
    required_files = [
        "app/__init__.py",
        "app/config.py",
        "app/database.py", 
        "app/models.py",
        "app/main.py",
        "app/dependencies.py",
        "app/services/__init__.py",
        "app/repositories/__init__.py"
    ]
    
    missing_files = []
    
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - ОТСУТСТВУЕТ!")
            missing_files.append(file_path)
    
    return missing_files

def main():
    """Основная функция"""
    print("🔧 ПОЛНОЕ ИСПРАВЛЕНИЕ ПРОЕКТА ТОВАРИЩБОТ")
    print("=" * 60)
    
    # 1. Создаем недостающие файлы
    print("\n1. Создание __init__.py файлов:")
    create_missing_files()
    
    # 2. Проверяем структуру
    print("\n2. Проверка структуры:")
    missing = check_structure()
    
    if missing:
        print(f"\n⚠️  Отсутствуют файлы: {len(missing)}")
        for file in missing:
            print(f"   - {file}")
        print("\nСоздайте эти файлы или запустите: python scripts/quick_fix.py")
    
    # 3. Исправляем импорты
    print("\n3. Исправление импортов:")
    fixed_files = fix_all_imports()
    
    if fixed_files:
        print(f"\n🎉 Исправлено файлов: {len(fixed_files)}")
    else:
        print("\n✨ Все импорты уже корректны")
    
    print("\n" + "=" * 60)
    print("🚀 Попробуйте запустить:")
    print("   python run.py")
    print("\n💡 Если ошибки продолжаются, проверьте:")
    print("   1. Все ли файлы созданы")
    print("   2. Правильность путей в импортах")
    print("   3. Синтаксические ошибки в Python коде")

if __name__ == "__main__":
    main()

# =====================================================
# РУЧНОЕ ИСПРАВЛЕНИЕ (если автоматическое не сработало)
# =====================================================

"""
НАЙДИТЕ И ЗАМЕНИТЕ В ФАЙЛАХ:

1. В ЛЮБЫХ .py файлах замените:
   from database import     → from app.database import
   from config import       → from app.config import
   from models import       → from app.models import
   from dependencies import → from app.dependencies import

2. В файлах сервисов:
   from user_service import     → from app.services.user_service import
   from chat_service import     → from app.services.chat_service import
   from file_service import     → from app.services.file_service import
   from ai_service import       → from app.services.ai_service import

3. В файлах репозиториев:
   from user_repository import     → from app.repositories.user_repository import
   from chat_repository import     → from app.repositories.chat_repository import
   from base_repository import     → from app.repositories.base_repository import

4. Относительные импорты:
   from .database import    → from app.database import
   from .config import      → from app.config import
   from .models import      → from app.models import

САМЫЕ ВЕРОЯТНЫЕ ФАЙЛЫ С ОШИБКАМИ:
- app/main.py
- app/dependencies.py  
- app/services/user_service.py
- app/services/chat_service.py
- app/repositories/user_repository.py
- scripts/migrate_to_sqlite.py
"""