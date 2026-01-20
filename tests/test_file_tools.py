"""
Unit tests for FileTools class
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_system.file_tools import FileTools

class TestFileTools(unittest.TestCase):
    """Test cases for FileTools"""

    def setUp(self) -> None:
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock SecurityConfig.WORKSPACE_ROOT to use temp directory
        self.workspace_patcher = patch('agent_system.file_tools.SecurityConfig.WORKSPACE_ROOT', Path(self.temp_dir))
        self.workspace_patcher.start()
        
        # Mock SecurityConfig.is_path_safe to allow temp directory paths
        def mock_is_path_safe(path):
            try:
                path.relative_to(Path(self.temp_dir))
                return True
            except ValueError:
                return False
        
        self.path_safe_patcher = patch('agent_system.file_tools.SecurityConfig.is_path_safe', side_effect=mock_is_path_safe)
        self.path_safe_patcher.start()
        
        # Mock SecurityConfig.MAX_FILE_SIZE
        self.max_file_size_patcher = patch('agent_system.file_tools.SecurityConfig.MAX_FILE_SIZE', 10 * 1024 * 1024)
        self.max_file_size_patcher.start()
        
        self.file_tools = FileTools("test_agent")

    def tearDown(self) -> None:
        """Clean up test fixtures"""
        # Stop all patchers
        self.workspace_patcher.stop()
        self.path_safe_patcher.stop()
        self.max_file_size_patcher.stop()
        
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_file_success(self) -> None:
        """Test successful file reading"""
        # Create test file
        test_file = Path(self.temp_dir) / "test.txt"
        test_content = "Hello, World!"
        test_file.write_text(test_content, encoding="utf-8")
        
        # Test reading
        result = self.file_tools.read_file("test.txt")
        
        self.assertTrue(result["success"])
        self.assertEqual(result["content"], test_content)
        self.assertIn("test.txt", result["path"])

    def test_read_file_normalizes_backslash(self) -> None:
        """Test reading with Windows-style backslashes"""
        nested_dir = Path(self.temp_dir) / "nested"
        nested_dir.mkdir(parents=True, exist_ok=True)
        test_file = nested_dir / "note.txt"
        test_content = "Backslash path"
        test_file.write_text(test_content, encoding="utf-8")

        result = self.file_tools.read_file("nested\\note.txt")

        self.assertTrue(result["success"])
        self.assertEqual(result["content"], test_content)

    def test_read_file_not_found(self) -> None:
        """Test reading non-existent file"""
        result = self.file_tools.read_file("nonexistent.txt")
        
        self.assertFalse(result["success"])
        self.assertIn("File not found", result["error"])

    def test_write_file_success(self) -> None:
        """Test successful file writing"""
        test_content = "Test content"
        
        with patch('agent_system.file_tools.AgentConfig.CURRENT_ACCESS_LEVEL', 3), \
             patch('agent_system.file_tools.AgentConfig.ACCESS_LEVEL_SAFE_WRITE', 3):
            result = self.file_tools.write_file("new_file.txt", test_content)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["size"], len(test_content))
        
        # Verify file was created
        test_file = Path(self.temp_dir) / "new_file.txt"
        self.assertTrue(test_file.exists())
        self.assertEqual(test_file.read_text(encoding="utf-8"), test_content)

    def test_write_file_dry_run(self) -> None:
        """Test write dry-run preview without file creation"""
        test_content = "Dry run content"
        target = Path(self.temp_dir) / "dry_run.txt"

        with patch('agent_system.file_tools.AgentConfig.CURRENT_ACCESS_LEVEL', 3), \
             patch('agent_system.file_tools.AgentConfig.ACCESS_LEVEL_SAFE_WRITE', 3):
            result = self.file_tools.write_file("dry_run.txt", test_content, dry_run=True)

        self.assertTrue(result["success"])
        self.assertTrue(result["dry_run"])
        self.assertFalse(target.exists())
        self.assertIn("diff", result)

    def test_write_file_permission_denied(self) -> None:
        """Test writing with insufficient permissions"""
        # Mock AgentConfig.ACCESS_LEVEL_SAFE_WRITE to be higher than current level
        with patch('agent_system.file_tools.AgentConfig.CURRENT_ACCESS_LEVEL', 1), \
             patch('agent_system.file_tools.AgentConfig.ACCESS_LEVEL_SAFE_WRITE', 3):
            result = self.file_tools.write_file("test.txt", "content")
        
        self.assertFalse(result["success"])
        self.assertIn("Write access denied", result["error"])

    def test_delete_file_success(self) -> None:
        """Test successful file deletion"""
        # Create test file
        test_file = Path(self.temp_dir) / "to_delete.txt"
        test_file.write_text("Delete me", encoding="utf-8")
        
        with patch('agent_system.file_tools.AgentConfig.CURRENT_ACCESS_LEVEL', 3), \
             patch('agent_system.file_tools.AgentConfig.ACCESS_LEVEL_SAFE_WRITE', 3):
            result = self.file_tools.delete_file("to_delete.txt")
        
        self.assertTrue(result["success"])
        self.assertFalse(test_file.exists())
        
        # Check backup was created
        backup_file = Path(self.temp_dir) / "to_delete.txt.deleted_backup"
        self.assertTrue(backup_file.exists())

    def test_delete_file_dry_run(self) -> None:
        """Test delete dry-run preview without file deletion"""
        test_file = Path(self.temp_dir) / "delete_dry.txt"
        test_file.write_text("Delete me", encoding="utf-8")

        with patch('agent_system.file_tools.AgentConfig.CURRENT_ACCESS_LEVEL', 3), \
             patch('agent_system.file_tools.AgentConfig.ACCESS_LEVEL_SAFE_WRITE', 3):
            result = self.file_tools.delete_file("delete_dry.txt", dry_run=True)

        self.assertTrue(result["success"])
        self.assertTrue(result["dry_run"])
        self.assertTrue(test_file.exists())
        self.assertIn("preview", result)

    def test_edit_file_success(self) -> None:
        """Test successful file editing"""
        # Create test file
        test_file = Path(self.temp_dir) / "edit_test.txt"
        original_content = "Hello World"
        test_file.write_text(original_content, encoding="utf-8")
        
        with patch('agent_system.file_tools.AgentConfig.CURRENT_ACCESS_LEVEL', 3), \
             patch('agent_system.file_tools.AgentConfig.ACCESS_LEVEL_SAFE_WRITE', 3):
            result = self.file_tools.edit_file("edit_test.txt", "World", "Universe")
        
        self.assertTrue(result["success"])
        
        # Verify content was changed
        new_content = test_file.read_text(encoding="utf-8")
        self.assertEqual(new_content, "Hello Universe")
        
        # Check backup was created
        backup_file = Path(self.temp_dir) / "edit_test.txt.backup"
        self.assertTrue(backup_file.exists())

    def test_edit_file_dry_run(self) -> None:
        """Test edit dry-run preview without file modification"""
        test_file = Path(self.temp_dir) / "edit_dry.txt"
        original_content = "Hello World"
        test_file.write_text(original_content, encoding="utf-8")

        with patch('agent_system.file_tools.AgentConfig.CURRENT_ACCESS_LEVEL', 3), \
             patch('agent_system.file_tools.AgentConfig.ACCESS_LEVEL_SAFE_WRITE', 3):
            result = self.file_tools.edit_file("edit_dry.txt", "World", "Universe", dry_run=True)

        self.assertTrue(result["success"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(test_file.read_text(encoding="utf-8"), original_content)
        self.assertIn("diff", result)

    def test_list_dir_success(self) -> None:
        """Test successful directory listing"""
        # Create test files
        (Path(self.temp_dir) / "file1.txt").write_text("content1")
        (Path(self.temp_dir) / "file2.py").write_text("content2")
        (Path(self.temp_dir) / "subdir").mkdir()
        
        result = self.file_tools.list_dir(".")
        
        self.assertTrue(result["success"])
        self.assertEqual(len(result["files"]), 3)
        
        # Check file info
        file_names = [f["name"] for f in result["files"]]
        self.assertIn("file1.txt", file_names)
        self.assertIn("file2.py", file_names)
        self.assertIn("subdir", file_names)

    def test_search_files(self) -> None:
        """Test file search functionality"""
        # Create test files with content
        (Path(self.temp_dir) / "test1.py").write_text("def hello(): pass")
        (Path(self.temp_dir) / "test2.py").write_text("def world(): pass")
        (Path(self.temp_dir) / "test3.txt").write_text("hello world")
        
        result = self.file_tools.search("hello", ["**/*.py", "**/*.txt"])
        
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)  # test1.py and test3.txt
        
        found_files = result["files"]
        self.assertIn("test1.py", found_files)
        self.assertIn("test3.txt", found_files)

if __name__ == "__main__":
    unittest.main()
