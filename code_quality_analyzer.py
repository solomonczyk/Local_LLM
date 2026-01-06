#!/usr/bin/env python3
"""
Анализатор качества кода мультиагентной системы
Проверяет: архитектуру, стиль, сложность, безопасность, тестирование
"""
import ast
import os
import re
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import defaultdict, Counter


class CodeQualityAnalyzer:
    """Анализатор качества кода"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.python_files = []
        self.analysis_results = {}

    def discover_python_files(self) -> List[Path]:
        """Найти все Python файлы в проекте"""
        python_files = []

        # Основные директории для анализа
        target_dirs = ["agent_runtime", "agent_system", "."]  # корневые файлы

        for target_dir in target_dirs:
            dir_path = self.project_root / target_dir
            if dir_path.exists():
                for py_file in dir_path.rglob("*.py"):
                    # Исключаем некоторые файлы
                    if not any(
                        exclude in str(py_file)
                        for exclude in ["__pycache__", ".venv", "venv", ".git", "test_", "lora_qwen", "codesearchnet"]
                    ):
                        python_files.append(py_file)

        self.python_files = python_files
        return python_files

    def analyze_file_metrics(self, file_path: Path) -> Dict[str, Any]:
        """Анализ метрик файла"""
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()

            # Базовые метрики
            metrics = {
                "file_path": str(file_path.relative_to(self.project_root)),
                "total_lines": len(lines),
                "code_lines": len([line for line in lines if line.strip() and not line.strip().startswith("#")]),
                "comment_lines": len([line for line in lines if line.strip().startswith("#")]),
                "blank_lines": len([line for line in lines if not line.strip()]),
                "file_size_kb": round(len(content) / 1024, 2),
            }

            # Анализ AST
            try:
                tree = ast.parse(content)
                ast_metrics = self._analyze_ast(tree)
                metrics.update(ast_metrics)
            except SyntaxError as e:
                metrics["syntax_error"] = str(e)
                metrics["ast_analysis"] = False
            else:
                metrics["ast_analysis"] = True

            # Анализ стиля
            style_issues = self._analyze_style(content, lines)
            metrics["style_issues"] = style_issues

            # Анализ сложности
            complexity = self._analyze_complexity(content, lines)
            metrics["complexity"] = complexity

            # Анализ безопасности
            security_issues = self._analyze_security(content)
            metrics["security_issues"] = security_issues

            return metrics

        except Exception as e:
            return {
                "file_path": str(file_path.relative_to(self.project_root)),
                "error": str(e),
                "analysis_failed": True,
            }

    def _analyze_ast(self, tree: ast.AST) -> Dict[str, Any]:
        """Анализ AST дерева"""
        classes = []
        functions = []
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                        "methods": len([n for n in node.body if isinstance(n, ast.FunctionDef)]),
                        "docstring": ast.get_docstring(node) is not None,
                    }
                )
            elif isinstance(node, ast.FunctionDef):
                # Только функции верхнего уровня (не методы)
                if not any(
                    isinstance(parent, ast.ClassDef)
                    for parent in ast.walk(tree)
                    if hasattr(parent, "body") and node in getattr(parent, "body", [])
                ):
                    functions.append(
                        {
                            "name": node.name,
                            "line": node.lineno,
                            "args_count": len(node.args.args),
                            "docstring": ast.get_docstring(node) is not None,
                            "is_async": isinstance(node, ast.AsyncFunctionDef),
                        }
                    )
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                else:
                    imports.append(node.module or "relative")

        return {
            "classes": classes,
            "functions": functions,
            "imports": imports,
            "class_count": len(classes),
            "function_count": len(functions),
            "import_count": len(imports),
        }

    def _analyze_style(self, content: str, lines: List[str]) -> List[Dict[str, Any]]:
        """Анализ стиля кода"""
        issues = []

        for i, line in enumerate(lines, 1):
            # Длина строки
            if len(line) > 120:
                issues.append(
                    {
                        "type": "line_length",
                        "line": i,
                        "message": f"Line too long ({len(line)} > 120 chars)",
                        "severity": "warning",
                    }
                )

            # Trailing whitespace
            if line.endswith(" ") or line.endswith("\t"):
                issues.append(
                    {"type": "trailing_whitespace", "line": i, "message": "Trailing whitespace", "severity": "info"}
                )

            # Множественные импорты
            if line.strip().startswith("import ") and "," in line:
                issues.append(
                    {
                        "type": "multiple_imports",
                        "line": i,
                        "message": "Multiple imports on one line",
                        "severity": "warning",
                    }
                )

            # Использование print() (может быть debug)
            if "print(" in line and not line.strip().startswith("#"):
                issues.append(
                    {
                        "type": "print_statement",
                        "line": i,
                        "message": "Print statement (consider logging)",
                        "severity": "info",
                    }
                )

        # Проверка docstrings
        if '"""' not in content and "'''" not in content:
            issues.append(
                {"type": "no_docstrings", "line": 1, "message": "No docstrings found in file", "severity": "warning"}
            )

        return issues

    def _analyze_complexity(self, content: str, lines: List[str]) -> Dict[str, Any]:
        """Анализ сложности кода"""

        # Цикломатическая сложность (приблизительная)
        complexity_keywords = ["if", "elif", "else", "for", "while", "try", "except", "with"]
        complexity_score = 0

        for line in lines:
            stripped = line.strip()
            for keyword in complexity_keywords:
                if stripped.startswith(keyword + " ") or stripped.startswith(keyword + ":"):
                    complexity_score += 1

        # Уровень вложенности
        max_nesting = 0
        current_nesting = 0

        for line in lines:
            if line.strip():
                indent = len(line) - len(line.lstrip())
                current_nesting = indent // 4
                max_nesting = max(max_nesting, current_nesting)

        # Длинные функции (эвристика)
        long_functions = []
        in_function = False
        function_start = 0
        function_name = ""

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("def ") or stripped.startswith("async def "):
                if in_function and i - function_start > 50:
                    long_functions.append(
                        {"name": function_name, "start_line": function_start, "length": i - function_start}
                    )
                in_function = True
                function_start = i
                function_name = stripped.split("(")[0].replace("def ", "").replace("async ", "")
            elif stripped.startswith("class "):
                in_function = False

        return {
            "cyclomatic_complexity": complexity_score,
            "max_nesting_level": max_nesting,
            "long_functions": long_functions,
            "complexity_score": complexity_score + max_nesting * 2,
        }

    def _analyze_security(self, content: str) -> List[Dict[str, Any]]:
        """Анализ проблем безопасности"""
        issues = []

        security_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password", "high"),
            (r'api_key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key", "high"),
            (r'secret\s*=\s*["\'][^"\']+["\']', "Hardcoded secret", "high"),
            (r"eval\s*\(", "Use of eval() function", "high"),
            (r"exec\s*\(", "Use of exec() function", "high"),
            (r"subprocess\.call\([^)]*shell=True", "Shell injection risk", "medium"),
            (r"os\.system\(", "OS command injection risk", "medium"),
            (r"pickle\.loads?\(", "Unsafe pickle usage", "medium"),
            (r"input\s*\(", "Use of input() function", "low"),
            (r'open\s*\([^)]*["\'][wax]', "File write operations", "info"),
        ]

        lines = content.splitlines()
        for pattern, description, severity in security_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                line_num = content[: match.start()].count("\n") + 1
                issues.append(
                    {
                        "type": "security",
                        "line": line_num,
                        "message": description,
                        "severity": severity,
                        "pattern": pattern,
                    }
                )

        return issues

    def analyze_project_structure(self) -> Dict[str, Any]:
        """Анализ структуры проекта"""

        structure = {
            "total_files": len(self.python_files),
            "directories": defaultdict(int),
            "file_types": defaultdict(int),
            "module_analysis": {},
        }

        for file_path in self.python_files:
            # Подсчет по директориям
            parent_dir = file_path.parent.name
            structure["directories"][parent_dir] += 1

            # Анализ модулей
            rel_path = file_path.relative_to(self.project_root)
            if len(rel_path.parts) > 1:
                module = rel_path.parts[0]
                if module not in structure["module_analysis"]:
                    structure["module_analysis"][module] = {"files": 0, "has_init": False, "submodules": set()}
                structure["module_analysis"][module]["files"] += 1

                # Проверка __init__.py
                init_file = file_path.parent / "__init__.py"
                if init_file.exists():
                    structure["module_analysis"][module]["has_init"] = True

                # Подмодули
                if len(rel_path.parts) > 2:
                    structure["module_analysis"][module]["submodules"].add(rel_path.parts[1])

        # Конвертируем sets в lists для JSON
        for module_info in structure["module_analysis"].values():
            module_info["submodules"] = list(module_info["submodules"])

        return structure

    def analyze_dependencies(self) -> Dict[str, Any]:
        """Анализ зависимостей"""

        all_imports = []
        import_graph = defaultdict(set)

        for file_path in self.python_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content)

                file_imports = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            file_imports.append(alias.name)
                            all_imports.append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or "relative"
                        file_imports.append(module)
                        all_imports.append(module)

                # Граф зависимостей
                rel_path = str(file_path.relative_to(self.project_root))
                import_graph[rel_path] = set(file_imports)

            except Exception:
                continue

        # Анализ популярных импортов
        import_counter = Counter(all_imports)

        # Внешние vs внутренние зависимости
        external_deps = set()
        internal_deps = set()

        for imp in all_imports:
            if imp.startswith(("agent_runtime", "agent_system")):
                internal_deps.add(imp)
            elif not imp.startswith(".") and imp != "relative":
                external_deps.add(imp)

        return {
            "total_imports": len(all_imports),
            "unique_imports": len(set(all_imports)),
            "external_dependencies": list(external_deps),
            "internal_dependencies": list(internal_deps),
            "most_used_imports": import_counter.most_common(10),
            "import_graph_size": len(import_graph),
        }

    def calculate_quality_scores(self, file_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Расчет оценок качества"""

        if not file_metrics:
            return {"error": "No files analyzed"}

        # Фильтруем файлы с ошибками
        valid_files = [f for f in file_metrics if not f.get("analysis_failed", False)]

        if not valid_files:
            return {"error": "No valid files analyzed"}

        # Метрики по всему проекту
        total_lines = sum(f["total_lines"] for f in valid_files)
        total_code_lines = sum(f["code_lines"] for f in valid_files)
        total_comment_lines = sum(f["comment_lines"] for f in valid_files)

        # Оценки качества (0-10)
        scores = {}

        # 1. Документированность (docstrings + комментарии)
        files_with_docstrings = sum(
            1
            for f in valid_files
            if f.get("ast_analysis")
            and any(cls.get("docstring", False) for cls in f.get("classes", []))
            or any(func.get("docstring", False) for func in f.get("functions", []))
        )

        comment_ratio = total_comment_lines / total_code_lines if total_code_lines > 0 else 0
        documentation_score = min(10, (files_with_docstrings / len(valid_files)) * 5 + comment_ratio * 50)
        scores["documentation"] = round(documentation_score, 1)

        # 2. Сложность кода
        avg_complexity = sum(f.get("complexity", {}).get("complexity_score", 0) for f in valid_files) / len(valid_files)
        max_nesting = max(f.get("complexity", {}).get("max_nesting_level", 0) for f in valid_files)
        complexity_score = max(0, 10 - (avg_complexity / 10) - (max_nesting / 2))
        scores["complexity"] = round(complexity_score, 1)

        # 3. Стиль кода
        total_style_issues = sum(len(f.get("style_issues", [])) for f in valid_files)
        style_score = max(0, 10 - (total_style_issues / len(valid_files)))
        scores["style"] = round(style_score, 1)

        # 4. Безопасность
        high_security_issues = sum(
            len([issue for issue in f.get("security_issues", []) if issue.get("severity") == "high"])
            for f in valid_files
        )
        medium_security_issues = sum(
            len([issue for issue in f.get("security_issues", []) if issue.get("severity") == "medium"])
            for f in valid_files
        )

        security_score = max(0, 10 - high_security_issues * 2 - medium_security_issues * 0.5)
        scores["security"] = round(security_score, 1)

        # 5. Архитектура (модульность)
        total_classes = sum(f.get("class_count", 0) for f in valid_files)
        total_functions = sum(f.get("function_count", 0) for f in valid_files)
        avg_file_size = sum(f["total_lines"] for f in valid_files) / len(valid_files)

        # Хорошая архитектура = умеренный размер файлов, хорошее соотношение классов/функций
        architecture_score = min(
            10,
            (10 - max(0, (avg_file_size - 200) / 50)) * 0.4
            + min(10, (total_classes + total_functions) / len(valid_files))  # размер файлов
            * 0.6,  # структурированность
        )
        scores["architecture"] = round(architecture_score, 1)

        # 6. Общая оценка
        overall_score = sum(scores.values()) / len(scores)
        scores["overall"] = round(overall_score, 1)

        return {
            "scores": scores,
            "metrics": {
                "total_files": len(valid_files),
                "total_lines": total_lines,
                "total_code_lines": total_code_lines,
                "total_comment_lines": total_comment_lines,
                "comment_ratio": round(comment_ratio * 100, 1),
                "avg_file_size": round(avg_file_size, 1),
                "total_classes": total_classes,
                "total_functions": total_functions,
                "total_style_issues": total_style_issues,
                "high_security_issues": high_security_issues,
                "medium_security_issues": medium_security_issues,
            },
        }

    def generate_report(self) -> Dict[str, Any]:
        """Генерация полного отчета"""

        print("🔍 Анализ качества кода мультиагентной системы")
        print("=" * 60)

        # Поиск файлов
        print("📁 Поиск Python файлов...")
        python_files = self.discover_python_files()
        print(f"   Найдено файлов: {len(python_files)}")

        # Анализ структуры проекта
        print("🏗️ Анализ структуры проекта...")
        structure = self.analyze_project_structure()

        # Анализ зависимостей
        print("📦 Анализ зависимостей...")
        dependencies = self.analyze_dependencies()

        # Анализ каждого файла
        print("📊 Анализ файлов...")
        file_metrics = []
        for i, file_path in enumerate(python_files, 1):
            print(f"   Анализ {i}/{len(python_files)}: {file_path.name}")
            metrics = self.analyze_file_metrics(file_path)
            file_metrics.append(metrics)

        # Расчет оценок качества
        print("🎯 Расчет оценок качества...")
        quality_scores = self.calculate_quality_scores(file_metrics)

        return {
            "analysis_timestamp": "2026-01-06",
            "project_structure": structure,
            "dependencies": dependencies,
            "file_metrics": file_metrics,
            "quality_scores": quality_scores,
            "summary": {
                "total_python_files": len(python_files),
                "analysis_successful": len([f for f in file_metrics if not f.get("analysis_failed", False)]),
                "analysis_failed": len([f for f in file_metrics if f.get("analysis_failed", False)]),
            },
        }


def main():
    """Основная функция анализа"""

    analyzer = CodeQualityAnalyzer()
    report = analyzer.generate_report()

    print("\n" + "=" * 60)
    print("📋 РЕЗУЛЬТАТЫ АНАЛИЗА КАЧЕСТВА КОДА")
    print("=" * 60)

    # Структура проекта
    structure = report["project_structure"]
    print(f"\n🏗️ Структура проекта:")
    print(f"   Всего Python файлов: {structure['total_files']}")
    print(f"   Модули: {list(structure['module_analysis'].keys())}")

    # Зависимости
    deps = report["dependencies"]
    print(f"\n📦 Зависимости:")
    print(f"   Всего импортов: {deps['total_imports']}")
    print(f"   Внешние зависимости: {len(deps['external_dependencies'])}")
    print(f"   Внутренние зависимости: {len(deps['internal_dependencies'])}")

    # Оценки качества
    if "scores" in report["quality_scores"]:
        scores = report["quality_scores"]["scores"]
        metrics = report["quality_scores"]["metrics"]

        print(f"\n🎯 Оценки качества (0-10):")
        print(f"   📚 Документированность: {scores['documentation']}/10")
        print(f"   🧮 Сложность кода: {scores['complexity']}/10")
        print(f"   🎨 Стиль кода: {scores['style']}/10")
        print(f"   🔒 Безопасность: {scores['security']}/10")
        print(f"   🏗️ Архитектура: {scores['architecture']}/10")
        print(f"   🏆 Общая оценка: {scores['overall']}/10")

        print(f"\n📊 Метрики:")
        print(f"   Строк кода: {metrics['total_code_lines']:,}")
        print(f"   Комментариев: {metrics['comment_ratio']}%")
        print(f"   Классов: {metrics['total_classes']}")
        print(f"   Функций: {metrics['total_functions']}")
        print(f"   Проблемы стиля: {metrics['total_style_issues']}")
        print(f"   Критичные проблемы безопасности: {metrics['high_security_issues']}")

        # Общая оценка
        overall = scores["overall"]
        if overall >= 8.0:
            quality_level = "ОТЛИЧНО"
            emoji = "🏆"
        elif overall >= 7.0:
            quality_level = "ХОРОШО"
            emoji = "✅"
        elif overall >= 6.0:
            quality_level = "УДОВЛЕТВОРИТЕЛЬНО"
            emoji = "⚠️"
        else:
            quality_level = "ТРЕБУЕТ УЛУЧШЕНИЯ"
            emoji = "❌"

        print(f"\n{emoji} ОБЩАЯ ОЦЕНКА КАЧЕСТВА КОДА: {quality_level} ({overall}/10)")

    # Сохранение отчета
    with open("code_quality_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n💾 Детальный отчет сохранен в: code_quality_report.json")

    return report["quality_scores"]["scores"]["overall"] >= 6.0 if "scores" in report["quality_scores"] else False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
