"""
Тест Retry Logic с exponential backoff
"""
import time
from unittest.mock import patch, MagicMock
import requests
from agent_runtime.orchestrator.agent import Agent, get_llm_circuit_breaker, CircuitBreaker
import agent_runtime.orchestrator.agent as agent_module


def test_retry_config():
    """Тест конфигурации retry"""
    print("=" * 60)
    print("Testing retry configuration")
    print("=" * 60)
    
    agent = Agent(name="Test", role="Test")
    
    assert agent._max_retries == 3
    assert agent._retry_base_delay == 1.0
    assert agent._retry_max_delay == 10.0
    assert agent._retry_count == 0
    
    print(f"max_retries: {agent._max_retries}")
    print(f"base_delay: {agent._retry_base_delay}s")
    print(f"max_delay: {agent._retry_max_delay}s")
    print("[OK] Retry config correct")
    
    print("\n" + "=" * 60)
    print("Retry config test passed!")
    print("=" * 60)


def test_retry_in_timing_stats():
    """Тест что retry метрики есть в timing stats"""
    print("\n" + "=" * 60)
    print("Testing retry metrics in timing stats")
    print("=" * 60)
    
    agent = Agent(name="Test", role="Test")
    stats = agent.get_timing_stats()
    
    assert "retry_count" in stats
    assert "retry_config" in stats
    assert stats["retry_config"]["max_retries"] == 3
    
    print(f"retry_count: {stats['retry_count']}")
    print(f"retry_config: {stats['retry_config']}")
    print("[OK] Retry metrics in stats")
    
    print("\n" + "=" * 60)
    print("Retry metrics test passed!")
    print("=" * 60)


def test_no_retry_on_connection_error():
    """Тест: connection error НЕ вызывает retry"""
    print("\n" + "=" * 60)
    print("Testing no retry on connection error")
    print("=" * 60)
    
    # Сбрасываем Circuit Breaker
    agent_module._llm_circuit_breaker = CircuitBreaker(
        failure_threshold=10,  # Высокий порог чтобы не открылся
        recovery_timeout=60
    )
    
    agent = Agent(
        name="Test",
        role="Test",
        llm_url="http://localhost:9999/v1"  # Несуществующий
    )
    
    initial_retry_count = agent._retry_count
    
    result = agent._call_llm([{"role": "user", "content": "test"}])
    
    print(f"Result: {result[:60]}...")
    print(f"Retry count before: {initial_retry_count}, after: {agent._retry_count}")
    
    assert "[LLM_CONNECTION_ERROR]" in result
    assert agent._retry_count == initial_retry_count  # Не было retry
    print("[OK] No retry on connection error")
    
    print("\n" + "=" * 60)
    print("No retry on connection error test passed!")
    print("=" * 60)


def test_exponential_backoff_calculation():
    """Тест расчёта exponential backoff"""
    print("\n" + "=" * 60)
    print("Testing exponential backoff calculation")
    print("=" * 60)
    
    base_delay = 1.0
    max_delay = 10.0
    
    delays = []
    for attempt in range(5):
        delay = min(base_delay * (2 ** attempt), max_delay)
        delays.append(delay)
        print(f"Attempt {attempt}: delay = {delay}s")
    
    assert delays == [1.0, 2.0, 4.0, 8.0, 10.0]  # Последний ограничен max_delay
    print("[OK] Exponential backoff correct")
    
    print("\n" + "=" * 60)
    print("Exponential backoff test passed!")
    print("=" * 60)


def test_retry_on_timeout_mock():
    """Тест retry при timeout (с mock)"""
    print("\n" + "=" * 60)
    print("Testing retry on timeout (mocked)")
    print("=" * 60)
    
    # Сбрасываем Circuit Breaker
    agent_module._llm_circuit_breaker = CircuitBreaker(
        failure_threshold=10,
        recovery_timeout=60
    )
    
    agent = Agent(name="Test", role="Test")
    agent._retry_base_delay = 0.1  # Быстрый retry для теста
    agent._max_retries = 3
    
    call_count = 0
    
    def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise requests.exceptions.Timeout("Timeout")
        # Третий вызов успешен
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Success after retry"}}]
        }
        return mock_response
    
    with patch('requests.post', side_effect=mock_post):
        result = agent._call_llm([{"role": "user", "content": "test"}])
    
    print(f"Call count: {call_count}")
    print(f"Result: {result}")
    print(f"Retry count: {agent._retry_count}")
    
    assert call_count == 3  # 2 timeout + 1 success
    assert result == "Success after retry"
    assert agent._retry_count == 2  # 2 retries
    print("[OK] Retry on timeout works")
    
    print("\n" + "=" * 60)
    print("Retry on timeout test passed!")
    print("=" * 60)


def test_max_retries_exceeded():
    """Тест: превышение max_retries"""
    print("\n" + "=" * 60)
    print("Testing max retries exceeded")
    print("=" * 60)
    
    # Сбрасываем Circuit Breaker
    agent_module._llm_circuit_breaker = CircuitBreaker(
        failure_threshold=10,
        recovery_timeout=60
    )
    
    agent = Agent(name="Test", role="Test")
    agent._retry_base_delay = 0.1
    agent._max_retries = 2
    
    call_count = 0
    
    def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise requests.exceptions.Timeout("Always timeout")
    
    with patch('requests.post', side_effect=mock_post):
        result = agent._call_llm([{"role": "user", "content": "test"}])
    
    print(f"Call count: {call_count}")
    print(f"Result: {result[:60]}...")
    
    assert call_count == 2  # max_retries попыток
    assert "[LLM_TIMEOUT]" in result
    assert "after 2 attempts" in result
    print("[OK] Max retries exceeded handled correctly")
    
    print("\n" + "=" * 60)
    print("Max retries exceeded test passed!")
    print("=" * 60)


def test_retry_on_5xx_error():
    """Тест retry при 5xx HTTP ошибке"""
    print("\n" + "=" * 60)
    print("Testing retry on 5xx HTTP error")
    print("=" * 60)
    
    # Сбрасываем Circuit Breaker
    agent_module._llm_circuit_breaker = CircuitBreaker(
        failure_threshold=10,
        recovery_timeout=60
    )
    
    agent = Agent(name="Test", role="Test")
    agent._retry_base_delay = 0.1
    agent._max_retries = 3
    
    call_count = 0
    
    def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
                response=mock_response
            )
            return mock_response
        # Третий вызов успешен
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Success after 503"}}]
        }
        return mock_response
    
    with patch('requests.post', side_effect=mock_post):
        result = agent._call_llm([{"role": "user", "content": "test"}])
    
    print(f"Call count: {call_count}")
    print(f"Result: {result}")
    
    assert call_count == 3
    assert result == "Success after 503"
    print("[OK] Retry on 5xx works")
    
    print("\n" + "=" * 60)
    print("Retry on 5xx test passed!")
    print("=" * 60)


def test_no_retry_on_4xx_error():
    """Тест: 4xx ошибка НЕ вызывает retry"""
    print("\n" + "=" * 60)
    print("Testing no retry on 4xx error")
    print("=" * 60)
    
    # Сбрасываем Circuit Breaker
    agent_module._llm_circuit_breaker = CircuitBreaker(
        failure_threshold=10,
        recovery_timeout=60
    )
    
    agent = Agent(name="Test", role="Test")
    agent._retry_base_delay = 0.1
    
    call_count = 0
    
    def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_response = MagicMock()
        mock_response.status_code = 400
        error = requests.exceptions.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = error
        return mock_response
    
    with patch('requests.post', side_effect=mock_post):
        result = agent._call_llm([{"role": "user", "content": "test"}])
    
    print(f"Call count: {call_count}")
    print(f"Result: {result[:60]}...")
    
    assert call_count == 1  # Только один вызов, без retry
    assert "[LLM_HTTP_ERROR]" in result
    print("[OK] No retry on 4xx error")
    
    print("\n" + "=" * 60)
    print("No retry on 4xx test passed!")
    print("=" * 60)


if __name__ == "__main__":
    test_retry_config()
    test_retry_in_timing_stats()
    test_no_retry_on_connection_error()
    test_exponential_backoff_calculation()
    test_retry_on_timeout_mock()
    test_max_retries_exceeded()
    test_retry_on_5xx_error()
    test_no_retry_on_4xx_error()
    
    print("\n" + "=" * 60)
    print("[SUCCESS] All retry logic tests passed!")
    print("=" * 60)
