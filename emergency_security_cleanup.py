#!/usr/bin/env python3
"""
ЭКСТРЕННАЯ ОЧИСТКА БЕЗОПАСНОСТИ
Немедленное исправление критических уязвимостей безопасности
"""
import os
import re
import shutil
from pathlib import Path
from typing import List, Dict, Set
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EmergencySecurityCleanup:
    """Экстренная очистка критических проблем безопасности"""
    
    def __init__(self):
        self.project_root = Path(".")
        self.compromised_key = os.getenv("AGENT_API_KEY", "")
        self.files_with_keys: List[Path] = []
        
    def scan_for_hardcoded_secrets(self) -> Dict[str, List[str]]:
        """Сканирует все файлы на наличие hardcoded секретов"""
        logger.info("🔍 Сканирование hardcoded секретов...")
        
        patterns = {
            'api_keys': [
                r'sk-[a-zA-Z0-9]{48}',  # OpenAI keys
                r'["\'][a-zA-Z0-9]{32,}["\']',  # Generic long keys
                r'api_key.*=.*["\'][a-zA-Z0-9_-]{20,}["\']',  # API key assignments
            ],
            'passwords': [
                r'password.*=.*["\'][^"\']{8,}["\']',
                r'passwd.*=.*["\'][^"\']{8,}["\']',
            ],
            'tokens': [
                r'token.*=.*["\'][a-zA-Z0-9_-]{20,}["\']',
                r'access_token.*=.*["\'][a-zA-Z0-9_-]{20,}["\']',
            ]
        }
        
        found_secrets = {}
        
        for py_file in self.project_root.rglob("*.py"):
            if py_file.name.startswith('.'):
                continue
                
            try:
                content = py_file.read_text(encoding='utf-8')
                
                for category, pattern_list in patterns.items():
                    for pattern in pattern_list:
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        if matches:
                            if category not in found_secrets:
                                found_secrets[category] = []
                            found_secrets[category].extend([
                                f"{py_file}:{match}" for match in matches
                            ])
                            
                # Проверка на конкретный скомпрометированный ключ
                if self.compromised_key in content:
                    self.files_with_keys.append(py_file)
                    
            except Exception as e:
                logger.warning(f"Не удалось прочитать {py_file}: {e}")
                
        return found_secrets
    
    def remove_hardcoded_secrets(self) -> None:
        """Удаляет hardcoded секреты из файлов"""
        logger.info("🧹 Удаление hardcoded секретов...")
        
        for file_path in self.files_with_keys:
            logger.info(f"Очистка {file_path}")
            
            try:
                content = file_path.read_text(encoding='utf-8')
                
                # Заменяем скомпрометированный ключ на переменную окружения
                old_pattern = f'"{self.compromised_key}"'
                new_pattern = 'os.getenv("AGENT_API_KEY", "")'
                
                content = content.replace(old_pattern, new_pattern)
                content = content.replace(f"'{self.compromised_key}'", new_pattern)
                
                # Добавляем импорт os если его нет
                if 'import os' not in content and 'from os import' not in content:
                    content = 'import os\n' + content
                
                file_path.write_text(content, encoding='utf-8')
                logger.info(f"✅ Очищен {file_path}")
                
            except Exception as e:
                logger.error(f"❌ Ошибка при очистке {file_path}: {e}")
    
    def create_env_template(self) -> None:
        """Создает шаблон .env файла"""
        logger.info("📝 Создание .env.template...")
        
        env_template = """# Конфигурация безопасности
# ВАЖНО: Никогда не коммитьте этот файл с реальными значениями!

# API ключ для агентов (получите новый на https://platform.openai.com)
AGENT_API_KEY=your_new_api_key_here

# Секретный ключ для JWT токенов
JWT_SECRET_KEY=your_jwt_secret_here

# Пароль базы данных
DB_PASSWORD=your_db_password_here

# Другие секреты
ENCRYPTION_KEY=your_encryption_key_here
"""
        
        Path(".env.template").write_text(env_template, encoding='utf-8')
        logger.info("✅ Создан .env.template")
    
    def update_gitignore(self) -> None:
        """Обновляет .gitignore для защиты секретов"""
        logger.info("🔒 Обновление .gitignore...")
        
        gitignore_additions = """
# Файлы с секретами
.env
.env.local
.env.production
*.key
*.pem
secrets.json
config/secrets.yaml

# Логи с потенциальными секретами
*.log
logs/
audit_logs/

# Временные файлы безопасности
security_*.json
auth_*.txt
"""
        
        gitignore_path = Path(".gitignore")
        
        if gitignore_path.exists():
            current_content = gitignore_path.read_text(encoding='utf-8')
            if "# Файлы с секретами" not in current_content:
                gitignore_path.write_text(current_content + gitignore_additions, encoding='utf-8')
                logger.info("✅ Обновлен .gitignore")
            else:
                logger.info("ℹ️ .gitignore уже содержит правила безопасности")
        else:
            gitignore_path.write_text(gitignore_additions, encoding='utf-8')
            logger.info("✅ Создан .gitignore")
    
    def remove_duplicate_classes(self) -> None:
        """Удаляет дублированные классы из code_quality_improvement_system.py"""
        logger.info("🔄 Удаление дублированных классов...")
        
        file_path = Path("code_quality_improvement_system.py")
        if not file_path.exists():
            logger.warning("Файл code_quality_improvement_system.py не найден")
            return
            
        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            # Находим и удаляем дублированные определения классов
            cleaned_lines = []
            skip_until_next_class = False
            seen_classes = set()
            
            for line in lines:
                if line.strip().startswith('class '):
                    class_name = line.strip().split()[1].split('(')[0].rstrip(':')
                    
                    if class_name in seen_classes:
                        skip_until_next_class = True
                        logger.info(f"Удаляю дублированный класс: {class_name}")
                        continue
                    else:
                        seen_classes.add(class_name)
                        skip_until_next_class = False
                
                elif line.strip().startswith('class ') or (line and not line[0].isspace() and not skip_until_next_class):
                    skip_until_next_class = False
                
                if not skip_until_next_class:
                    cleaned_lines.append(line)
            
            file_path.write_text('\n'.join(cleaned_lines), encoding='utf-8')
            logger.info("✅ Удалены дублированные классы")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при удалении дублей: {e}")
    
    def run_emergency_cleanup(self) -> None:
        """Запускает экстренную очистку"""
        logger.info("🚨 НАЧАЛО ЭКСТРЕННОЙ ОЧИСТКИ БЕЗОПАСНОСТИ")
        
        # 1. Сканирование секретов
        secrets = self.scan_for_hardcoded_secrets()
        if secrets:
            logger.warning(f"Найдены секреты: {secrets}")
        
        # 2. Удаление hardcoded секретов
        if self.files_with_keys:
            self.remove_hardcoded_secrets()
        
        # 3. Создание .env шаблона
        self.create_env_template()
        
        # 4. Обновление .gitignore
        self.update_gitignore()
        
        # 5. Удаление дублированных классов
        self.remove_duplicate_classes()
        
        logger.info("✅ ЭКСТРЕННАЯ ОЧИСТКА ЗАВЕРШЕНА")
        logger.info("⚠️  ВАЖНО: Получите новый API ключ и добавьте в .env файл!")

if __name__ == "__main__":
    cleanup = EmergencySecurityCleanup()
    cleanup.run_emergency_cleanup()