#!/usr/bin/env python3
"""
Автоматический форматировщик кода для достижения идеального качества
Интегрируется с системой улучшения качества кода
"""
import subprocess
import sys
import os
from pathlib import Path
from typing import List, Dict, Any
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutoCodeFormatter:
    """Автоматический форматировщик кода"""
    
    def __init__(self):
        self.tools = {
            'black': 'black',
            'isort': 'isort', 
            'flake8': 'flake8',
            'mypy': 'mypy'
        }
        self.check_tools()
    
    def check_tools(self):
        """Проверяет наличие необходимых инструментов"""
        missing_tools = []
        
        for tool_name, command in self.tools.items():
            try:
                subprocess.run([command, '--version'], 
                             capture_output=True, check=True)
                logger.info(f"✅ {tool_name} доступен")
            except (subprocess.CalledProcessError, FileNotFoundError):
                missing_tools.append(tool_name)
                logger.warning(f"❌ {tool_name} не найден")
        
        if missing_tools:
            logger.info("Установка недостающих инструментов...")
            self.install_tools(missing_tools)
    
    def install_tools(self, tools: List[str]):
        """Устанавливает недостающие инструменты"""
        tool_packages = {
            'black': 'black',
            'isort': 'isort',
            'flake8': 'flake8',
            'mypy': 'mypy'
        }
        
        for tool in tools:
            if tool in tool_packages:
                try:
                    subprocess.run([
                        sys.executable, '-m', 'pip', 'install', 
                        tool_packages[tool]
                    ], check=True)
                    logger.info(f"✅ Установлен {tool}")
                except subprocess.CalledProcessError:
                    logger.error(f"❌ Не удалось установить {tool}")
    
    def format_file(self, file_path: str) -> Dict[str, Any]:
        """Форматирует один файл"""
        results = {
            'file': file_path,
            'black': False,
            'isort': False,
            'flake8_issues': [],
            'mypy_issues': []
        }
        
        if not Path(file_path).exists():
            logger.error(f"Файл не найден: {file_path}")
            return results
        
        # Black форматирование
        try:
            result = subprocess.run([
                'black', '--line-length', '120', file_path
            ], capture_output=True, text=True)
            results['black'] = result.returncode == 0
            if results['black']:
                logger.info(f"✅ Black: {file_path}")
            else:
                logger.warning(f"❌ Black: {file_path} - {result.stderr}")
        except Exception as e:
            logger.error(f"Ошибка Black для {file_path}: {e}")
        
        # isort сортировка импортов
        try:
            result = subprocess.run([
                'isort', '--profile', 'black', '--line-length', '120', file_path
            ], capture_output=True, text=True)
            results['isort'] = result.returncode == 0
            if results['isort']:
                logger.info(f"✅ isort: {file_path}")
            else:
                logger.warning(f"❌ isort: {file_path} - {result.stderr}")
        except Exception as e:
            logger.error(f"Ошибка isort для {file_path}: {e}")
        
        # flake8 проверка стиля
        try:
            result = subprocess.run([
                'flake8', '--max-line-length', '120', 
                '--ignore', 'E203,W503', file_path
            ], capture_output=True, text=True)
            
            if result.stdout:
                results['flake8_issues'] = result.stdout.strip().split('\n')
                logger.warning(f"⚠️ flake8 issues в {file_path}: {len(results['flake8_issues'])}")
            else:
                logger.info(f"✅ flake8: {file_path}")
        except Exception as e:
            logger.error(f"Ошибка flake8 для {file_path}: {e}")
        
        # mypy проверка типов
        try:
            result = subprocess.run([
                'mypy', '--ignore-missing-imports', file_path
            ], capture_output=True, text=True)
            
            if result.stdout and 'Success' not in result.stdout:
                results['mypy_issues'] = result.stdout.strip().split('\n')
                logger.warning(f"⚠️ mypy issues в {file_path}: {len(results['mypy_issues'])}")
            else:
                logger.info(f"✅ mypy: {file_path}")
        except Exception as e:
            logger.error(f"Ошибка mypy для {file_path}: {e}")
        
        return results
    
    def format_directory(self, directory: str, pattern: str = "*.py") -> List[Dict[str, Any]]:
        """Форматирует все Python файлы в директории"""
        results = []
        
        for file_path in Path(directory).rglob(pattern):
            if file_path.is_file():
                result = self.format_file(str(file_path))
                results.append(result)
        
        return results
    
    def create_pre_commit_config(self):
        """Создает конфигурацию pre-commit hooks"""
        config_content = """
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        args: [--line-length=120]
        
  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: [--profile=black, --line-length=120]
        
  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=120, --ignore=E203,W503]
        
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        args: [--ignore-missing-imports]
"""
        
        with open('.pre-commit-config.yaml', 'w') as f:
            f.write(config_content.strip())
        
        logger.info("✅ Создан .pre-commit-config.yaml")
        
        # Установка pre-commit hooks
        try:
            subprocess.run(['pre-commit', 'install'], check=True)
            logger.info("✅ Pre-commit hooks установлены")
        except subprocess.CalledProcessError:
            logger.warning("❌ Не удалось установить pre-commit hooks")
    
    def generate_report(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Генерирует отчет о форматировании"""
        total_files = len(results)
        black_success = sum(1 for r in results if r['black'])
        isort_success = sum(1 for r in results if r['isort'])
        flake8_issues = sum(len(r['flake8_issues']) for r in results)
        mypy_issues = sum(len(r['mypy_issues']) for r in results)
        
        report = {
            'summary': {
                'total_files': total_files,
                'black_success_rate': black_success / total_files if total_files > 0 else 0,
                'isort_success_rate': isort_success / total_files if total_files > 0 else 0,
                'total_flake8_issues': flake8_issues,
                'total_mypy_issues': mypy_issues
            },
            'details': results
        }
        
        return report

def main():
    """Основная функция"""
    formatter = AutoCodeFormatter()
    
    # Форматирование ключевых директорий
    directories = ['agent_system', 'agent_runtime']
    all_results = []
    
    for directory in directories:
        if Path(directory).exists():
            logger.info(f"Форматирование директории: {directory}")
            results = formatter.format_directory(directory)
            all_results.extend(results)
        else:
            logger.warning(f"Директория не найдена: {directory}")
    
    # Форматирование корневых Python файлов
    root_files = [
        'code_quality_improvement_system.py',
        'auto_code_formatter.py',
        'agent_training_system.py'
    ]
    
    for file_path in root_files:
        if Path(file_path).exists():
            result = formatter.format_file(file_path)
            all_results.append(result)
    
    # Генерация отчета
    report = formatter.generate_report(all_results)
    
    print("\n📊 Отчет о форматировании:")
    print(f"   Всего файлов: {report['summary']['total_files']}")
    print(f"   Black успешно: {report['summary']['black_success_rate']:.1%}")
    print(f"   isort успешно: {report['summary']['isort_success_rate']:.1%}")
    print(f"   flake8 проблем: {report['summary']['total_flake8_issues']}")
    print(f"   mypy проблем: {report['summary']['total_mypy_issues']}")
    
    # Создание pre-commit конфигурации
    formatter.create_pre_commit_config()
    
    logger.info("Автоматическое форматирование завершено")

if __name__ == "__main__":
    main()