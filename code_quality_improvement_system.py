"""
Система улучшения качества кода агентов
Интегрированная система для достижения 10/10 баллов в тестах качества кода
"""
import json
import time
import ast
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import re
import os


class QualityLevel(Enum):
    """Уровни качества кода"""
    CRITICAL = 0
    POOR = 1
    BASIC = 2
    GOOD = 3
    EXCELLENT = 4
    PERFECT = 5


@dataclass
class QualityMetrics:
    """Метрики качества кода"""
    syntax_score: float = 0.0
    style_score: float = 0.0
    security_score: float = 0.0
    documentation_score: float = 0.0
    complexity_score: float = 0.0
    architecture_score: float = 0.0
    performance_score: float = 0.0
    overall_score: float = 0.0
    
    def calculate_overall(self) -> float:
        """Вычисляет общую оценку"""
        scores = [
            self.syntax_score,
            self.style_score, 
            self.security_score,
            self.documentation_score,
            self.complexity_score,
            self.architecture_score,
            self.performance_score
        ]
        self.overall_score = sum(scores) / len(scores)
        return self.overall_score


@dataclass
class ImprovementTask:
    """Задача по улучшению качества"""
    file_path: str
    issue_type: str
    severity: str
    description: str
    fix_suggestion: str
    line_number: Optional[int] = None
    estimated_time: int = 5  # минуты


class CodeQualityImprover:
    """Система улучшения качества кода агентов"""
    
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root)
        self.logger = self._setup_logging()
        self.improvement_tasks: List[ImprovementTask] = []
        self.metrics_history: List[Dict] = []
        
    def _setup_logging(self) -> logging.Logger:
        """Настраивает логирование"""
        logger = logging.getLogger("CodeQualityImprover")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('code_quality_improvement.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class QualityLevel(Enum):
    """Уровни качества кода"""
    CRITICAL = 0  # 0-3 балла
    POOR = 1      # 3-5 баллов
    FAIR = 2      # 5-7 баллов
    GOOD = 3      # 7-8.5 баллов
    EXCELLENT = 4 # 8.5-10 баллов

@dataclass
class QualityMetrics:
    """Метрики качества кода"""
    syntax_score: float = 0.0
    style_score: float = 0.0
    documentation_score: float = 0.0
    error_handling_score: float = 0.0
    type_hints_score: float = 0.0
    complexity_score: float = 0.0
    security_score: float = 0.0
    architecture_score: float = 0.0
    performance_score: float = 0.0
    requirements_compliance: float = 0.0
    
    @property
    def overall_score(self) -> float:
        """Общая оценка качества"""
        scores = [
            self.syntax_score,
            self.style_score,
            self.documentation_score,
            self.error_handling_score,
            self.type_hints_score,
            self.complexity_score,
            self.security_score,
            self.architecture_score,
            self.performance_score,
            self.requirements_compliance
        ]
        return sum(scores) / len(scores)
    
    @property
    def quality_level(self) -> QualityLevel:
        """Определяет уровень качества"""
        score = self.overall_score
        if score >= 8.5:
            return QualityLevel.EXCELLENT
        elif score >= 7.0:
            return QualityLevel.GOOD
        elif score >= 5.0:
            return QualityLevel.FAIR
        elif score >= 3.0:
            return QualityLevel.POOR
        else:
            return QualityLevel.CRITICAL

@dataclass
class ImprovementSuggestion:
    """Предложение по улучшению"""
    category: str
    priority: str  # CRITICAL, HIGH, MEDIUM, LOW
    description: str
    code_example: Optional[str] = None
    fix_example: Optional[str] = None
    impact_score: float = 0.0

class CodeQualityAnalyzer:
    """Анализатор качества кода"""
    
    def __init__(self):
        self.patterns = self._load_quality_patterns()
        
    def _load_quality_patterns(self) -> Dict[str, Any]:
        """Загружает паттерны для анализа качества"""
        return {
            'style_issues': [
                r'print\(',  # Использование print вместо logging
                r'\s+$',     # Trailing whitespace
                r'.{121,}',  # Длинные строки
            ],
            'security_issues': [
                r'eval\(',
                r'exec\(',
                r'os\.system\(',
                r'subprocess\.call\(',
                r'["\']password["\']',
                r'["\']secret["\']',
                r'["\']api_key["\']',
            ],
            'error_handling': [
                r'except:',  # Bare except
                r'pass\s*$', # Empty except blocks
            ],
            'documentation': [
                r'def\s+\w+\([^)]*\):\s*$',  # Functions without docstrings
                r'class\s+\w+[^:]*:\s*$',    # Classes without docstrings
            ]
        }
    
    def analyze_file(self, file_path: str) -> Tuple[QualityMetrics, List[ImprovementSuggestion]]:
        """Анализирует файл и возвращает метрики и предложения"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            metrics = QualityMetrics()
            suggestions = []
            
            # Анализ синтаксиса
            metrics.syntax_score = self._analyze_syntax(content)
            
            # Анализ стиля
            style_score, style_suggestions = self._analyze_style(content)
            metrics.style_score = style_score
            suggestions.extend(style_suggestions)
            
            # Анализ документации
            doc_score, doc_suggestions = self._analyze_documentation(content)
            metrics.documentation_score = doc_score
            suggestions.extend(doc_suggestions)
            
            # Анализ обработки ошибок
            error_score, error_suggestions = self._analyze_error_handling(content)
            metrics.error_handling_score = error_score
            suggestions.extend(error_suggestions)
            
            # Анализ type hints
            metrics.type_hints_score = self._analyze_type_hints(content)
            
            # Анализ сложности
            metrics.complexity_score = self._analyze_complexity(content)
            
            # Анализ безопасности
            security_score, security_suggestions = self._analyze_security(content)
            metrics.security_score = security_score
            suggestions.extend(security_suggestions)
            
            return metrics, suggestions
            
        except Exception as e:
            logger.error(f"Ошибка анализа файла {file_path}: {e}")
            return QualityMetrics(), []
    
    def _analyze_syntax(self, content: str) -> float:
        """Анализирует синтаксис кода"""
        try:
            ast.parse(content)
            return 10.0
        except SyntaxError as e:
            logger.warning(f"Синтаксическая ошибка: {e}")
            return 0.0
    
    def _analyze_style(self, content: str) -> Tuple[float, List[ImprovementSuggestion]]:
        """Анализирует стиль кода"""
        suggestions = []
        issues = 0
        total_lines = len(content.splitlines())
        
        # Проверка на print statements
        print_matches = re.findall(r'print\(', content)
        if print_matches:
            issues += len(print_matches)
            suggestions.append(ImprovementSuggestion(
                category="style",
                priority="HIGH",
                description=f"Найдено {len(print_matches)} использований print(). Используйте logging.",
                code_example="print('Debug info')",
                fix_example="logger.info('Debug info')",
                impact_score=2.0
            ))
        
        # Проверка на trailing whitespace
        trailing_ws = re.findall(r'\s+$', content, re.MULTILINE)
        if trailing_ws:
            issues += len(trailing_ws)
            suggestions.append(ImprovementSuggestion(
                category="style",
                priority="MEDIUM",
                description=f"Найдено {len(trailing_ws)} строк с лишними пробелами в конце",
                impact_score=0.5
            ))
        
        # Проверка длинных строк
        long_lines = [line for line in content.splitlines() if len(line) > 120]
        if long_lines:
            issues += len(long_lines)
            suggestions.append(ImprovementSuggestion(
                category="style",
                priority="MEDIUM",
                description=f"Найдено {len(long_lines)} строк длиннее 120 символов",
                impact_score=1.0
            ))
        
        # Расчет оценки стиля
        if total_lines == 0:
            return 10.0, suggestions
        
        issue_ratio = issues / total_lines
        style_score = max(0.0, 10.0 - (issue_ratio * 20))
        
        return style_score, suggestions
    
    def _analyze_documentation(self, content: str) -> Tuple[float, List[ImprovementSuggestion]]:
        """Анализирует документацию"""
        suggestions = []
        
        # Поиск функций без docstrings
        function_pattern = r'def\s+(\w+)\([^)]*\):\s*\n(?!\s*""")'
        functions_without_docs = re.findall(function_pattern, content)
        
        # Поиск классов без docstrings
        class_pattern = r'class\s+(\w+)[^:]*:\s*\n(?!\s*""")'
        classes_without_docs = re.findall(class_pattern, content)
        
        total_functions = len(re.findall(r'def\s+\w+\(', content))
        total_classes = len(re.findall(r'class\s+\w+', content))
        
        if functions_without_docs:
            suggestions.append(ImprovementSuggestion(
                category="documentation",
                priority="HIGH",
                description=f"Функции без docstrings: {', '.join(functions_without_docs)}",
                code_example="def function():\n    pass",
                fix_example='def function():\n    """Описание функции."""\n    pass',
                impact_score=2.0
            ))
        
        if classes_without_docs:
            suggestions.append(ImprovementSuggestion(
                category="documentation",
                priority="HIGH",
                description=f"Классы без docstrings: {', '.join(classes_without_docs)}",
                impact_score=2.0
            ))
        
        # Расчет оценки документации
        total_items = total_functions + total_classes
        if total_items == 0:
            return 10.0, suggestions
        
        undocumented = len(functions_without_docs) + len(classes_without_docs)
        doc_score = max(0.0, 10.0 - (undocumented / total_items * 10))
        
        return doc_score, suggestions
    
    def _analyze_error_handling(self, content: str) -> Tuple[float, List[ImprovementSuggestion]]:
        """Анализирует обработку ошибок"""
        suggestions = []
        issues = 0
        
        # Bare except
        bare_except = re.findall(r'except:', content)
        if bare_except:
            issues += len(bare_except)
            suggestions.append(ImprovementSuggestion(
                category="error_handling",
                priority="CRITICAL",
                description=f"Найдено {len(bare_except)} bare except блоков",
                code_example="except:",
                fix_example="except SpecificException as e:",
                impact_score=3.0
            ))
        
        # Empty except blocks
        empty_except = re.findall(r'except[^:]*:\s*pass', content)
        if empty_except:
            issues += len(empty_except)
            suggestions.append(ImprovementSuggestion(
                category="error_handling",
                priority="HIGH",
                description=f"Найдено {len(empty_except)} пустых except блоков",
                impact_score=2.0
            ))
        
        # Расчет оценки
        total_except = len(re.findall(r'except', content))
        if total_except == 0:
            return 8.0, suggestions  # Нет обработки ошибок - средняя оценка
        
        error_score = max(0.0, 10.0 - (issues / total_except * 10))
        return error_score, suggestions
    
    def _analyze_type_hints(self, content: str) -> float:
        """Анализирует использование type hints"""
        try:
            tree = ast.parse(content)
            
            total_functions = 0
            functions_with_hints = 0
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    total_functions += 1
                    
                    # Проверяем аннотации аргументов
                    has_arg_hints = any(arg.annotation for arg in node.args.args)
                    has_return_hint = node.returns is not None
                    
                    if has_arg_hints or has_return_hint:
                        functions_with_hints += 1
            
            if total_functions == 0:
                return 10.0
            
            hint_ratio = functions_with_hints / total_functions
            return hint_ratio * 10.0
            
        except Exception:
            return 5.0  # Средняя оценка при ошибке анализа
    
    def _analyze_complexity(self, content: str) -> float:
        """Анализирует сложность кода"""
        try:
            tree = ast.parse(content)
            
            max_complexity = 0
            total_complexity = 0
            function_count = 0
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    function_count += 1
                    complexity = self._calculate_cyclomatic_complexity(node)
                    total_complexity += complexity
                    max_complexity = max(max_complexity, complexity)
            
            if function_count == 0:
                return 10.0
            
            avg_complexity = total_complexity / function_count
            
            # Оценка на основе средней сложности
            if avg_complexity <= 5:
                return 10.0
            elif avg_complexity <= 10:
                return 8.0
            elif avg_complexity <= 15:
                return 6.0
            else:
                return max(0.0, 10.0 - (avg_complexity - 15) * 0.5)
                
        except Exception:
            return 5.0
    
    def _calculate_cyclomatic_complexity(self, node: ast.FunctionDef) -> int:
        """Вычисляет цикломатическую сложность функции"""
        complexity = 1  # Базовая сложность
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        
        return complexity
    
    def _analyze_security(self, content: str) -> Tuple[float, List[ImprovementSuggestion]]:
        """Анализирует безопасность кода"""
        suggestions = []
        security_issues = 0
        
        # Опасные функции
        dangerous_patterns = {
            r'eval\(': "Использование eval() крайне опасно",
            r'exec\(': "Использование exec() крайне опасно",
            r'os\.system\(': "Использование os.system() небезопасно",
            r'subprocess\.call\([^)]*shell=True': "shell=True в subprocess опасно",
        }
        
        for pattern, message in dangerous_patterns.items():
            matches = re.findall(pattern, content)
            if matches:
                security_issues += len(matches)
                suggestions.append(ImprovementSuggestion(
                    category="security",
                    priority="CRITICAL",
                    description=f"{message}. Найдено {len(matches)} использований",
                    impact_score=5.0
                ))
        
        # Hardcoded secrets
        secret_patterns = [
            r'["\']password["\']\s*[:=]',
            r'["\']secret["\']\s*[:=]',
            r'["\']api_key["\']\s*[:=]',
            r'["\']token["\']\s*[:=]',
        ]
        
        for pattern in secret_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                security_issues += len(matches)
                suggestions.append(ImprovementSuggestion(
                    category="security",
                    priority="HIGH",
                    description=f"Возможные hardcoded secrets. Найдено {len(matches)} случаев",
                    impact_score=3.0
                ))
        
        # Расчет оценки безопасности
        if security_issues == 0:
            return 10.0, suggestions
        else:
            security_score = max(0.0, 10.0 - security_issues * 2.0)
            return security_score, suggestions

class CodeQualityImprover:
    """Система улучшения качества кода"""
    
    def __init__(self):
        self.analyzer = CodeQualityAnalyzer()
        self.improvement_history = []
        
    def improve_file(self, file_path: str) -> Dict[str, Any]:
        """Улучшает качество кода в файле"""
        logger.info(f"Начинаю улучшение файла: {file_path}")
        
        # Анализ до улучшения
        metrics_before, suggestions = self.analyzer.analyze_file(file_path)
        
        # Применение автоматических исправлений
        applied_fixes = self._apply_automatic_fixes(file_path, suggestions)
        
        # Анализ после улучшения
        metrics_after, _ = self.analyzer.analyze_file(file_path)
        
        improvement_result = {
            'file_path': file_path,
            'timestamp': datetime.now().isoformat(),
            'metrics_before': asdict(metrics_before),
            'metrics_after': asdict(metrics_after),
            'improvement': metrics_after.overall_score - metrics_before.overall_score,
            'applied_fixes': applied_fixes,
            'remaining_suggestions': len([s for s in suggestions if not s.category in applied_fixes])
        }
        
        self.improvement_history.append(improvement_result)
        
        logger.info(f"Улучшение завершено. Прирост качества: {improvement_result['improvement']:.2f}")
        
        return improvement_result
    
    def _apply_automatic_fixes(self, file_path: str, suggestions: List[ImprovementSuggestion]) -> List[str]:
        """Применяет автоматические исправления"""
        applied_fixes = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Исправление trailing whitespace
            if any(s.category == 'style' and 'лишними пробелами' in s.description for s in suggestions):
                content = re.sub(r'\s+$', '', content, flags=re.MULTILINE)
                applied_fixes.append('trailing_whitespace')
            
            # Замена print на logging (базовая)
            if any(s.category == 'style' and 'print(' in s.description for s in suggestions):
                # Добавляем import logging если его нет
                if 'import logging' not in content:
                    content = 'import logging\n' + content
                
                # Добавляем logger если его нет
                if 'logger = logging.getLogger' not in content:
                    content = content.replace(
                        'import logging\n',
                        'import logging\n\nlogger = logging.getLogger(__name__)\n'
                    )
                
def main():
    """Главная функция для запуска системы улучшения качества"""
    print("🚀 Code Quality Improvement System")
    print("=" * 50)
    
    # Создаем систему улучшения
    improver = CodeQualityImprover()
    
    # Запускаем анализ
    print("📊 Running initial analysis...")
    initial_metrics = improver.run_full_analysis()
    
    print(f"\n📋 Initial Quality Report:")
    print(f"  🔒 Security Score: {initial_metrics.security_score:.1f}/10")
    print(f"  🎨 Style Score: {initial_metrics.style_score:.1f}/10")
    print(f"  🧮 Complexity Score: {initial_metrics.complexity_score:.1f}/10")
    print(f"  📚 Documentation Score: {initial_metrics.documentation_score:.1f}/10")
    print(f"  🏗️ Architecture Score: {initial_metrics.architecture_score:.1f}/10")
    print(f"  ⚡ Performance Score: {initial_metrics.performance_score:.1f}/10")
    print(f"  🎯 Overall Score: {initial_metrics.overall_score:.1f}/10")
    
    print(f"\n🔍 Found {len(improver.improvement_tasks)} issues to fix")
    
    # Спрашиваем разрешение на автоматические исправления
    if len(improver.improvement_tasks) > 0:
        response = input("\n🔧 Run automatic improvements? (yes/no): ")
        if response.lower() == 'yes':
            print("\n🚀 Running automatic improvements...")
            success = improver.run_auto_improvements()
            
            if success:
                print("✅ Automatic improvements completed successfully!")
            else:
                print("⚠️ Some improvements failed - check logs for details")
        else:
            print("📋 Improvement report saved to code_quality_improvement_report.json")
    else:
        print("✅ No issues found - code quality is excellent!")
    
    print("\n🎯 Next steps:")
    print("1. Review the improvement report")
    print("2. Fix remaining manual issues")
    print("3. Add unit tests")
    print("4. Set up pre-commit hooks")
    print("5. Monitor quality regularly")


if __name__ == "__main__":
    main()

    def scan_security_iss