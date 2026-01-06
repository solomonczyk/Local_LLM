"""
Unit tests for KnowledgeBaseManager
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_runtime.orchestrator.kb_manager import KnowledgeBaseManager


class TestKnowledgeBaseManager(unittest.TestCase):
    """Test cases for KnowledgeBaseManager"""

    def setUp(self) -> None:
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create mock KB files
        self.kb_dir = Path(self.temp_dir) / "kb"
        self.kb_dir.mkdir()
        
        # Create test KB content
        security_kb = """# Security Checklist

## Authentication
Always use strong authentication mechanisms.

## Authorization  
Implement proper access controls.

## Data Protection
Encrypt sensitive data at rest and in transit.
"""
        
        (self.kb_dir / "security_checklist.md").write_text(security_kb)
        
        # Create KB manager and patch its mapping after initialization
        self.kb_manager = KnowledgeBaseManager(kb_top_k=3, kb_max_chars=1000, cache_size=10)
        
        # Override the kb_mapping with our test paths
        self.kb_manager.kb_mapping = {
            "security": str(self.kb_dir / "security_checklist.md"),
            "architect": str(self.kb_dir / "nonexistent.md"),  # Test missing file
        }
        
        # Reload KB with our test mapping
        self.kb_manager._load_kb()

    def tearDown(self) -> None:
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self) -> None:
        """Test KB manager initialization"""
        self.assertEqual(self.kb_manager.kb_top_k, 3)
        self.assertEqual(self.kb_manager.kb_max_chars, 1000)
        self.assertIsInstance(self.kb_manager.kb_cache, dict)
        self.assertIsInstance(self.kb_manager.kb_version_hash, str)

    def test_kb_loading(self) -> None:
        """Test KB file loading"""
        # Security KB should be loaded
        self.assertIn("security", self.kb_manager.kb_cache)
        self.assertGreater(len(self.kb_manager.kb_cache["security"]), 0)
        
        # Architect KB should be empty (file doesn't exist)
        self.assertIn("architect", self.kb_manager.kb_cache)
        self.assertEqual(len(self.kb_manager.kb_cache["architect"]), 0)

    def test_chunk_kb(self) -> None:
        """Test KB chunking functionality"""
        content = """# Test Document

## Section 1
This is section 1 content.

## Section 2  
This is section 2 content with more details.
"""
        
        chunks = self.kb_manager._chunk_kb(content, "test.md")
        
        self.assertGreater(len(chunks), 0)
        for chunk in chunks:
            self.assertIn("content", chunk)
            self.assertIn("doc", chunk)
            self.assertIn("section", chunk)
            self.assertEqual(chunk["doc"], "test.md")

    def test_ballast_section_detection(self) -> None:
        """Test ballast section detection"""
        self.assertTrue(self.kb_manager._is_ballast_section("Introduction"))
        self.assertTrue(self.kb_manager._is_ballast_section("1. Overview"))
        self.assertTrue(self.kb_manager._is_ballast_section("About"))
        
        self.assertFalse(self.kb_manager._is_ballast_section("Authentication"))
        self.assertFalse(self.kb_manager._is_ballast_section("Implementation Details"))

    def test_cache_functionality(self) -> None:
        """Test LRU cache functionality"""
        # First retrieval should be cache miss
        content1, stats1 = self.kb_manager.retrieve_kb("security", "authentication test")
        self.assertEqual(stats1["kb_cache"], "MISS")
        
        # Second retrieval should be cache hit
        content2, stats2 = self.kb_manager.retrieve_kb("security", "authentication test")
        self.assertEqual(stats2["kb_cache"], "HIT")
        self.assertEqual(content1, content2)

    def test_retrieve_kb_with_limits(self) -> None:
        """Test KB retrieval with character limits"""
        content, stats = self.kb_manager.retrieve_kb("security", "authentication")
        
        self.assertIsInstance(content, str)
        self.assertLessEqual(stats["chars_used"], self.kb_manager.kb_max_chars)
        self.assertLessEqual(stats["chunks_used"], self.kb_manager.kb_top_k)
        self.assertIn("sources", stats)

    def test_retrieve_kb_nonexistent_agent(self) -> None:
        """Test KB retrieval for non-existent agent"""
        content, stats = self.kb_manager.retrieve_kb("nonexistent", "test query")
        
        self.assertEqual(content, "")
        self.assertEqual(stats["chunks_used"], 0)
        self.assertEqual(stats["chars_used"], 0)

    def test_cache_key_generation(self) -> None:
        """Test cache key generation"""
        key1 = self.kb_manager._get_cache_key("security", "test query")
        key2 = self.kb_manager._get_cache_key("security", "test query")
        key3 = self.kb_manager._get_cache_key("security", "different query")
        
        self.assertEqual(key1, key2)  # Same query should generate same key
        self.assertNotEqual(key1, key3)  # Different query should generate different key

    def test_query_normalization(self) -> None:
        """Test query normalization"""
        normalized1 = self.kb_manager._normalize_query("  Test   Query  ")
        normalized2 = self.kb_manager._normalize_query("test query")
        
        self.assertEqual(normalized1, normalized2)
        self.assertEqual(normalized1, "test query")

    def test_cache_stats(self) -> None:
        """Test cache statistics"""
        # Generate some cache activity
        self.kb_manager.retrieve_kb("security", "test1")
        self.kb_manager.retrieve_kb("security", "test1")  # Cache hit
        self.kb_manager.retrieve_kb("security", "test2")  # Cache miss
        
        stats = self.kb_manager.get_cache_stats()
        
        self.assertIn("retrieval_cache", stats)
        self.assertIn("kb_version_hash", stats)
        self.assertIn("kb_loaded", stats)
        
        cache_stats = stats["retrieval_cache"]
        self.assertGreater(cache_stats["hits"], 0)
        self.assertGreater(cache_stats["misses"], 0)
        self.assertGreaterEqual(cache_stats["hit_rate"], 0)

    def test_ballast_limiting(self) -> None:
        """Test that ballast sections are limited"""
        # Create content with multiple ballast sections
        content_with_ballast = """# Test Document

## Introduction
This is an introduction.

## Overview  
This is an overview.

## About
This is about section.

## Implementation
This is implementation details.
"""
        
        chunks = self.kb_manager._chunk_kb(content_with_ballast, "test.md")
        
        # Mock the KB cache for this test
        original_cache = self.kb_manager.kb_cache.copy()
        self.kb_manager.kb_cache["test_agent"] = chunks
        
        try:
            content, stats = self.kb_manager.retrieve_kb("test_agent", "test query")
            
            # Should have at most 1 ballast section
            self.assertLessEqual(stats.get("ballast_used", 0), 1)
            
        finally:
            # Restore original cache
            self.kb_manager.kb_cache = original_cache


if __name__ == "__main__":
    unittest.main()