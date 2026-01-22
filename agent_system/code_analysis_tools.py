"""
Code analysis tools с безопасностью
"""
import re
from typing import Any, Dict

from .audit import audit_logger
from .config import SecurityConfig


class CodeAnalysisTools:
    """Инструменты для анализа кода"""

    def __init__(self, agent_name: str = "system"):
        self.agent_name = agent_name
        self.workspace = SecurityConfig.WORKSPACE_ROOT

    def analyze_code(self, path: str) -> Dict[str, Any]:
        """Анализ кода (синтаксис, стиль, сложность)"""
        try:
            file_path = (self.workspace / path).resolve()

            if not SecurityConfig.is_path_safe(file_path):
                raise PermissionError(f"Path outside workspace: {path}")

            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {path}")

            content = file_path.read_text(encoding="utf-8")

            analysis = {
                "file_info": {
                    "path": str(file_path),
                    "size": len(content),
                    "lines": len(content.splitlines()),
                    "extension": file_path.suffix,
                },
                "syntax_check": self._check_syntax(content, file_path.suffix),
                "style_check": self._check_style(content, file_path.suffix),
                "complexity": self._analyze_complexity(content, file_path.suffix),
                "security": self._check_security_issues(content, file_path.suffix),
            }

            audit_logger.log_action(
                agent=self.agent_name,
                action="analyze_code",
                params={"path": path},
                result=f"Analyzed {analysis['file_info']['lines']} lines",
                success=True,
            )

            return {"success": True, **analysis}

        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="analyze_code",
                params={"path": path},
                result=None,
                success=False,
                error=str(e),
            )
            return {"success": False, "error": str(e)}

    def _check_syntax(self, content: str, extension: str) -> Dict[str, Any]:
        """Проверка синтаксиса"""
        if extension == ".py":
            try:
                import ast

                ast.parse(content)
                return {"valid": True, "errors": []}
            except SyntaxError as e:
                return {"valid": False, "errors": [f"Line {e.lineno}: {e.msg}"]}

        return {"valid": True, "errors": [], "note": f"Syntax check not implemented for {extension}"}

    def _check_style(self, content: str, extension: str) -> Dict[str, Any]:
        """Проверка стиля кода"""
        issues = []

        if extension == ".py":
            lines = content.splitlines()
            for i, line in enumerate(lines, 1):
                # Проверка длины строки
                if len(line) > 120:
                    issues.append(f"Line {i}: Line too long ({len(line)} > 120)")

                # Проверка trailing whitespace
                if line.endswith(" ") or line.endswith("\t"):
                    issues.append(f"Line {i}: Trailing whitespace")

                # Проверка импортов
                if line.strip().startswith("import ") and "," in line:
                    issues.append(f"Line {i}: Multiple imports on one line")

        return {"issues_count": len(issues), "issues": issues[:10]}  # Первые 10 проблем

    def _analyze_complexity(self, content: str, extension: str) -> Dict[str, Any]:
        """Анализ сложности кода"""
        if extension == ".py":
            lines = content.splitlines()

            # Подсчет функций и классов
            functions = len([line for line in lines if line.strip().startswith("def ")])
            classes = len([line for line in lines if line.strip().startswith("class ")])

            # Подсчет уровня вложенности
            max_indent = 0
            for line in lines:
                if line.strip():
                    indent = len(line) - len(line.lstrip())
                    max_indent = max(max_indent, indent // 4)

            return {
                "functions": functions,
                "classes": classes,
                "max_nesting_level": max_indent,
                "complexity_score": functions + classes + max_indent,
            }

        return {"note": f"Complexity analysis not implemented for {extension}"}

    def _check_security_issues(self, content: str, extension: str) -> Dict[str, Any]:
        """Проверка проблем безопасности"""
        issues = []

        # Общие проблемы безопасности
        security_patterns = [
            (r"password\s*=\s*[\"'][^\"']+[\"']", "Hardcoded password"),
            (r"api_key\s*=\s*[\"'][^\"']+[\"']", "Hardcoded API key"),
            (r"secret\s*=\s*[\"'][^\"']+[\"']", "Hardcoded secret"),
            (r"eval\s*\(", "Use of eval() function"),
            (r"exec\s*\(", "Use of exec() function"),
        ]

        if extension == ".py":
            security_patterns.extend(
                [
                    (r"subprocess\.call\([^)]*shell=True", "Shell injection risk"),
                    (r"os\.system\(", "OS command injection risk"),
                ]
            )

        for pattern, description in security_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = content[: match.start()].count("\n") + 1
                issues.append(f"Line {line_num}: {description}")

        return {"issues_count": len(issues), "issues": issues}
