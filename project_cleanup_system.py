#!/usr/bin/env python3
"""
СИСТЕМА ОЧИСТКИ ПРОЕКТА
Удаление неактуальных документов, дублированного кода и оптимизация структуры
"""
import os
import shutil
from pathlib import Path
from typing import List, Dict, Set, Tuple
import logging
import re
import ast
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProjectCleanupSystem:
    """Система комплексной очистки проекта"""
    
    def __init__(self):
        self.project_root = Path(".")
        self.removed_files: List[Path] = []
        self.cleaned_files: List[Path] = []
        
        # Неактуальные документы для удаления
        self.outdated_docs = [
            # Отчеты с датой 2026-01-06
            "ADVANCED_AGENT_CODE_QUALITY_REPORT_2026-01-06.md",
            "AGENT_CODE_QUALITY_REPORT_2026-01-06.md", 
            "AUDIT_REPORT_2026-01-06.md",
            "CODE_AUDIT_2026-01-06.md",
            "CODE_QUALITY_AUDIT_2026-01-06.md",
            "CODE_QUALITY_IMPROVEMENTS_2026-01-06.md",
            "EXPERT_AGENT_CODE_QUALITY_REPORT_2026-01-06.md",
            "FINAL_CODE_QUALITY_IMPROVEMENTS_2026-01-06.md",
            "FINAL_EXPERT_CODE_QUALITY_ASSESSMENT.md",
            "FINAL_STATUS_2026-01-06.md",
            "MULTIAGENT_AUDIT_2026-01-06.md",
            "MULTIAGENT_QUALITY_AUDIT_2026-01-06.md",
            "PROGRESS_REPORT_2026-01-06.md",
            "SECURITY_IMPROVEMENTS_2026-01-06.md",
            "SUCCESS_REPORT_2026-01-06.md",
            "TODAY_PLAN_2026-01-06.md",
            "UI_FIX_PROGRESS_2026-01-06.md",
            
            # Другие неактуальные документы
            "daily_report_2026-01-04.md",
            "daily_report_2026-01-05.md",
            "HTTPS_STATUS.md",
            "IMPORTANT_REMINDER.md",
            "NIP_IO_DOMAINS.md",
            "DEPLOYMENT_SUCCESS.md",
            "MULTIAGENT_EXECUTIVE_SUMMARY.md",
            "QUALITY_EXECUTIVE_SUMMARY.md",
            "NATURAL_INTERACTION_DEMO.md",
        ]
        
        # Дублированные файлы
        self.duplicate_files = [
            "ui_simple.py",  # Оставляем ui.py
            "ui_minimal.py",  # Оставляем ui.py
            "test_multiagent_quality_mock.py",  # Оставляем test_multiagent_quality.py
            "test_agent_code_quality_mock.py",  # Оставляем test_agent_code_quality.py
        ]
        
        # Временные и ненужные файлы
        self.temp_files = [
            ".tmp-agent-system.tar679728075",
            "agent-system.tar.gz",
            "agent_training_progress.json",
            "code_quality_report.json",
            "multiagent_quality_analysis.json",
            "security_report.json",
        ]
    
    def remove_outdated_documents(self) -> None:
        """Удаляет неактуальные документы"""
        logger.info("📄 Удаление неактуальных документов...")
        
        for doc_name in self.outdated_docs:
            doc_path = self.project_root / doc_name
            if doc_path.exists():
                try:
                    doc_path.unlink()
                    self.removed_files.append(doc_path)
                    logger.info(f"✅ Удален: {doc_name}")
                except Exception as e:
                    logger.error(f"❌ Ошибка при удалении {doc_name}: {e}")
            else:
                logger.debug(f"ℹ️ Файл не найден: {doc_name}")
    
    def remove_duplicate_files(self) -> None:
        """Удаляет дублированные файлы"""
        logger.info("🔄 Удаление дублированных файлов...")
        
        for file_name in self.duplicate_files:
            file_path = self.project_root / file_name
            if file_path.exists():
                try:
                    file_path.unlink()
                    self.removed_files.append(file_path)
                    logger.info(f"✅ Удален дубль: {file_name}")
                except Exception as e:
                    logger.error(f"❌ Ошибка при удалении {file_name}: {e}")
    
    def remove_temp_files(self) -> None:
        """Удаляет временные файлы"""
        logger.info("🗑️ Удаление временных файлов...")
        
        for file_name in self.temp_files:
            file_path = self.project_root / file_name
            if file_path.exists():
                try:
                    file_path.unlink()
                    self.removed_files.append(file_path)
                    logger.info(f"✅ Удален временный файл: {file_name}")
                except Exception as e:
                    logger.error(f"❌ Ошибка при удалении {file_name}: {e}")
    
    def clean_duplicate_code_in_file(self, file_path: Path) -> bool:
        """Очищает дублированный код в файле"""
        try:
            content = file_path.read_text(encoding='utf-8')
            original_content = content
            
            # Удаляем дублированные импорты
            lines = content.split('\n')
            seen_imports = set()
            cleaned_lines = []
            
            for line in lines:
                stripped = line.strip()
                
                # Проверяем импорты
                if stripped.startswith(('import ', 'from ')):
                    if stripped not in seen_imports:
                        seen_imports.add(stripped)
                        cleaned_lines.append(line)
                    else:
                        logger.debug(f"Удален дублированный импорт: {stripped}")
                else:
                    cleaned_lines.append(line)
            
            content = '\n'.join(cleaned_lines)
            
            # Удаляем дублированные определения классов и функций
            content = self._remove_duplicate_definitions(content)
            
            # Удаляем лишние пустые строки
            content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
            
            if content != original_content:
                file_path.write_text(content, encoding='utf-8')
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при очистке {file_path}: {e}")
            
        return False
    
    def _remove_duplicate_definitions(self, content: str) -> str:
        """Удаляет дублированные определения классов и функций"""
        try:
            tree = ast.parse(content)
            seen_definitions = set()
            lines = content.split('\n')
            lines_to_remove = set()
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                    definition_key = f"{type(node).__name__}:{node.name}"
                    
                    if definition_key in seen_definitions:
                        # Помечаем строки для удаления
                        start_line = node.lineno - 1
                        end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + 1
                        
                        for i in range(start_line, min(end_line, len(lines))):
                            lines_to_remove.add(i)
                            
                        logger.info(f"Найдено дублирование: {definition_key} на строке {node.lineno}")
                    else:
                        seen_definitions.add(definition_key)
            
            # Удаляем помеченные строки
            if lines_to_remove:
                cleaned_lines = [line for i, line in enumerate(lines) if i not in lines_to_remove]
                return '\n'.join(cleaned_lines)
                
        except SyntaxError:
            logger.warning(f"Не удалось парсить файл для удаления дублей")
        except Exception as e:
            logger.error(f"Ошибка при удалении дублированных определений: {e}")
            
        return content
    
    def clean_python_files(self) -> None:
        """Очищает Python файлы от дублированного кода"""
        logger.info("🐍 Очистка Python файлов от дублей...")
        
        python_files = list(self.project_root.rglob("*.py"))
        
        for py_file in python_files:
            # Пропускаем файлы в .venv и .git
            if any(part.startswith('.') for part in py_file.parts):
                continue
                
            if self.clean_duplicate_code_in_file(py_file):
                self.cleaned_files.append(py_file)
                logger.info(f"✅ Очищен: {py_file.name}")
    
    def remove_unused_imports(self) -> None:
        """Удаляет неиспользуемые импорты из Python файлов"""
        logger.info("📦 Удаление неиспользуемых импортов...")
        
        python_files = [
            "code_quality_improvement_system.py",
            "auto_code_formatter.py", 
            "quality_progress_monitor.py",
            "ui.py",
        ]
        
        for file_name in python_files:
            file_path = self.project_root / file_name
            if file_path.exists():
                self._remove_unused_imports_from_file(file_path)
    
    def _remove_unused_imports_from_file(self, file_path: Path) -> None:
        """Удаляет неиспользуемые импорты из конкретного файла"""
        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            # Простая эвристика для определения неиспользуемых импортов
            import_lines = []
            code_lines = []
            
            for i, line in enumerate(lines):
                if line.strip().startswith(('import ', 'from ')):
                    import_lines.append((i, line))
                else:
                    code_lines.append(line)
            
            code_content = '\n'.join(code_lines)
            used_imports = []
            
            for line_num, import_line in import_lines:
                # Извлекаем имена импортов
                if import_line.strip().startswith('import '):
                    module_name = import_line.replace('import ', '').split(' as ')[0].strip()
                    if module_name in code_content:
                        used_imports.append((line_num, import_line))
                elif import_line.strip().startswith('from '):
                    # Для from imports проверяем более детально
                    used_imports.append((line_num, import_line))  # Пока оставляем все from imports
            
            # Создаем новый контент
            new_lines = [''] * len(lines)
            for line_num, import_line in used_imports:
                new_lines[line_num] = import_line
            
            for i, line in enumerate(lines):
                if not line.strip().startswith(('import ', 'from ')):
                    new_lines[i] = line
            
            # Удаляем пустые строки от удаленных импортов
            final_lines = [line for line in new_lines if line is not None]
            
            new_content = '\n'.join(final_lines)
            if new_content != content:
                file_path.write_text(new_content, encoding='utf-8')
                logger.info(f"✅ Удалены неиспользуемые импорты: {file_path.name}")
                
        except Exception as e:
            logger.error(f"Ошибка при удалении импортов из {file_path}: {e}")
    
    def create_project_structure_report(self) -> None:
        """Создает отчет о новой структуре проекта"""
        logger.info("📊 Создание отчета о структуре проекта...")
        
        report = """# 📁 СТРУКТУРА ПРОЕКТА ПОСЛЕ ОЧИСТКИ

## 🎯 Результаты очистки

### ✅ Удаленные файлы
"""
        
        if self.removed_files:
            for file_path in self.removed_files:
                report += f"- ❌ {file_path.name}\n"
        else:
            report += "- Нет удаленных файлов\n"
        
        report += "\n### 🧹 Очищенные файлы\n"
        
        if self.cleaned_files:
            for file_path in self.cleaned_files:
                report += f"- ✅ {file_path.name}\n"
        else:
            report += "- Нет очищенных файлов\n"
        
        report += f"""

## 📈 Статистика
- **Удалено файлов:** {len(self.removed_files)}
- **Очищено файлов:** {len(self.cleaned_files)}
- **Дата очистки:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 🎯 Рекомендуемая структура проекта

```
project/
├── src/                    # Основной код
│   ├── agent_runtime/      # Среда выполнения агентов
│   ├── agent_system/       # Система агентов
│   └── ui/                 # Пользовательский интерфейс
├── tests/                  # Тесты
├── docs/                   # Документация
├── scripts/                # Скрипты развертывания
├── config/                 # Конфигурационные файлы
└── requirements.txt        # Зависимости
```

## 🔧 Следующие шаги

1. **Реорганизация файлов** - переместить файлы в новую структуру
2. **Обновление импортов** - исправить пути импортов
3. **Добавление type hints** - улучшить типизацию
4. **Создание тестов** - добавить unit тесты
5. **Настройка CI/CD** - автоматизировать проверки качества

---
*Отчет сгенерирован системой очистки проекта*
"""
        
        report_path = self.project_root / "PROJECT_CLEANUP_REPORT.md"
        report_path.write_text(report, encoding='utf-8')
        logger.info(f"✅ Создан отчет: {report_path.name}")
    
    def run_full_cleanup(self) -> None:
        """Запускает полную очистку проекта"""
        logger.info("🚀 НАЧАЛО ПОЛНОЙ ОЧИСТКИ ПРОЕКТА")
        
        # 1. Удаление неактуальных документов
        self.remove_outdated_documents()
        
        # 2. Удаление дублированных файлов
        self.remove_duplicate_files()
        
        # 3. Удаление временных файлов
        self.remove_temp_files()
        
        # 4. Очистка Python файлов
        self.clean_python_files()
        
        # 5. Удаление неиспользуемых импортов
        self.remove_unused_imports()
        
        # 6. Создание отчета
        self.create_project_structure_report()
        
        logger.info("✅ ПОЛНАЯ ОЧИСТКА ПРОЕКТА ЗАВЕРШЕНА")
        logger.info(f"📊 Удалено файлов: {len(self.removed_files)}")
        logger.info(f"🧹 Очищено файлов: {len(self.cleaned_files)}")

if __name__ == "__main__":
    cleanup = ProjectCleanupSystem()
    cleanup.run_full_cleanup()