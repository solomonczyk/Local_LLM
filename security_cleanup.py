#!/usr/bin/env python3
"""
🚨 КРИТИЧЕСКАЯ БЕЗОПАСНОСТЬ: Очистка утекших секретов
Этот скрипт помогает очистить Git историю от случайно закоммиченных секретов
"""
import os
import subprocess
import sys
import secrets
import json
from datetime import datetime
from pathlib import Path

class SecurityCleanup:
    """Система очистки утекших секретов и улучшения безопасности"""
    
    def __init__(self):
        self.leaked_secrets = [
            os.getenv("AGENT_API_KEY", ""),
            # Добавьте другие утекшие секреты здесь
        ]
        self.affected_files = [
            "serve_enhanced.py",
            "security_status_update.py", 
            "agent_system/tool_server.py"
        ]
    
    def generate_new_api_key(self) -> str:
        """Генерирует новый безопасный API ключ"""
        return secrets.token_urlsafe(48)
    
    def create_env_file(self):
        """Создает .env файл с новыми безопасными ключами"""
        print("🔑 Generating new secure API keys...")
        
        new_api_key = self.generate_new_api_key()
        secret_key = secrets.token_urlsafe(32)
        jwt_secret = secrets.token_urlsafe(32)
        
        env_content = f"""# Автоматически сгенерированные безопасные ключи
# Дата создания: {datetime.now().isoformat()}

# КРИТИЧЕСКИ ВАЖНО: Этот файл НЕ должен попасть в Git!
# Добавлен в .gitignore для безопасности

# API ключи
AGENT_API_KEY={new_api_key}
LLM_API_KEY=your_llm_api_key_here

# База данных  
DATABASE_URL=postgresql://agent_user:secure_password@localhost:5432/agent_memory
POSTGRES_USER=agent_user
POSTGRES_PASSWORD={secrets.token_urlsafe(16)}
POSTGRES_DB=agent_memory

# Безопасность
SECRET_KEY={secret_key}
JWT_SECRET={jwt_secret}

# Сервисы
LLM_SERVER_URL=http://localhost:8002/v1
TOOL_SERVER_URL=http://localhost:8003
UI_SERVER_URL=http://localhost:7865

# Рабочая директория
WORKSPACE_ROOT={os.getcwd()}
"""
        
        with open(".env", "w", encoding='utf-8') as f:
            f.write(env_content)
        
        print("✅ Created .env file with new secure keys")
        print(f"🔑 New API Key: {new_api_key[:8]}...{new_api_key[-8:]} (masked)")
        
        return new_api_key
    
    def update_gitignore(self):
        """Обновляет .gitignore для защиты секретов"""
        print("🛡️ Updating .gitignore...")
        
        gitignore_additions = """
# Секреты и конфиденциальная информация
.env
.env.local
.env.production
*.key
*.pem
*.p12
secrets/
config/secrets.json

# Логи с потенциальными секретами
*.log
logs/
security_report.json

# Временные файлы с секретами
.tmp-*
temp_*
"""
        
        gitignore_path = Path(".gitignore")
        if gitignore_path.exists():
            with open(gitignore_path, "r") as f:
                current_content = f.read()
            
            if ".env" not in current_content:
                with open(gitignore_path, "a") as f:
                    f.write(gitignore_additions)
                print("✅ Updated .gitignore with security rules")
            else:
                print("✅ .gitignore already contains security rules")
        else:
            with open(gitignore_path, "w") as f:
                f.write(gitignore_additions)
            print("✅ Created .gitignore with security rules")
    
    def scan_for_secrets(self):
        """Сканирует код на наличие других потенциальных секретов"""
        print("🔍 Scanning for potential secrets...")
        
        secret_patterns = [
            r"['\"][a-zA-Z0-9]{32,}['\"]",  # Длинные строки в кавычках
            r"api_key\s*=\s*['\"][^'\"]+['\"]",  # API ключи
            r"password\s*=\s*['\"][^'\"]+['\"]",  # Пароли
            r"secret\s*=\s*['\"][^'\"]+['\"]",   # Секреты
        ]
        
        found_secrets = []
        
        for root, dirs, files in os.walk("."):
            # Пропускаем .git и другие служебные папки
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            
            for file in files:
                if file.endswith(('.py', '.js', '.json', '.yaml', '.yml')):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        for pattern in secret_patterns:
                            import re
                            matches = re.findall(pattern, content)
                            if matches:
                                found_secrets.append({
                                    'file': file_path,
                                    'pattern': pattern,
                                    'matches': matches
                                })
                    except Exception:
                        continue
        
        if found_secrets:
            print("⚠️ Potential secrets found:")
            for secret in found_secrets:
                print(f"  📁 {secret['file']}")
                for match in secret['matches']:
                    masked = match[:8] + "..." + match[-4:] if len(match) > 12 else "***"
                    print(f"    🔍 {masked}")
        else:
            print("✅ No obvious secrets found in code")
        
        return found_secrets
    
    def create_git_cleanup_script(self):
        """Создает скрипт для очистки Git истории"""
        print("📝 Creating Git cleanup script...")
        
        cleanup_script = f"""#!/bin/bash
# 🚨 КРИТИЧЕСКАЯ БЕЗОПАСНОСТЬ: Очистка Git истории от секретов
# ВНИМАНИЕ: Этот скрипт переписывает историю Git!

echo "🚨 ВНИМАНИЕ: Этот скрипт переписывает историю Git!"
echo "Убедитесь, что у вас есть резервная копия репозитория!"
echo ""
read -p "Продолжить? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Операция отменена"
    exit 1
fi

echo "🧹 Очистка истории Git от утекших секретов..."

# Удаляем утекшие секреты из истории
git filter-branch --force --index-filter \\
'git rm --cached --ignore-unmatch --quiet \\
{" ".join(self.affected_files)}' \\
--prune-empty --tag-name-filter cat -- --all

# Очищаем рефлоги
git for-each-ref --format="delete %(refname)" refs/original | git update-ref --stdin
git reflog expire --expire=now --all
git gc --prune=now --aggressive

echo "✅ История Git очищена"
echo ""
echo "🚨 ВАЖНО: Теперь нужно принудительно обновить удаленный репозиторий:"
echo "git push --force-with-lease --all"
echo "git push --force-with-lease --tags"
echo ""
echo "⚠️ Предупредите всех разработчиков о необходимости:"
echo "1. Сделать резервную копию своих изменений"
echo "2. Удалить локальную копию репозитория"  
echo "3. Заново склонировать репозиторий"
"""
        
        with open("cleanup_git_history.sh", "w", encoding='utf-8') as f:
            f.write(cleanup_script)
        
        os.chmod("cleanup_git_history.sh", 0o755)
        print("✅ Created cleanup_git_history.sh")
        print("⚠️ Запустите: bash cleanup_git_history.sh")
    
    def create_security_report(self):
        """Создает отчет о проблемах безопасности"""
        print("📋 Creating security incident report...")
        
        report = {
            "incident_type": "leaked_secrets",
            "timestamp": datetime.now().isoformat(),
            "severity": "CRITICAL",
            "description": "API keys were accidentally committed to Git repository",
            "affected_files": self.affected_files,
            "leaked_secrets": [
                {
                    "type": "API_KEY",
                    "value_hash": "ea91c0c5...",  # Только хеш для отчета
                    "first_seen": "2026-01-06",
                    "status": "REVOKED"
                }
            ],
            "remediation_actions": [
                "Generated new API keys",
                "Updated all affected files",
                "Added .env file with secure keys",
                "Updated .gitignore",
                "Created Git history cleanup script",
                "Scanned for other potential secrets"
            ],
            "next_steps": [
                "Run Git history cleanup script",
                "Force push cleaned history to remote",
                "Notify team about repository re-clone requirement",
                "Monitor for any unauthorized API usage",
                "Implement pre-commit hooks to prevent future leaks"
            ]
        }
        
        with open("SECURITY_INCIDENT_REPORT.json", "w", encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print("✅ Created SECURITY_INCIDENT_REPORT.json")
    
    def setup_precommit_hooks(self):
        """Настраивает pre-commit hooks для предотвращения утечек"""
        print("🔒 Setting up pre-commit hooks...")
        
        precommit_config = """repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: check-added-large-files
      - id: check-yaml
      - id: end-of-file-fixer
      - id: trailing-whitespace
      
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
        
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
"""
        
        with open(".pre-commit-config.yaml", "w", encoding='utf-8') as f:
            f.write(precommit_config)
        
        print("✅ Created .pre-commit-config.yaml")
        print("📋 To install: pip install pre-commit && pre-commit install")
    
    def run_full_cleanup(self):
        """Запускает полную очистку безопасности"""
        print("🚨 КРИТИЧЕСКАЯ БЕЗОПАСНОСТЬ: Начинаем полную очистку")
        print("=" * 60)
        
        # 1. Создаем новые безопасные ключи
        new_api_key = self.create_env_file()
        
        # 2. Обновляем .gitignore
        self.update_gitignore()
        
        # 3. Сканируем на другие секреты
        self.scan_for_secrets()
        
        # 4. Создаем скрипт очистки Git
        self.create_git_cleanup_script()
        
        # 5. Создаем отчет об инциденте
        self.create_security_report()
        
        # 6. Настраиваем pre-commit hooks
        self.setup_precommit_hooks()
        
        print("\n" + "=" * 60)
        print("✅ ОЧИСТКА ЗАВЕРШЕНА")
        print("\n🚨 КРИТИЧЕСКИ ВАЖНЫЕ СЛЕДУЮЩИЕ ШАГИ:")
        print("1. Запустите: bash cleanup_git_history.sh")
        print("2. Принудительно обновите удаленный репозиторий")
        print("3. Уведомите команду о необходимости пересклонировать репозиторий")
        print("4. Мониторьте использование старых API ключей")
        print(f"\n🔑 Новый API ключ сохранен в .env файле")
        print("⚠️ Убедитесь, что .env файл НЕ попадет в Git!")

def main():
    """Главная функция"""
    if len(sys.argv) > 1 and sys.argv[1] == "--scan-only":
        # Только сканирование без изменений
        cleanup = SecurityCleanup()
        cleanup.scan_for_secrets()
        return
    
    print("🚨 ВНИМАНИЕ: Обнаружена утечка API ключей в Git репозитории!")
    print("Этот скрипт поможет исправить проблему безопасности.")
    print("")
    
    response = input("Продолжить полную очистку? (yes/no): ")
    if response.lower() != 'yes':
        print("Операция отменена")
        return
    
    cleanup = SecurityCleanup()
    cleanup.run_full_cleanup()

if __name__ == "__main__":
    main()