"""
Knowledge Base Manager для консилиума агентов
"""
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

class KnowledgeBaseManager:
    """
    Управление Knowledge Base для агентов консилиума.
    
    Этот класс отвечает за:
    - Загрузку и кэширование KB файлов
    - Разбиение контента на чанки с метаданными
    - Интеллектуальный retrieval с лимитами
    - LRU кэширование для оптимизации производительности
    - Анти-балласт фильтрацию (ограничение введений/обзоров)
    
    Attributes:
        kb_top_k: Максимальное количество чанков для retrieval
        kb_max_chars: Максимальное количество символов в ответе
        kb_cache: Кэш загруженных и обработанных KB файлов
        kb_version_hash: Хэш версии KB для инвалидации кэша
        
    Example:
        >>> kb_manager = KnowledgeBaseManager(kb_top_k=5, kb_max_chars=4000)
        >>> content, stats = kb_manager.retrieve_kb("security", "JWT authentication")
        >>> print(f"Retrieved {stats['chunks_used']} chunks, {stats['chars_used']} chars")
    """

    # Балластные секции (максимум 1 в выдаче)
    BALLAST_SECTIONS = {"introduction", "scope", "overview", "about", "preface"}

    def __init__(self, kb_top_k: int = 5, kb_max_chars: int = 4000, cache_size: int = 100):
        self.kb_top_k = kb_top_k
        self.kb_max_chars = kb_max_chars

        # Маппинг агентов к их KB файлам
        self.kb_mapping = {
            "security": "agent_runtime/kb/security_checklist.md",
            "architect": "agent_runtime/kb/architecture_review.md",
            "qa": "agent_runtime/kb/testing_strategy.md",
            "dev": "agent_runtime/kb/development_guide.md",
            "seo": "agent_runtime/kb/seo_guide.md",
            "ux": "agent_runtime/kb/ux_guide.md",
            "director": "agent_runtime/kb/architectural_programming.md",
        }

        # Кэш загруженных KB и версия
        self.kb_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.kb_version_hash: str = ""

        # LRU кэш для retrieval результатов
        self._retrieval_cache: Dict[str, Tuple[str, dict]] = {}
        self._retrieval_cache_order: List[str] = []  # Для LRU
        self._retrieval_cache_size = cache_size
        self._cache_hits = 0
        self._cache_misses = 0

        self._load_kb()

    def _load_kb(self):
        """Загрузить KB файлы в кэш (разбитые на чанки с метаданными)"""
        # Собираем контент для хэширования
        all_content = []

        for agent_name, kb_path in self.kb_mapping.items():
            try:
                kb_file = Path(kb_path)
                if kb_file.exists():
                    content = kb_file.read_text(encoding="utf-8")
                    all_content.append(f"{kb_path}:{content}")
                    doc_name = kb_file.name
                    # Разбиваем на чанки по секциям с метаданными
                    self.kb_cache[agent_name] = self._chunk_kb(content, doc_name)
                    total_chars = sum(len(c["content"]) for c in self.kb_cache[agent_name])
                    print(
                        f"[OK] KB loaded for {agent_name}: {len(self.kb_cache[agent_name])} chunks, {total_chars} chars"
                    )
                else:
                    print(f"[WARN] KB not found for {agent_name}: {kb_path}")
                    self.kb_cache[agent_name] = []
            except Exception as e:
                print(f"[ERROR] Error loading KB for {agent_name}: {e}")
                self.kb_cache[agent_name] = []

        # Вычисляем хэш всех KB файлов (первые 8 символов)
        combined = "\n".join(sorted(all_content))
        self.kb_version_hash = hashlib.sha256(combined.encode()).hexdigest()[:8]
        print(f"[*] KB version: {self.kb_version_hash}")

    def _chunk_kb(self, content: str, doc_name: str) -> List[Dict[str, Any]]:
        """Разбить KB на чанки по секциям markdown с метаданными"""
        import re

        # Разбиваем по ## заголовкам
        sections = re.split(r"\n(?=##\s)", content)
        chunks = []

        for section in sections:
            section = section.strip()
            if not section:
                continue

            # Извлекаем заголовок секции
            title_match = re.match(r"^##\s+(.+?)(?:\n|$)", section)
            section_title = title_match.group(1).strip() if title_match else "Introduction"

            # Если секция слишком большая, разбиваем по параграфам
            if len(section) > 2000:
                paragraphs = section.split("\n\n")
                current_chunk = ""
                chunk_idx = 0
                for para in paragraphs:
                    if len(current_chunk) + len(para) < 1500:
                        current_chunk += para + "\n\n"
                    else:
                        if current_chunk:
                            chunks.append(
                                {
                                    "content": current_chunk.strip(),
                                    "doc": doc_name,
                                    "section": f"{section_title} (part {chunk_idx + 1})",
                                }
                            )
                            chunk_idx += 1
                        current_chunk = para + "\n\n"
                if current_chunk:
                    chunks.append(
                        {
                            "content": current_chunk.strip(),
                            "doc": doc_name,
                            "section": (f"{section_title} (part {chunk_idx + 1})" if chunk_idx > 0 else section_title),
                        }
                    )
            else:
                chunks.append({"content": section, "doc": doc_name, "section": section_title})

        # Fallback если ничего не нашли
        if not chunks:
            chunks.append({"content": content[:2000], "doc": doc_name, "section": "Full document"})

        return chunks

    def _is_ballast_section(self, section_title: str) -> bool:
        """Проверить является ли секция балластной"""
        # Нормализуем: убираем номера, скобки, приводим к lowercase

        normalized = re.sub(r"^[\d\)\.\-\s]+", "", section_title)  # убираем "0) ", "1. " и т.д.
        normalized = normalized.lower().split("(")[0].strip()
        return normalized in self.BALLAST_SECTIONS

    def _normalize_query(self, query: str) -> str:
        """Нормализовать запрос для ключа кэша"""
        # Простая нормализация: lowercase, убираем лишние пробелы
        return " ".join(query.lower().split())

    def _get_cache_key(self, agent_name: str, task: str) -> str:
        """Сформировать ключ кэша"""
        normalized = self._normalize_query(task)
        query_hash = hashlib.md5(normalized.encode()).hexdigest()[:8]
        return f"{agent_name}:{query_hash}:{self.kb_version_hash}:{self.kb_top_k}:{self.kb_max_chars}"

    def _cache_get(self, key: str) -> Optional[Tuple[str, dict]]:
        """Получить из кэша (LRU)"""
        if key in self._retrieval_cache:
            # Перемещаем в конец (most recently used)
            self._retrieval_cache_order.remove(key)
            self._retrieval_cache_order.append(key)
            self._cache_hits += 1
            return self._retrieval_cache[key]
        self._cache_misses += 1
        return None

    def _cache_put(self, key: str, value: Tuple[str, dict]):
        """Положить в кэш (LRU eviction)"""
        if key in self._retrieval_cache:
            self._retrieval_cache_order.remove(key)
        elif len(self._retrieval_cache) >= self._retrieval_cache_size:
            # Удаляем oldest
            oldest = self._retrieval_cache_order.pop(0)
            del self._retrieval_cache[oldest]

        self._retrieval_cache[key] = value
        self._retrieval_cache_order.append(key)

    def retrieve_kb(self, agent_name: str, task: str) -> Tuple[str, dict]:
        """
        Получить релевантные чанки KB с учётом лимитов и анти-балласт правила.
        Использует LRU кэш для ускорения повторных запросов.

        Возвращает (kb_content, stats) где stats включает sources и cache status
        """
        # Проверяем кэш
        cache_key = self._get_cache_key(agent_name, task)
        cached = self._cache_get(cache_key)
        if cached is not None:
            content, stats = cached
            stats = stats.copy()
            stats["kb_cache"] = "HIT"
            print(f"  [CACHE] {agent_name}: kb_cache=HIT")
            return content, stats

        # Cache MISS - выполняем retrieval
        if agent_name not in self.kb_cache or not self.kb_cache[agent_name]:
            stats = {"chunks_used": 0, "chars_used": 0, "total_chunks": 0, "sources": [], "kb_cache": "MISS"}
            return "", stats

        chunks = self.kb_cache[agent_name]

        # Разделяем чанки на балластные и полезные
        ballast_chunks = []
        useful_chunks = []

        for chunk in chunks:
            if self._is_ballast_section(chunk["section"]):
                ballast_chunks.append(chunk)
            else:
                useful_chunks.append(chunk)

        # Собираем итоговый список: сначала полезные, потом максимум 1 балластный
        prioritized = useful_chunks[: self.kb_top_k]

        # Добавляем 1 балластный если есть место и он есть
        if len(prioritized) < self.kb_top_k and ballast_chunks:
            prioritized.append(ballast_chunks[0])

        # Теперь применяем лимиты
        selected_content = []
        sources = []
        chars_used = 0
        ballast_used = 0

        for chunk in prioritized[: self.kb_top_k]:
            content = chunk["content"]
            is_ballast = self._is_ballast_section(chunk["section"])

            if chars_used + len(content) <= self.kb_max_chars:
                selected_content.append(content)
                sources.append({"doc": chunk["doc"], "section": chunk["section"], "ballast": is_ballast})
                chars_used += len(content)
                if is_ballast:
                    ballast_used += 1
            else:
                # Обрезаем последний чанк если нужно
                remaining = self.kb_max_chars - chars_used
                if remaining > 200:
                    selected_content.append(content[:remaining] + "...")
                    sources.append(
                        {"doc": chunk["doc"], "section": chunk["section"] + " (truncated)", "ballast": is_ballast}
                    )
                    chars_used += remaining
                break

        result_content = "\n\n---\n\n".join(selected_content)
        stats = {
            "chunks_used": len(selected_content),
            "chars_used": chars_used,
            "total_chunks": len(chunks),
            "ballast_used": ballast_used,
            "limit_top_k": self.kb_top_k,
            "limit_max_chars": self.kb_max_chars,
            "sources": sources,
        }

        # Сохраняем в кэш
        self._cache_put(cache_key, (result_content, stats))
        stats = stats.copy()
        stats["kb_cache"] = "MISS"
        print(f"  [CACHE] {agent_name}: kb_cache=MISS")

        return result_content, stats

    def get_cache_stats(self) -> Dict[str, Any]:
        """Получить статистику кэша"""
        total_cache_requests = self._cache_hits + self._cache_misses
        hit_rate = round(self._cache_hits / total_cache_requests, 2) if total_cache_requests > 0 else 0

        return {
            "kb_version_hash": self.kb_version_hash,
            "retrieval_cache": {
                "size": len(self._retrieval_cache),
                "max_size": self._retrieval_cache_size,
                "hits": self._cache_hits,
                "misses": self._cache_misses,
                "hit_rate": hit_rate,
            },
            "kb_loaded": {name: bool(kb) for name, kb in self.kb_cache.items()},
        }
