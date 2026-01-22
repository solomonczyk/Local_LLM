"""
Tool implementations с безопасностью - главный класс
"""
from typing import Any, Dict, List

from .code_analysis_tools import CodeAnalysisTools
from .file_tools import FileTools
from .system_tools import SystemTools

class ToolExecutor:
    """Безопасное выполнение инструментов - объединяет все типы операций"""

    def __init__(self, agent_name: str = "system"):
        self.agent_name = agent_name
        
        # Инициализируем специализированные инструменты
        self.file_tools = FileTools(agent_name)
        self.system_tools = SystemTools(agent_name)
        self.code_analysis_tools = CodeAnalysisTools(agent_name)

    # === File Operations ===
    def read_file(self, path: str) -> Dict[str, Any]:
        """Чтение файла"""
        return self.file_tools.read_file(path)

    def write_file(
        self,
        path: str,
        content: str,
        mode: str = "overwrite",
        dry_run: bool = False,
        expected_sha256: str = None,
        expected_exists: bool = None,
    ) -> Dict[str, Any]:
        """Запись файла"""
        return self.file_tools.write_file(path, content, mode, dry_run, expected_sha256, expected_exists)

    def delete_file(
        self,
        path: str,
        dry_run: bool = False,
        expected_sha256: str = None,
        expected_exists: bool = None,
    ) -> Dict[str, Any]:
        """Удаление файла"""
        return self.file_tools.delete_file(path, dry_run, expected_sha256, expected_exists)

    def edit_file(
        self,
        path: str,
        old_text: str,
        new_text: str,
        dry_run: bool = False,
        expected_sha256: str = None,
        expected_exists: bool = None,
    ) -> Dict[str, Any]:
        """Редактирование части файла (замена текста)"""
        return self.file_tools.edit_file(path, old_text, new_text, dry_run, expected_sha256, expected_exists)

    def copy_file(
        self,
        source_path: str,
        dest_path: str,
        dry_run: bool = False,
        expected_source_sha256: str = None,
        expected_dest_sha256: str = None,
        expected_source_exists: bool = None,
        expected_dest_exists: bool = None,
    ) -> Dict[str, Any]:
        """Копирование файла"""
        return self.file_tools.copy_file(
            source_path,
            dest_path,
            dry_run,
            expected_source_sha256,
            expected_dest_sha256,
            expected_source_exists,
            expected_dest_exists,
        )

    def move_file(
        self,
        source_path: str,
        dest_path: str,
        dry_run: bool = False,
        expected_source_sha256: str = None,
        expected_dest_sha256: str = None,
        expected_source_exists: bool = None,
        expected_dest_exists: bool = None,
    ) -> Dict[str, Any]:
        """Перемещение/переименование файла"""
        return self.file_tools.move_file(
            source_path,
            dest_path,
            dry_run,
            expected_source_sha256,
            expected_dest_sha256,
            expected_source_exists,
            expected_dest_exists,
        )

    def list_dir(self, path: str = ".", pattern: str = "*") -> Dict[str, Any]:
        """Список файлов в директории"""
        return self.file_tools.list_dir(path, pattern)

    def search(self, query: str, globs: List[str] = None, max_results: int = None, max_files: int = None) -> Dict[str, Any]:
        """????? ? ??????"""
        return self.file_tools.search(query, globs, max_results, max_files)

    # === System Operations ===
    def git(self, cmd: str) -> Dict[str, Any]:
        """Выполнение git команд"""
        return self.system_tools.git(cmd)

    def shell(self, command: str) -> Dict[str, Any]:
        """Выполнение shell команд (ограниченно)"""
        return self.system_tools.shell(command)

    def system_info(self, info_type: str = "disks") -> Dict[str, Any]:
        """Получение системной информации"""
        return self.system_tools.system_info(info_type)

    def network_info(self) -> Dict[str, Any]:
        """Получение сетевой информации"""
        return self.system_tools.network_info()

    def run_tests(self, test_path: str = "tests/") -> Dict[str, Any]:
        """Запуск тестов"""
        return self.system_tools.run_tests(test_path)

    def create_project_structure(self, project_type: str = "python") -> Dict[str, Any]:
        """Создание структуры проекта"""
        return self.system_tools.create_project_structure(project_type)

    # === Code Analysis ===
    def analyze_code(self, path: str) -> Dict[str, Any]:
        """Анализ кода (синтаксис, стиль, сложность)"""
        return self.code_analysis_tools.analyze_code(path)
