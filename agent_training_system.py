"""
Система тренировки агентов для достижения максимального качества кода
"""
import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

class TrainingLevel(Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

@dataclass
class TrainingTask:
    """Задача для тренировки агента"""
    name: str
    description: str
    level: TrainingLevel
    target_score: float
    requirements: List[str]
    example_solution: str
    scoring_criteria: Dict[str, float]

class AgentTrainingSystem:
    """Система для тренировки агентов на достижение 10/10 баллов"""
    
    def __init__(self):
        self.training_tasks = self._create_training_tasks()
        self.progress_history: List[Dict] = []
    
    def _create_training_tasks(self) -> List[TrainingTask]:
        """Создает прогрессивные задачи для тренировки"""
        return [
            # Уровень 1: Базовые улучшения
            TrainingTask(
                name="perfect_factorial",
                description="Создай идеальную функцию факториала с максимальной обработкой ошибок",
                level=TrainingLevel.BEGINNER,
                target_score=10.0,
                requirements=[
                    "Type hints для всех параметров",
                    "Comprehensive docstring с Examples",
                    "Валидация типов и значений",
                    "Обработка edge cases",
                    "Performance notes в документации",
                    "Логирование операций"
                ],
                example_solution="""
def perfect_factorial(n: int) -> int:
    '''
    Вычисляет факториал числа n с полной обработкой ошибок.
    
    Args:
        n: Неотрицательное целое число <= 1000
        
    Returns:
        Факториал числа n
        
    Raises:
        TypeError: Если n не является целым числом
        ValueError: Если n отрицательное или слишком большое
        OverflowError: Если результат слишком большой
        
    Example:
        >>> perfect_factorial(5)
        120
        >>> perfect_factorial(0)
        1
        
    Performance:
        O(n) время, O(1) память (итеративная версия)
    '''
    import logging
    
    # Валидация типа
    if not isinstance(n, int):
        raise TypeError(f"Expected int, got {type(n).__name__}")
    
    # Валидация значения
    if n < 0:
        raise ValueError("Factorial undefined for negative numbers")
    
    if n > 1000:
        raise ValueError("Number too large for computation")
    
    # Логирование
    logging.info(f"Computing factorial of {n}")
    
    # Базовые случаи
    if n in (0, 1):
        return 1
    
    # Итеративная реализация
    result = 1
    for i in range(2, n + 1):
        result *= i
        if result > 10**100:
            raise OverflowError("Result too large")
    
    return result
                """,
                scoring_criteria={
                    "syntax_valid": 2.0,
                    "type_hints": 1.5,
                    "documentation": 2.0,
                    "error_handling": 2.0,
                    "requirements": 2.0,
                    "performance": 0.5
                }
            ),
            
            # Уровень 2: Архитектурные паттерны
            TrainingTask(
                name="strategy_pattern_calculator",
                description="Реализуй калькулятор используя Strategy pattern с полной архитектурой",
                level=TrainingLevel.INTERMEDIATE,
                target_score=10.0,
                requirements=[
                    "Strategy pattern implementation",
                    "Factory pattern для создания стратегий",
                    "Comprehensive error handling",
                    "Type safety с Protocol",
                    "Logging и metrics",
                    "Unit tests в docstring"
                ],
                example_solution="""
from abc import ABC, abstractmethod
from typing import Protocol, Dict, Any

class OperationStrategy(Protocol):
    def execute(self, a: float, b: float) -> float: ...
    def validate(self, a: float, b: float) -> bool: ...

class AdditionStrategy:
    def execute(self, a: float, b: float) -> float:
        return a + b
    
    def validate(self, a: float, b: float) -> bool:
        return True

class DivisionStrategy:
    def execute(self, a: float, b: float) -> float:
        if b == 0:
            raise ZeroDivisionError("Division by zero")
        return a / b
    
    def validate(self, a: float, b: float) -> bool:
        return b != 0

class StrategyFactory:
    _strategies = {
        'add': AdditionStrategy,
        'divide': DivisionStrategy
    }
    
    @classmethod
    def create(cls, operation: str) -> OperationStrategy:
        if operation not in cls._strategies:
            raise ValueError(f"Unknown operation: {operation}")
        return cls._strategies[operation]()

class PerfectCalculator:
    '''
    Калькулятор с архитектурными паттернами и полной обработкой ошибок.
    
    Example:
        >>> calc = PerfectCalculator()
        >>> result = calc.calculate('add', 5, 3)
        >>> assert result == 8
    '''
    
    def __init__(self):
        self.history: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(__name__)
    
    def calculate(self, operation: str, a: float, b: float) -> float:
        start_time = time.time()
        
        try:
            strategy = StrategyFactory.create(operation)
            
            if not strategy.validate(a, b):
                raise ValueError(f"Invalid inputs for {operation}")
            
            result = strategy.execute(a, b)
            
            # Логирование и метрики
            execution_time = time.time() - start_time
            self._log_operation(operation, a, b, result, execution_time)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Calculation failed: {e}")
            raise
    
    def _log_operation(self, op: str, a: float, b: float, result: float, time: float):
        record = {
            'operation': op,
            'inputs': [a, b],
            'result': result,
            'execution_time': time,
            'timestamp': time.time()
        }
        self.history.append(record)
        self.logger.info(f"Executed {op}({a}, {b}) = {result} in {time:.4f}s")
                """,
                scoring_criteria={
                    "syntax_valid": 1.0,
                    "architecture_patterns": 3.0,
                    "type_safety": 2.0,
                    "error_handling": 2.0,
                    "documentation": 1.5,
                    "performance": 0.5
                }
            ),
            
            # Уровень 3: Высокопроизводительные системы
            TrainingTask(
                name="async_data_pipeline",
                description="Создай высокопроизводительный async data pipeline с метриками",
                level=TrainingLevel.EXPERT,
                target_score=10.0,
                requirements=[
                    "Async/await с proper error handling",
                    "Connection pooling и rate limiting",
                    "Circuit breaker pattern",
                    "Comprehensive metrics collection",
                    "Memory-efficient processing",
                    "Batch processing optimization",
                    "Graceful shutdown handling"
                ],
                example_solution="""
import asyncio
import aiohttp
from typing import AsyncIterator, Dict, List, Optional, Callable
from contextlib import asynccontextmanager

@dataclass
class PipelineMetrics:
    processed_items: int = 0
    failed_items: int = 0
    average_processing_time: float = 0.0
    throughput_per_second: float = 0.0

class HighPerformanceDataPipeline:
    '''
    Высокопроизводительный асинхронный data pipeline.
    
    Features:
    - Async processing с connection pooling
    - Circuit breaker для отказоустойчивости
    - Rate limiting с token bucket
    - Comprehensive metrics
    - Memory-efficient streaming
    - Graceful shutdown
    
    Example:
        >>> async with HighPerformanceDataPipeline() as pipeline:
        ...     async for result in pipeline.process_stream(data_source):
        ...         print(f"Processed: {result}")
    '''
    
    def __init__(self, max_concurrent: int = 50, rate_limit: int = 100):
        self.max_concurrent = max_concurrent
        self.rate_limit = rate_limit
        self.metrics = PipelineMetrics()
        self.logger = logging.getLogger(__name__)
        
        # Concurrency control
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._rate_limiter = asyncio.Semaphore(rate_limit)
        
        # Circuit breaker
        self._circuit_failures: Dict[str, int] = {}
        self._circuit_last_failure: Dict[str, float] = {}
        
        # Metrics tracking
        self._processing_times: List[float] = []
        self._start_time = time.time()
    
    async def __aenter__(self):
        # Connection pooling setup
        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=30,
            keepalive_timeout=30
        )
        
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=60)
        )
        
        # Start token bucket refill
        self._token_task = asyncio.create_task(self._refill_tokens())
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Graceful shutdown
        if hasattr(self, '_token_task'):
            self._token_task.cancel()
        
        if hasattr(self, '_session'):
            await self._session.close()
    
    async def process_stream(self, 
                           data_source: AsyncIterator[Dict],
                           batch_size: int = 10) -> AsyncIterator[Dict]:
        '''
        Обрабатывает поток данных с оптимальной производительностью.
        
        Args:
            data_source: Асинхронный итератор данных
            batch_size: Размер батча для обработки
            
        Yields:
            Обработанные элементы данных
        '''
        batch = []
        
        async for item in data_source:
            batch.append(item)
            
            if len(batch) >= batch_size:
                # Обрабатываем батч параллельно
                results = await self._process_batch(batch)
                
                for result in results:
                    if result is not None:
                        yield result
                
                batch.clear()
        
        # Обрабатываем оставшиеся элементы
        if batch:
            results = await self._process_batch(batch)
            for result in results:
                if result is not None:
                    yield result
    
    async def _process_batch(self, batch: List[Dict]) -> List[Optional[Dict]]:
        '''Параллельная обработка батча с error handling.'''
        tasks = [self._process_single_item(item) for item in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                self.metrics.failed_items += 1
                self.logger.error(f"Processing failed: {result}")
                processed_results.append(None)
            else:
                self.metrics.processed_items += 1
                processed_results.append(result)
        
        return processed_results
    
    async def _process_single_item(self, item: Dict) -> Dict:
        '''Обработка одного элемента с полным набором оптимизаций.'''
        start_time = time.time()
        
        # Rate limiting
        async with self._rate_limiter:
            async with self._semaphore:
                
                # Circuit breaker check
                item_id = item.get('id', 'unknown')
                if self._is_circuit_open(item_id):
                    raise Exception(f"Circuit breaker open for {item_id}")
                
                try:
                    # Симуляция обработки
                    processed_item = await self._perform_processing(item)
                    
                    # Reset circuit breaker on success
                    self._reset_circuit_breaker(item_id)
                    
                    # Record metrics
                    processing_time = time.time() - start_time
                    self._record_processing_time(processing_time)
                    
                    return processed_item
                
                except Exception as e:
                    self._record_circuit_failure(item_id)
                    raise
    
    async def _perform_processing(self, item: Dict) -> Dict:
        '''Фактическая обработка элемента.'''
        # Симуляция async обработки
        await asyncio.sleep(0.01)  # Имитация I/O операции
        
        return {
            **item,
            'processed': True,
            'timestamp': time.time(),
            'processing_version': '1.0'
        }
    
    def _is_circuit_open(self, item_id: str) -> bool:
        '''Проверка состояния circuit breaker.'''
        if item_id not in self._circuit_failures:
            return False
        
        failures = self._circuit_failures[item_id]
        last_failure = self._circuit_last_failure.get(item_id, 0)
        
        # Открываем circuit после 5 ошибок
        if failures >= 5:
            # Проверяем timeout (30 секунд)
            if time.time() - last_failure > 30:
                self._reset_circuit_breaker(item_id)
                return False
            return True
        
        return False
    
    def _record_circuit_failure(self, item_id: str) -> None:
        '''Записывает ошибку для circuit breaker.'''
        self._circuit_failures[item_id] = self._circuit_failures.get(item_id, 0) + 1
        self._circuit_last_failure[item_id] = time.time()
    
    def _reset_circuit_breaker(self, item_id: str) -> None:
        '''Сбрасывает circuit breaker.'''
        self._circuit_failures.pop(item_id, None)
        self._circuit_last_failure.pop(item_id, None)
    
    def _record_processing_time(self, processing_time: float) -> None:
        '''Записывает время обработки для метрик.'''
        self._processing_times.append(processing_time)
        
        # Ограничиваем размер истории
        if len(self._processing_times) > 1000:
            self._processing_times = self._processing_times[-500:]
        
        # Обновляем метрики
        self.metrics.average_processing_time = sum(self._processing_times) / len(self._processing_times)
        
        elapsed_time = time.time() - self._start_time
        if elapsed_time > 0:
            self.metrics.throughput_per_second = self.metrics.processed_items / elapsed_time
    
    async def _refill_tokens(self) -> None:
        '''Пополнение токенов для rate limiting.'''
        while True:
            await asyncio.sleep(1.0 / self.rate_limit)
            if self._rate_limiter._value < self.rate_limit:
                self._rate_limiter.release()
    
    def get_metrics(self) -> PipelineMetrics:
        '''Получение текущих метрик производительности.'''
        return self.metrics
                """,
                scoring_criteria={
                    "syntax_valid": 1.0,
                    "architecture_patterns": 2.0,
                    "async_programming": 2.0,
                    "performance_optimization": 2.0,
                    "error_handling": 1.5,
                    "metrics_collection": 1.0,
                    "documentation": 0.5
                }
            )
        ]
    
    def train_agent(self, task_name: str) -> Dict[str, Any]:
        """Тренирует агента на конкретной задаче"""
        task = next((t for t in self.training_tasks if t.name == task_name), None)
        if not task:
            raise ValueError(f"Task {task_name} not found")
        
        print(f"🎯 Тренировка агента на задаче: {task.name}")
        print(f"📋 Описание: {task.description}")
        print(f"🎖️ Уровень: {task.level.value}")
        print(f"🎯 Целевой балл: {task.target_score}/10")
        
        print(f"\n✅ Требования для достижения {task.target_score}/10:")
        for i, req in enumerate(task.requirements, 1):
            print(f"  {i}. {req}")
        
        print(f"\n💡 Пример идеального решения:")
        print("=" * 60)
        print(task.example_solution)
        print("=" * 60)
        
        print(f"\n📊 Критерии оценки:")
        for criterion, max_score in task.scoring_criteria.items():
            print(f"  • {criterion}: {max_score} баллов")
        
        # Записываем прогресс
        progress_record = {
            "timestamp": time.time(),
            "task_name": task_name,
            "level": task.level.value,
            "target_score": task.target_score,
            "status": "training_started"
        }
        self.progress_history.append(progress_record)
        
        return {
            "task": task,
            "training_started": True,
            "next_steps": [
                "Изучите пример решения",
                "Реализуйте все требования",
                "Протестируйте код на соответствие критериям",
                "Запустите оценку качества"
            ]
        }
    
    def get_training_plan(self) -> Dict[str, Any]:
        """Возвращает полный план тренировки"""
        plan = {
            "total_tasks": len(self.training_tasks),
            "levels": {},
            "estimated_time": "6-8 недель",
            "progression": []
        }
        
        for task in self.training_tasks:
            level = task.level.value
            if level not in plan["levels"]:
                plan["levels"][level] = []
            
            plan["levels"][level].append({
                "name": task.name,
                "description": task.description,
                "target_score": task.target_score,
                "requirements_count": len(task.requirements)
            })
        
        # Рекомендуемая последовательность
        plan["progression"] = [
            "1. Начните с BEGINNER уровня",
            "2. Достигните 10/10 на всех базовых задачах",
            "3. Переходите к INTERMEDIATE уровню",
            "4. Изучите архитектурные паттерны",
            "5. Освойте ADVANCED уровень",
            "6. Достигните EXPERT уровня",
            "7. Регулярно тестируйте прогресс"
        ]
        
        return plan
    
    def save_progress(self, filename: str = "agent_training_progress.json"):
        """Сохраняет прогресс тренировки"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.progress_history, f, indent=2, default=str)
        print(f"💾 Прогресс сохранен в {filename}")

def main():
    """Демонстрация системы тренировки"""
    trainer = AgentTrainingSystem()
    
    print("🚀 Система тренировки агентов для достижения 10/10 баллов")
    print("=" * 70)
    
    # Показываем план тренировки
    plan = trainer.get_training_plan()
    print(f"\n📋 План тренировки ({plan['estimated_time']}):")
    print(f"Всего задач: {plan['total_tasks']}")
    
    for level, tasks in plan["levels"].items():
        print(f"\n🎖️ Уровень {level.upper()}:")
        for task in tasks:
            print(f"  • {task['name']}: {task['description']}")
    
    print(f"\n📈 Рекомендуемая последовательность:")
    for step in plan["progression"]:
        print(f"  {step}")
    
    # Демонстрация тренировки на первой задаче
    print(f"\n" + "="*70)
    trainer.train_agent("perfect_factorial")
    
    # Сохраняем прогресс
    trainer.save_progress()

if __name__ == "__main__":
    main()