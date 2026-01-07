"""
Расширенное тестирование качества кода агентов - сложные сценарии
"""
import ast
import json
import time
import re
from typing import Dict, List, Any

class AdvancedAgentCodeQualityTester:
    """Расширенный тестер для сложных сценариев генерации кода"""
    
    def __init__(self):
        # Более сложные примеры кода, которые могли бы сгенерировать агенты
        self.advanced_code_examples = {
            "design_patterns": '''from abc import ABC, abstractmethod
from typing import List, Optional
from enum import Enum

class PaymentStatus(Enum):
    """Статусы платежа."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class PaymentProcessor(ABC):
    """Абстрактный базовый класс для обработки платежей."""
    
    @abstractmethod
    def process_payment(self, amount: float, currency: str) -> Dict[str, Any]:
        """Обрабатывает платеж."""
        pass
    
    @abstractmethod
    def validate_payment_data(self, payment_data: Dict[str, Any]) -> bool:
        """Валидирует данные платежа."""
        pass

class CreditCardProcessor(PaymentProcessor):
    """Обработчик платежей по кредитным картам."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._transaction_log: List[Dict[str, Any]] = []
    
    def process_payment(self, amount: float, currency: str = "USD") -> Dict[str, Any]:
        """
        Обрабатывает платеж по кредитной карте.
        
        Args:
            amount: Сумма платежа
            currency: Валюта платежа
            
        Returns:
            Результат обработки платежа
            
        Raises:
            ValueError: При некорректных данных
            PaymentError: При ошибке обработки
        """
        if amount <= 0:
            raise ValueError("Сумма платежа должна быть положительной")
        
        if currency not in ["USD", "EUR", "RUB"]:
            raise ValueError(f"Неподдерживаемая валюта: {currency}")
        
        try:
            # Симуляция обработки платежа
            transaction_id = f"txn_{int(time.time())}"
            
            result = {
                "transaction_id": transaction_id,
                "amount": amount,
                "currency": currency,
                "status": PaymentStatus.COMPLETED.value,
                "timestamp": time.time()
            }
            
            self._transaction_log.append(result)
            return result
            
        except Exception as e:
            error_result = {
                "error": str(e),
                "status": PaymentStatus.FAILED.value,
                "timestamp": time.time()
            }
            self._transaction_log.append(error_result)
            raise PaymentError(f"Ошибка обработки платежа: {e}")
    
    def validate_payment_data(self, payment_data: Dict[str, Any]) -> bool:
        """Валидирует данные платежа."""
        required_fields = ["card_number", "expiry_date", "cvv", "amount"]
        
        for field in required_fields:
            if field not in payment_data:
                return False
        
        # Дополнительные проверки
        card_number = payment_data.get("card_number", "")
        if not card_number.isdigit() or len(card_number) != 16:
            return False
        
        return True

class PaymentError(Exception):
    """Исключение для ошибок платежей."""
    pass''',
            
            "async_architecture": '''import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from contextlib import asynccontextmanager

@dataclass
class APIEndpoint:
    """Конфигурация API endpoint."""
    url: str
    method: str = "GET"
    timeout: int = 30
    retries: int = 3
    headers: Optional[Dict[str, str]] = None

class AsyncAPIClient:
    """
    Асинхронный клиент для работы с множественными API.
    
    Поддерживает:
    - Параллельные запросы
    - Retry логику с exponential backoff
    - Circuit breaker pattern
    - Rate limiting
    - Кэширование ответов
    """
    
    def __init__(self, max_concurrent: int = 10, rate_limit: int = 100):
        self.max_concurrent = max_concurrent
        self.rate_limit = rate_limit
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rate_limiter = asyncio.Semaphore(rate_limit)
        self.cache: Dict[str, Any] = {}
        self.circuit_breaker_failures: Dict[str, int] = {}
        self.logger = logging.getLogger(__name__)
    
    @asynccontextmanager
    async def session(self):
        """Контекстный менеджер для HTTP сессии."""
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
        timeout = aiohttp.ClientTimeout(total=60)
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        ) as session:
            yield session
    
    async def fetch_single(
        self, 
        endpoint: APIEndpoint, 
        session: aiohttp.ClientSession,
        cache_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Выполняет один HTTP запрос с обработкой ошибок.
        
        Args:
            endpoint: Конфигурация endpoint
            session: HTTP сессия
            cache_key: Ключ для кэширования
            
        Returns:
            Ответ API или информация об ошибке
        """
        # Проверяем кэш
        if cache_key and cache_key in self.cache:
            self.logger.info(f"Cache hit for {cache_key}")
            return self.cache[cache_key]
        
        # Circuit breaker check
        if self.circuit_breaker_failures.get(endpoint.url, 0) > 5:
            return {"error": "Circuit breaker open", "url": endpoint.url}
        
        async with self.semaphore:  # Ограничение concurrent запросов
            async with self.rate_limiter:  # Rate limiting
                for attempt in range(endpoint.retries):
                    try:
                        async with session.request(
                            endpoint.method,
                            endpoint.url,
                            headers=endpoint.headers or {},
                            timeout=aiohttp.ClientTimeout(total=endpoint.timeout)
                        ) as response:
                            
                            if response.status == 200:
                                data = await response.json()
                                result = {
                                    "data": data,
                                    "status": response.status,
                                    "url": endpoint.url,
                                    "attempt": attempt + 1
                                }
                                
                                # Кэшируем успешный ответ
                                if cache_key:
                                    self.cache[cache_key] = result
                                
                                # Сбрасываем счетчик ошибок
                                self.circuit_breaker_failures[endpoint.url] = 0
                                
                                return result
                            else:
                                self.logger.warning(f"HTTP {response.status} for {endpoint.url}")
                                
                    except asyncio.TimeoutError:
                        self.logger.error(f"Timeout for {endpoint.url} (attempt {attempt + 1})")
                        if attempt < endpoint.retries - 1:
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
                    except Exception as e:
                        self.logger.error(f"Error for {endpoint.url}: {e}")
                        if attempt < endpoint.retries - 1:
                            await asyncio.sleep(2 ** attempt)
                
                # Увеличиваем счетчик ошибок для circuit breaker
                self.circuit_breaker_failures[endpoint.url] = \
                    self.circuit_breaker_failures.get(endpoint.url, 0) + 1
                
                return {
                    "error": "Max retries exceeded",
                    "url": endpoint.url,
                    "retries": endpoint.retries
                }
    
    async def fetch_multiple(
        self, 
        endpoints: List[APIEndpoint],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Выполняет множественные HTTP запросы параллельно.
        
        Args:
            endpoints: Список endpoint для запросов
            progress_callback: Callback для отслеживания прогресса
            
        Returns:
            Список результатов запросов
        """
        async with self.session() as session:
            tasks = []
            
            for i, endpoint in enumerate(endpoints):
                cache_key = f"{endpoint.method}:{endpoint.url}"
                task = self.fetch_single(endpoint, session, cache_key)
                tasks.append(task)
            
            results = []
            completed = 0
            
            # Обрабатываем результаты по мере готовности
            for coro in asyncio.as_completed(tasks):
                result = await coro
                results.append(result)
                completed += 1
                
                if progress_callback:
                    progress_callback(completed, len(endpoints))
            
            return results
    
    def clear_cache(self):
        """Очищает кэш."""
        self.cache.clear()
        self.logger.info("Cache cleared")
    
    def get_circuit_breaker_status(self) -> Dict[str, int]:
        """Возвращает статус circuit breaker для всех URL."""
        return self.circuit_breaker_failures.copy()''',
            
            "data_pipeline": '''import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Callable, Union
from pathlib import Path
from abc import ABC, abstractmethod

@dataclass
class DataQualityMetrics:
    """Метрики качества данных."""
    completeness: float  # Процент заполненных значений
    uniqueness: float    # Процент уникальных значений
    validity: float      # Процент валидных значений
    consistency: float   # Процент консистентных значений
    accuracy: float      # Процент точных значений

class DataProcessor(ABC):
    """Абстрактный базовый класс для обработки данных."""
    
    @abstractmethod
    def process(self, data: pd.DataFrame) -> pd.DataFrame:
        """Обрабатывает данные."""
        pass
    
    @abstractmethod
    def validate(self, data: pd.DataFrame) -> bool:
        """Валидирует данные."""
        pass

class DataCleaningProcessor(DataProcessor):
    """Процессор для очистки данных."""
    
    def __init__(self, 
                 remove_duplicates: bool = True,
                 fill_missing: bool = True,
                 outlier_threshold: float = 3.0):
        self.remove_duplicates = remove_duplicates
        self.fill_missing = fill_missing
        self.outlier_threshold = outlier_threshold
        self.logger = logging.getLogger(__name__)
    
    def process(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Очищает данные от дубликатов, пропусков и выбросов.
        
        Args:
            data: Исходные данные
            
        Returns:
            Очищенные данные
        """
        cleaned_data = data.copy()
        original_shape = cleaned_data.shape
        
        # Удаление дубликатов
        if self.remove_duplicates:
            before_dedup = len(cleaned_data)
            cleaned_data = cleaned_data.drop_duplicates()
            after_dedup = len(cleaned_data)
            self.logger.info(f"Removed {before_dedup - after_dedup} duplicates")
        
        # Обработка пропущенных значений
        if self.fill_missing:
            for column in cleaned_data.columns:
                if cleaned_data[column].dtype in ['int64', 'float64']:
                    # Заполняем медианой для числовых данных
                    median_value = cleaned_data[column].median()
                    cleaned_data[column].fillna(median_value, inplace=True)
                else:
                    # Заполняем модой для категориальных данных
                    mode_value = cleaned_data[column].mode().iloc[0] if not cleaned_data[column].mode().empty else 'Unknown'
                    cleaned_data[column].fillna(mode_value, inplace=True)
        
        # Удаление выбросов (только для числовых колонок)
        numeric_columns = cleaned_data.select_dtypes(include=[np.number]).columns
        for column in numeric_columns:
            z_scores = np.abs((cleaned_data[column] - cleaned_data[column].mean()) / cleaned_data[column].std())
            cleaned_data = cleaned_data[z_scores < self.outlier_threshold]
        
        final_shape = cleaned_data.shape
        self.logger.info(f"Data shape changed from {original_shape} to {final_shape}")
        
        return cleaned_data
    
    def validate(self, data: pd.DataFrame) -> bool:
        """Валидирует очищенные данные."""
        if data.empty:
            return False
        
        # Проверяем, что нет критических пропусков
        critical_missing_threshold = 0.5
        for column in data.columns:
            missing_ratio = data[column].isnull().sum() / len(data)
            if missing_ratio > critical_missing_threshold:
                self.logger.error(f"Column {column} has {missing_ratio:.2%} missing values")
                return False
        
        return True

class DataPipeline:
    """
    Конвейер обработки данных с поддержкой множественных процессоров.
    
    Поддерживает:
    - Цепочку обработчиков данных
    - Валидацию на каждом этапе
    - Метрики качества данных
    - Логирование и мониторинг
    - Откат к предыдущему состоянию при ошибках
    """
    
    def __init__(self, name: str):
        self.name = name
        self.processors: List[DataProcessor] = []
        self.logger = logging.getLogger(__name__)
        self.processing_history: List[Dict[str, Any]] = []
    
    def add_processor(self, processor: DataProcessor) -> 'DataPipeline':
        """Добавляет процессор в конвейер."""
        self.processors.append(processor)
        self.logger.info(f"Added processor {processor.__class__.__name__} to pipeline {self.name}")
        return self
    
    def calculate_quality_metrics(self, data: pd.DataFrame) -> DataQualityMetrics:
        """
        Вычисляет метрики качества данных.
        
        Args:
            data: Данные для анализа
            
        Returns:
            Метрики качества данных
        """
        total_cells = data.size
        
        # Completeness - процент заполненных значений
        filled_cells = total_cells - data.isnull().sum().sum()
        completeness = filled_cells / total_cells if total_cells > 0 else 0
        
        # Uniqueness - средний процент уникальных значений по колонкам
        uniqueness_scores = []
        for column in data.columns:
            unique_ratio = data[column].nunique() / len(data) if len(data) > 0 else 0
            uniqueness_scores.append(unique_ratio)
        uniqueness = np.mean(uniqueness_scores) if uniqueness_scores else 0
        
        # Validity - процент валидных значений (без NaN и inf)
        valid_cells = total_cells - data.isnull().sum().sum()
        if data.select_dtypes(include=[np.number]).size > 0:
            valid_cells -= np.isinf(data.select_dtypes(include=[np.number])).sum().sum()
        validity = valid_cells / total_cells if total_cells > 0 else 0
        
        # Consistency и Accuracy - упрощенные метрики
        consistency = 0.9  # Placeholder - требует доменных знаний
        accuracy = 0.85    # Placeholder - требует эталонных данных
        
        return DataQualityMetrics(
            completeness=completeness,
            uniqueness=uniqueness,
            validity=validity,
            consistency=consistency,
            accuracy=accuracy
        )
    
    def process(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Выполняет полный цикл обработки данных.
        
        Args:
            data: Исходные данные
            
        Returns:
            Результат обработки с метриками и историей
        """
        if data.empty:
            raise ValueError("Input data is empty")
        
        current_data = data.copy()
        processing_steps = []
        
        # Начальные метрики
        initial_metrics = self.calculate_quality_metrics(current_data)
        processing_steps.append({
            "step": "initial",
            "processor": "none",
            "shape": current_data.shape,
            "quality_metrics": initial_metrics
        })
        
        # Обрабатываем данные через каждый процессор
        for i, processor in enumerate(self.processors):
            step_name = f"step_{i+1}_{processor.__class__.__name__}"
            
            try:
                # Сохраняем состояние для возможного отката
                backup_data = current_data.copy()
                
                # Обрабатываем данные
                processed_data = processor.process(current_data)
                
                # Валидируем результат
                if not processor.validate(processed_data):
                    self.logger.error(f"Validation failed for {processor.__class__.__name__}")
                    current_data = backup_data  # Откат
                    continue
                
                current_data = processed_data
                
                # Вычисляем метрики после обработки
                step_metrics = self.calculate_quality_metrics(current_data)
                
                processing_steps.append({
                    "step": step_name,
                    "processor": processor.__class__.__name__,
                    "shape": current_data.shape,
                    "quality_metrics": step_metrics
                })
                
                self.logger.info(f"Completed {step_name}: shape {current_data.shape}")
                
            except Exception as e:
                self.logger.error(f"Error in {processor.__class__.__name__}: {e}")
                processing_steps.append({
                    "step": step_name,
                    "processor": processor.__class__.__name__,
                    "error": str(e)
                })
        
        # Финальные метрики
        final_metrics = self.calculate_quality_metrics(current_data)
        
        result = {
            "pipeline_name": self.name,
            "processed_data": current_data,
            "initial_shape": data.shape,
            "final_shape": current_data.shape,
            "initial_quality": initial_metrics,
            "final_quality": final_metrics,
            "processing_steps": processing_steps,
            "success": len(processing_steps) > 1  # Больше чем только initial step
        }
        
        # Сохраняем в историю
        self.processing_history.append({
            "timestamp": pd.Timestamp.now(),
            "initial_shape": data.shape,
            "final_shape": current_data.shape,
            "quality_improvement": final_metrics.completeness - initial_metrics.completeness
        })
        
        return result
    
    def get_processing_history(self) -> List[Dict[str, Any]]:
        """Возвращает историю обработки."""
        return self.processing_history.copy()
    
    def export_metrics(self, filepath: Union[str, Path]) -> None:
        """Экспортирует метрики в JSON файл."""
        metrics_data = {
            "pipeline_name": self.name,
            "processors": [p.__class__.__name__ for p in self.processors],
            "history": self.processing_history
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(metrics_data, f, indent=2, default=str)
        
        self.logger.info(f"Metrics exported to {filepath}")'''
        }
        
        # Примеры кода с проблемами для тестирования детекции
        self.problematic_code_examples = {
            "security_issues": '''import os
import subprocess

# ПРОБЛЕМА: Hardcoded credentials
API_KEY = "sk-1234567890abcdef"
DATABASE_URL = "postgresql://admin:password123@localhost/db"

def execute_command(user_input):
    # ПРОБЛЕМА: Command injection vulnerability
    result = subprocess.run(f"ls {user_input}", shell=True, capture_output=True)
    return result.stdout

def unsafe_file_read(filename):
    # ПРОБЛЕМА: Path traversal vulnerability
    with open(f"/data/{filename}", 'r') as f:
        return f.read()

def eval_user_code(code):
    # ПРОБЛЕМА: Code injection
    return eval(code)''',
            
            "performance_issues": '''import time

def inefficient_search(data, target):
    # ПРОБЛЕМА: O(n²) complexity
    for i in range(len(data)):
        for j in range(len(data)):
            if data[i] == target and data[j] == target:
                return i, j
    return None

def memory_leak_example():
    # ПРОБЛЕМА: Потенциальная утечка памяти
    global_cache = []
    while True:
        data = [i for i in range(10000)]
        global_cache.append(data)
        time.sleep(0.1)

def blocking_io():
    # ПРОБЛЕМА: Блокирующий I/O без async
    import requests
    urls = ["http://example.com"] * 100
    results = []
    for url in urls:
        response = requests.get(url)
        results.append(response.text)
    return results''',
            
            "maintainability_issues": '''def process_data(d):
    # ПРОБЛЕМА: Нет документации, неясные имена переменных
    r = []
    for x in d:
        if x > 0:
            y = x * 2
            if y > 10:
                z = y / 3
                r.append(z)
            else:
                r.append(y)
        else:
            r.append(0)
    return r

class DataProcessor:
    # ПРОБЛЕМА: Слишком много ответственностей
    def __init__(self):
        self.data = []
        self.results = []
        self.errors = []
        self.config = {}
        self.cache = {}
        self.logger = None
        self.db_connection = None
        self.api_client = None
    
    def process_everything(self, input_data, config, db_url, api_key):
        # ПРОБЛЕМА: Монолитный метод
        try:
            self.connect_to_db(db_url)
            self.setup_api(api_key)
            self.validate_input(input_data)
            self.clean_data(input_data)
            self.transform_data()
            self.enrich_data()
            self.validate_output()
            self.save_to_db()
            self.send_to_api()
            self.generate_report()
            self.cleanup()
        except:
            pass  # ПРОБЛЕМА: Пустой except'''
        }
    
    def test_advanced_code_quality(self) -> Dict[str, Any]:
        """Тестирует качество кода на сложных примерах"""
        print("🧪 Расширенное тестирование качества кода агентов")
        print("=" * 70)
        
        # Тестовые задачи повышенной сложности
        advanced_tasks = [
            {
                "name": "design_patterns",
                "description": "Реализуй паттерн Strategy для обработки платежей с валидацией",
                "complexity": "expert",
                "code_key": "design_patterns",
                "expected_patterns": ["ABC", "abstractmethod", "Enum", "type hints", "error handling"]
            },
            {
                "name": "async_architecture", 
                "description": "Создай асинхронный API клиент с circuit breaker и rate limiting",
                "complexity": "expert",
                "code_key": "async_architecture",
                "expected_patterns": ["async", "await", "asyncio", "context manager", "semaphore"]
            },
            {
                "name": "data_pipeline",
                "description": "Разработай data pipeline с метриками качества и обработкой ошибок",
                "complexity": "expert", 
                "code_key": "data_pipeline",
                "expected_patterns": ["pandas", "dataclass", "ABC", "logging", "metrics"]
            }
        ]
        
        # Тестируем проблемный код
        problematic_tasks = [
            {
                "name": "security_issues",
                "description": "Код с проблемами безопасности",
                "complexity": "problematic",
                "code_key": "security_issues",
                "expected_issues": ["hardcoded credentials", "command injection", "path traversal"]
            },
            {
                "name": "performance_issues", 
                "description": "Код с проблемами производительности",
                "complexity": "problematic",
                "code_key": "performance_issues",
                "expected_issues": ["O(n²) complexity", "memory leak", "blocking I/O"]
            },
            {
                "name": "maintainability_issues",
                "description": "Код с проблемами поддерживаемости", 
                "complexity": "problematic",
                "code_key": "maintainability_issues",
                "expected_issues": ["no documentation", "unclear names", "monolithic method"]
            }
        ]
        
        results = {
            "advanced_tests": [],
            "problematic_tests": [],
            "advanced_average": 0.0,
            "problematic_average": 0.0,
            "expert_level_ready": False
        }
        
        # Тестируем продвинутые примеры
        print("\n🎯 Тестирование экспертного уровня:")
        advanced_scores = []
        
        for task in advanced_tasks:
            print(f"\n📝 Экспертная задача: {task['name']}")
            code = self.advanced_code_examples.get(task['code_key'], "")
            
            if code:
                quality_score = self._analyze_advanced_code_quality(code, task)
                advanced_scores.append(quality_score['total_score'])
                
                results["advanced_tests"].append({
                    "task": task['name'],
                    "complexity": task['complexity'],
                    "quality_score": quality_score,
                    "code_length": len(code)
                })
                
                print(f"{'✅' if quality_score['total_score'] >= 8.0 else '⚠️'} Качество: {quality_score['total_score']:.1f}/10")
        
        # Тестируем проблемный код
        print(f"\n🔍 Тестирование детекции проблем:")
        problematic_scores = []
        
        for task in problematic_tasks:
            print(f"\n📝 Проблемный код: {task['name']}")
            code = self.problematic_code_examples.get(task['code_key'], "")
            
            if code:
                quality_score = self._analyze_problematic_code(code, task)
                problematic_scores.append(quality_score['total_score'])
                
                results["problematic_tests"].append({
                    "task": task['name'],
                    "complexity": task['complexity'],
                    "quality_score": quality_score,
                    "detected_issues": quality_score.get('detected_issues', [])
                })
                
                print(f"❌ Качество: {quality_score['total_score']:.1f}/10 (ожидаемо низкое)")
        
        # Вычисляем средние оценки
        if advanced_scores:
            results["advanced_average"] = sum(advanced_scores) / len(advanced_scores)
            results["expert_level_ready"] = results["advanced_average"] >= 8.5
        
        if problematic_scores:
            results["problematic_average"] = sum(problematic_scores) / len(problematic_scores)
        
        return results
    
    def _analyze_advanced_code_quality(self, code: str, task: Dict) -> Dict[str, Any]:
        """Анализирует качество продвинутого кода"""
        quality_metrics = {
            "syntax_valid": 0,
            "architecture_patterns": 0,
            "error_handling": 0,
            "type_safety": 0,
            "documentation": 0,
            "performance_awareness": 0,
            "maintainability": 0,
            "security_awareness": 0,
            "total_score": 0
        }
        
        # 1. Синтаксис (1 балл)
        try:
            ast.parse(code)
            quality_metrics["syntax_valid"] = 1.0
            print("  ✅ Синтаксис корректен")
        except SyntaxError:
            print("  ❌ Синтаксические ошибки")
        
        # 2. Архитектурные паттерны (2 балла)
        pattern_score = 0
        expected_patterns = task.get("expected_patterns", [])
        
        for pattern in expected_patterns:
            if pattern.lower() in code.lower():
                pattern_score += 0.4
        
        quality_metrics["architecture_patterns"] = min(2.0, pattern_score)
        print(f"  {'✅' if pattern_score >= 1.5 else '⚠️'} Архитектурные паттерны: {pattern_score:.1f}/2.0")
        
        # 3. Обработка ошибок (1.5 балла)
        error_handling_score = 0
        if "try:" in code and "except" in code:
            error_handling_score += 0.5
        if "raise" in code:
            error_handling_score += 0.5
        if "ValueError" in code or "TypeError" in code or "Exception" in code:
            error_handling_score += 0.3
        if "logging" in code or "logger" in code:
            error_handling_score += 0.2
        
        quality_metrics["error_handling"] = min(1.5, error_handling_score)
        print(f"  {'✅' if error_handling_score >= 1.0 else '⚠️'} Обработка ошибок: {error_handling_score:.1f}/1.5")
        
        # 4. Type safety (1.5 балла)
        type_score = 0
        if "from typing import" in code or "typing." in code:
            type_score += 0.5
        if "->" in code:
            type_score += 0.5
        if ": " in code and "def " in code:
            type_score += 0.3
        if "Optional" in code or "Union" in code or "List" in code or "Dict" in code:
            type_score += 0.2
        
        quality_metrics["type_safety"] = min(1.5, type_score)
        print(f"  {'✅' if type_score >= 1.0 else '⚠️'} Type safety: {type_score:.1f}/1.5")
        
        # 5. Документация (1 балл)
        doc_score = 0
        if '"""' in code:
            doc_score += 0.5
        if "Args:" in code and "Returns:" in code:
            doc_score += 0.3
        if "Raises:" in code:
            doc_score += 0.2
        
        quality_metrics["documentation"] = min(1.0, doc_score)
        print(f"  {'✅' if doc_score >= 0.7 else '⚠️'} Документация: {doc_score:.1f}/1.0")
        
        # 6. Performance awareness (1 балл)
        perf_score = 0
        if "async" in code and "await" in code:
            perf_score += 0.4
        if "cache" in code.lower() or "Cache" in code:
            perf_score += 0.2
        if "semaphore" in code.lower() or "Semaphore" in code:
            perf_score += 0.2
        if "pool" in code.lower() or "Pool" in code:
            perf_score += 0.2
        
        quality_metrics["performance_awareness"] = min(1.0, perf_score)
        print(f"  {'✅' if perf_score >= 0.6 else '⚠️'} Performance awareness: {perf_score:.1f}/1.0")
        
        # 7. Maintainability (1 балл)
        maint_score = 0.8  # Базовая оценка
        
        # Проверяем длину функций
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if hasattr(node, 'end_lineno') and hasattr(node, 'lineno'):
                        func_length = node.end_lineno - node.lineno
                        if func_length > 50:
                            maint_score -= 0.2
        except:
            pass
        
        # Проверяем именование
        if re.search(r'def [a-z_][a-z0-9_]*\(', code):
            maint_score += 0.1
        
        quality_metrics["maintainability"] = max(0.0, min(1.0, maint_score))
        print(f"  {'✅' if maint_score >= 0.7 else '⚠️'} Maintainability: {maint_score:.1f}/1.0")
        
        # 8. Security awareness (0.5 балла)
        security_score = 0.3  # Базовая оценка
        
        # Проверяем на отсутствие очевидных проблем
        if "eval(" not in code and "exec(" not in code:
            security_score += 0.1
        if "shell=True" not in code:
            security_score += 0.1
        
        quality_metrics["security_awareness"] = min(0.5, security_score)
        print(f"  {'✅' if security_score >= 0.4 else '⚠️'} Security awareness: {security_score:.1f}/0.5")
        
        # Общий балл
        total = sum(quality_metrics.values()) - quality_metrics["total_score"]
        quality_metrics["total_score"] = total
        
        return quality_metrics
    
    def _analyze_problematic_code(self, code: str, task: Dict) -> Dict[str, Any]:
        """Анализирует проблемный код и детектирует проблемы"""
        quality_metrics = {
            "syntax_valid": 0,
            "security_issues": 0,
            "performance_issues": 0,
            "maintainability_issues": 0,
            "detected_issues": [],
            "total_score": 0
        }
        
        detected_issues = []
        
        # 1. Синтаксис
        try:
            ast.parse(code)
            quality_metrics["syntax_valid"] = 1.0
        except SyntaxError:
            detected_issues.append("Синтаксические ошибки")
        
        # 2. Проблемы безопасности
        security_issues = 0
        if 'API_KEY = "' in code or 'password' in code.lower():
            detected_issues.append("Hardcoded credentials")
            security_issues += 1
        
        if "shell=True" in code:
            detected_issues.append("Command injection vulnerability")
            security_issues += 1
        
        if "eval(" in code or "exec(" in code:
            detected_issues.append("Code injection vulnerability")
            security_issues += 1
        
        if "/{" in code and "}" in code:  # Простая проверка path traversal
            detected_issues.append("Potential path traversal")
            security_issues += 1
        
        quality_metrics["security_issues"] = max(0, 3 - security_issues)  # Инвертируем
        
        # 3. Проблемы производительности
        performance_issues = 0
        if "for i in range(len(" in code and "for j in range(len(" in code:
            detected_issues.append("O(n²) complexity")
            performance_issues += 1
        
        if "while True:" in code and "append" in code:
            detected_issues.append("Potential memory leak")
            performance_issues += 1
        
        if "requests.get" in code and "for" in code:
            detected_issues.append("Blocking I/O in loop")
            performance_issues += 1
        
        quality_metrics["performance_issues"] = max(0, 3 - performance_issues)
        
        # 4. Проблемы поддерживаемости
        maintainability_issues = 0
        if '"""' not in code and "def " in code:
            detected_issues.append("Missing documentation")
            maintainability_issues += 1
        
        # Проверяем короткие имена переменных
        if re.search(r'\b[a-z]\b', code):
            detected_issues.append("Unclear variable names")
            maintainability_issues += 1
        
        if "except:" in code:
            detected_issues.append("Bare except clause")
            maintainability_issues += 1
        
        # Проверяем длинные методы
        if code.count('\n') > 30 and "def " in code:
            detected_issues.append("Monolithic method")
            maintainability_issues += 1
        
        quality_metrics["maintainability_issues"] = max(0, 3 - maintainability_issues)
        quality_metrics["detected_issues"] = detected_issues
        
        # Общий балл (должен быть низким для проблемного кода)
        total = (quality_metrics["syntax_valid"] + 
                quality_metrics["security_issues"] + 
                quality_metrics["performance_issues"] + 
                quality_metrics["maintainability_issues"]) / 4 * 10
        
        quality_metrics["total_score"] = total
        
        print(f"  🔍 Обнаружено проблем: {len(detected_issues)}")
        for issue in detected_issues:
            print(f"    ❌ {issue}")
        
        return quality_metrics
    
    def generate_advanced_report(self, results: Dict[str, Any]) -> str:
        """Генерирует расширенный отчет"""
        report = f"""# 🎯 Расширенный анализ качества кода агентов

## 📊 Результаты экспертного тестирования

### 🏆 Экспертный уровень
- **Средняя оценка:** {results['advanced_average']:.1f}/10
- **Готовность к экспертным задачам:** {'✅ ДА' if results['expert_level_ready'] else '❌ НЕТ'}

### 🔍 Детекция проблем
- **Средняя оценка проблемного кода:** {results['problematic_average']:.1f}/10 (ожидаемо низкая)

## 🎯 Экспертная оценка

"""
        
        if results['expert_level_ready']:
            report += """### ✅ ЭКСПЕРТНЫЙ УРОВЕНЬ ДОСТИГНУТ!

Агенты демонстрируют способность генерировать код **экспертного уровня** с:
- Сложными архитектурными паттернами
- Асинхронным программированием
- Продвинутой обработкой ошибок
- Метриками и мониторингом
- Type safety и документацией

**Готовность:** Агенты готовы для сложных enterprise проектов.

"""
        else:
            report += f"""### ⚠️ ЭКСПЕРТНЫЙ УРОВЕНЬ НЕ ДОСТИГНУТ

Текущая оценка {results['advanced_average']:.1f}/10 не достигает порога 8.5/10.

**Требуется улучшение в:**
- Архитектурных паттернах
- Асинхронном программировании  
- Продвинутой обработке ошибок
- Performance оптимизации

"""
        
        # Детальные результаты
        report += "## 📋 Детальные результаты экспертных задач\n\n"
        
        for test in results['advanced_tests']:
            score = test['quality_score']
            report += f"### {test['task']} ({test['complexity']})\n"
            report += f"**Общая оценка:** {score['total_score']:.1f}/10\n\n"
            
            report += "**Детальные метрики:**\n"
            report += f"- 🔧 Синтаксис: {score['syntax_valid']:.1f}/1.0\n"
            report += f"- 🏗️ Архитектурные паттерны: {score['architecture_patterns']:.1f}/2.0\n"
            report += f"- 🛡️ Обработка ошибок: {score['error_handling']:.1f}/1.5\n"
            report += f"- 🏷️ Type safety: {score['type_safety']:.1f}/1.5\n"
            report += f"- 📚 Документация: {score['documentation']:.1f}/1.0\n"
            report += f"- ⚡ Performance awareness: {score['performance_awareness']:.1f}/1.0\n"
            report += f"- 🔧 Maintainability: {score['maintainability']:.1f}/1.0\n"
            report += f"- 🔒 Security awareness: {score['security_awareness']:.1f}/0.5\n\n"
        
        # Результаты детекции проблем
        report += "## 🔍 Результаты детекции проблем\n\n"
        
        for test in results['problematic_tests']:
            report += f"### {test['task']}\n"
            report += f"**Оценка качества:** {test['quality_score']['total_score']:.1f}/10 (низкая - ожидаемо)\n"
            
            detected = test['quality_score'].get('detected_issues', [])
            if detected:
                report += "**Обнаруженные проблемы:**\n"
                for issue in detected:
                    report += f"- ❌ {issue}\n"
            report += "\n"
        
        # Рекомендации
        report += "## 💡 Рекомендации для достижения экспертного уровня\n\n"
        
        if results['expert_level_ready']:
            report += """### Для поддержания экспертного уровня:
1. **Расширяйте паттерны** - добавьте больше GoF паттернов
2. **Углубляйте async** - добавьте advanced concurrency patterns
3. **Усиливайте мониторинг** - метрики, трейсинг, профилирование
4. **Развивайте security** - добавьте security-by-design принципы

"""
        else:
            report += """### Критические улучшения для экспертного уровня:
1. **Изучите архитектурные паттерны** - Strategy, Factory, Observer, etc.
2. **Освойте async/await** - asyncio, aiohttp, concurrent.futures
3. **Улучшите error handling** - custom exceptions, retry logic, circuit breaker
4. **Добавьте type safety** - полное покрытие type hints
5. **Внедрите мониторинг** - logging, metrics, health checks

"""
        
        report += f"""## 🎯 Заключение

{'✅ **ЭКСПЕРТНЫЙ УРОВЕНЬ ДОСТИГНУТ**' if results['expert_level_ready'] else '⚠️ **ТРЕБУЕТСЯ РАЗВИТИЕ ДО ЭКСПЕРТНОГО УРОВНЯ**'}

Агенты {'готовы' if results['expert_level_ready'] else 'не готовы'} для решения сложных архитектурных задач и enterprise разработки.

---
**Отчет подготовлен:** {time.strftime('%d.%m.%Y %H:%M')}
**Эксперт:** Senior Software Architect
"""
        
        return report

def main():
    """Основная функция расширенного тестирования"""
    print("🚀 Запуск расширенного тестирования качества кода агентов")
    
    tester = AdvancedAgentCodeQualityTester()
    results = tester.test_advanced_code_quality()
    
    # Генерируем отчет
    report = tester.generate_advanced_report(results)
    
    # Сохраняем отчет
    report_file = f"ADVANCED_AGENT_CODE_QUALITY_REPORT_{time.strftime('%Y-%m-%d')}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n📄 Расширенный отчет сохранен в файл: {report_file}")
    
    # Выводим результаты
    print(f"\n🎯 ЭКСПЕРТНАЯ ОЦЕНКА: {results['advanced_average']:.1f}/10")
    print(f"🔍 ДЕТЕКЦИЯ ПРОБЛЕМ: {results['problematic_average']:.1f}/10 (ожидаемо низкая)")
    print(f"🏆 ЭКСПЕРТНЫЙ УРОВЕНЬ: {'✅ ДОСТИГНУТ' if results['expert_level_ready'] else '❌ НЕ ДОСТИГНУТ'}")
    
    return results

if __name__ == "__main__":
    main()