"""
Проактивное поведение агента - инициатива и предложения
"""
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .conversation import conversation_manager


class ProactiveAgent:
    """Агент с проактивным поведением"""

    def __init__(self):
        self.suggestion_patterns = {
            # Паттерны для определения намерений
            "file_creation": [r"создай|напиши|сделай.*файл", r"нужен.*файл", r"можешь.*создать"],
            "code_review": [r"проверь|посмотри.*код", r"есть.*ошибк", r"работает.*правильно"],
            "project_setup": [r"новый.*проект", r"начать.*разработку", r"структура.*проект"],
            "debugging": [r"не.*работает", r"ошибка", r"проблема.*с"],
            "optimization": [r"медленно", r"оптимизир", r"ускорить"],
        }

    def analyze_intent(self, message: str) -> Dict[str, Any]:
        """Анализ намерений пользователя"""
        message_lower = message.lower()
        detected_intents = []

        for intent, patterns in self.suggestion_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    detected_intents.append(intent)
                    break

        return {
            "intents": detected_intents,
            "confidence": len(detected_intents) / len(self.suggestion_patterns),
            "message_type": self._classify_message_type(message),
        }

    def _classify_message_type(self, message: str) -> str:
        """Классификация типа сообщения"""
        message_lower = message.lower()

        if any(word in message_lower for word in ["?", "как", "что", "где", "когда", "почему"]):
            return "question"
        elif any(word in message_lower for word in ["создай", "сделай", "напиши", "удали"]):
            return "command"
        elif any(word in message_lower for word in ["спасибо", "отлично", "хорошо", "понятно"]):
            return "acknowledgment"
        else:
            return "statement"

    def generate_suggestions(self, session_id: str, user_message: str) -> List[str]:
        """Генерация проактивных предложений"""
        context = conversation_manager.get_or_create_context(session_id)
        intent_analysis = self.analyze_intent(user_message)
        suggestions = []

        # Анализ текущего состояния проекта
        current_files = self._analyze_current_directory()

        # Предложения на основе намерений
        for intent in intent_analysis["intents"]:
            suggestions.extend(self._get_intent_suggestions(intent, current_files, context))

        # Предложения на основе контекста
        suggestions.extend(self._get_context_suggestions(context, current_files))

        # Удаляем дубликаты и ограничиваем количество
        unique_suggestions = list(dict.fromkeys(suggestions))
        return unique_suggestions[:3]  # Максимум 3 предложения

    def _analyze_current_directory(self) -> Dict[str, Any]:
        """Анализ текущей директории"""
        current_dir = Path(".")
        files = list(current_dir.glob("*"))

        analysis = {
            "total_files": len([f for f in files if f.is_file()]),
            "directories": len([f for f in files if f.is_dir()]),
            "python_files": len(list(current_dir.glob("*.py"))),
            "config_files": len(
                list(current_dir.glob("*.json")) + list(current_dir.glob("*.yaml")) + list(current_dir.glob("*.yml"))
            ),
            "has_git": (current_dir / ".git").exists(),
            "has_readme": any((current_dir / name).exists() for name in ["README.md", "readme.md", "README.txt"]),
            "has_requirements": (current_dir / "requirements.txt").exists(),
            "has_package_json": (current_dir / "package.json").exists(),
            "recent_files": sorted([f for f in files if f.is_file()], key=lambda x: x.stat().st_mtime, reverse=True)[
                :5
            ],
        }

        return analysis

    def _get_intent_suggestions(self, intent: str, current_files: Dict[str, Any], context) -> List[str]:
        """Предложения на основе намерений"""
        suggestions = []

        if intent == "file_creation":
            if current_files["python_files"] == 0:
                suggestions.append("💡 Создать основной Python файл (main.py)?")
            if not current_files["has_readme"]:
                suggestions.append("📝 Создать README.md для документации проекта?")
            if current_files["python_files"] > 0 and not current_files["has_requirements"]:
                suggestions.append("📦 Создать requirements.txt для зависимостей?")

        elif intent == "project_setup":
            suggestions.extend(
                [
                    "🏗️ Создать структуру проекта с папками src/, tests/, docs/?",
                    "⚙️ Настроить Git репозиторий и .gitignore?",
                    "🐍 Создать виртуальное окружение Python?",
                ]
            )

        elif intent == "code_review":
            if current_files["python_files"] > 0:
                suggestions.append("🔍 Проверить Python код на соответствие PEP8?")
            suggestions.append("🧪 Запустить тесты для проверки функциональности?")

        elif intent == "debugging":
            suggestions.extend(
                [
                    "🐛 Проверить логи на наличие ошибок?",
                    "🔧 Запустить диагностику системы?",
                    "📊 Проанализировать производительность?",
                ]
            )

        return suggestions

    def _get_context_suggestions(self, context, current_files: Dict[str, Any]) -> List[str]:
        """Предложения на основе контекста"""
        suggestions = []

        # Если долго не было активности
        if context.messages and (context.last_activity < (context.messages[-1].timestamp - 300)):  # 5 минут
            suggestions.append("⏰ Продолжим работу с того места, где остановились?")

        # Если есть активные файлы
        if context.active_files:
            suggestions.append(f"📄 Продолжить работу с файлом {context.active_files[-1]}?")

        # Если много файлов, но нет структуры
        if current_files["total_files"] > 10 and current_files["directories"] < 3:
            suggestions.append("📁 Организовать файлы по папкам для лучшей структуры?")

        # Если есть Git, но нет коммитов недавно
        if current_files["has_git"]:
            suggestions.append("💾 Сохранить изменения в Git коммите?")

        return suggestions

    def generate_clarifying_questions(self, user_message: str) -> List[str]:
        """Генерация уточняющих вопросов"""
        message_lower = user_message.lower()
        questions = []

        # Вопросы для неясных запросов
        if len(user_message.split()) < 3:
            questions.append("🤔 Можете уточнить, что именно вы хотите сделать?")

        # Вопросы для технических задач
        if any(word in message_lower for word in ["создай", "сделай", "напиши"]):
            if "файл" in message_lower and not any(ext in message_lower for ext in [".py", ".js", ".html", ".css"]):
                questions.append("📝 Какой тип файла создать? (.py, .js, .html, .md)")

            if "проект" in message_lower:
                questions.append("🏗️ Какой тип проекта? (веб-приложение, API, скрипт, библиотека)")

        # Вопросы для проблем
        if any(word in message_lower for word in ["не работает", "ошибка", "проблема"]):
            questions.extend(["🔍 Какую именно ошибку вы видите?", "📋 В каком файле или функции возникла проблема?"])

        return questions[:2]  # Максимум 2 вопроса

    def should_be_proactive(self, session_id: str, user_message: str) -> bool:
        """Определить, нужно ли быть проактивным"""
        context = conversation_manager.get_or_create_context(session_id)

        # Быть проактивным если:
        # 1. Первое сообщение в сессии
        if len(context.messages) <= 1:
            return True

        # 2. Пользователь задает общий вопрос
        if any(word in user_message.lower() for word in ["что", "как", "помоги", "не знаю"]):
            return True

        # 3. Пользователь выражает неуверенность
        if any(phrase in user_message.lower() for phrase in ["не уверен", "может быть", "наверное"]):
            return True

        return False


# Глобальный проактивный агент
proactive_agent = ProactiveAgent()
