"""
Тест Circuit Breaker для LLM
"""
import time
from agent_runtime.orchestrator.agent import CircuitBreaker, CircuitBreakerError, get_llm_circuit_breaker, Agent


def test_circuit_breaker_states():
    """Тест переходов состояний Circuit Breaker"""
    print("=" * 60)
    print("Testing Circuit Breaker state transitions")
    print("=" * 60)

    # Создаём CB с низкими порогами для теста
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=2, success_threshold=1)  # 2 секунды для быстрого теста

    # Начальное состояние
    print(f"\n1. Initial state: {cb.state}")
    assert cb.state == "CLOSED"
    assert cb.can_execute() == True
    print("   [OK] CLOSED, can execute")

    # Первая ошибка
    cb.record_failure(Exception("Test error 1"))
    print(f"\n2. After 1 failure: {cb.state}, failures={cb.failure_count}")
    assert cb.state == "CLOSED"  # Ещё не достигли порога
    print("   [OK] Still CLOSED (threshold=2)")

    # Вторая ошибка - переход в OPEN
    cb.record_failure(Exception("Test error 2"))
    print(f"\n3. After 2 failures: {cb.state}, failures={cb.failure_count}")
    assert cb.state == "OPEN"
    assert cb.can_execute() == False
    print("   [OK] OPEN, cannot execute")

    # Ждём recovery timeout
    print(f"\n4. Waiting {cb.recovery_timeout}s for recovery...")
    time.sleep(cb.recovery_timeout + 0.5)

    # Проверяем переход в HALF_OPEN
    can_exec = cb.can_execute()
    print(f"5. After recovery timeout: {cb.state}, can_execute={can_exec}")
    assert cb.state == "HALF_OPEN"
    assert can_exec == True
    print("   [OK] HALF_OPEN, can execute (probe)")

    # Успешный вызов - переход в CLOSED
    cb.record_success()
    print(f"\n6. After success in HALF_OPEN: {cb.state}")
    assert cb.state == "CLOSED"
    assert cb.failure_count == 0
    print("   [OK] CLOSED, failure count reset")

    print("\n" + "=" * 60)
    print("All state transition tests passed!")
    print("=" * 60)


def test_circuit_breaker_metrics():
    """Тест метрик Circuit Breaker"""
    print("\n" + "=" * 60)
    print("Testing Circuit Breaker metrics")
    print("=" * 60)

    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)

    # Симулируем вызовы
    cb.record_success()
    cb.record_success()
    cb.record_failure(Exception("Error 1"))
    cb.record_success()

    status = cb.get_status()
    print(f"\nStatus: {status}")

    assert status["total_calls"] == 4
    assert status["total_failures"] == 1
    assert status["state"] == "CLOSED"
    print("[OK] Metrics correct")

    print("\n" + "=" * 60)
    print("Metrics tests passed!")
    print("=" * 60)


def test_circuit_breaker_half_open_failure():
    """Тест: ошибка в HALF_OPEN возвращает в OPEN"""
    print("\n" + "=" * 60)
    print("Testing HALF_OPEN failure -> OPEN")
    print("=" * 60)

    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)

    # Переводим в OPEN
    cb.record_failure(Exception("Error"))
    assert cb.state == "OPEN"
    print(f"1. State: {cb.state}")

    # Ждём recovery
    time.sleep(1.5)
    cb.can_execute()  # Переход в HALF_OPEN
    assert cb.state == "HALF_OPEN"
    print(f"2. State: {cb.state}")

    # Ошибка в HALF_OPEN
    cb.record_failure(Exception("Error in probe"))
    assert cb.state == "OPEN"
    print(f"3. State after failure: {cb.state}")
    print("[OK] Correctly returned to OPEN")

    print("\n" + "=" * 60)
    print("HALF_OPEN failure test passed!")
    print("=" * 60)


def test_global_circuit_breaker():
    """Тест глобального Circuit Breaker"""
    print("\n" + "=" * 60)
    print("Testing global LLM Circuit Breaker")
    print("=" * 60)

    cb1 = get_llm_circuit_breaker()
    cb2 = get_llm_circuit_breaker()

    assert cb1 is cb2, "Should be singleton"
    print("[OK] Singleton pattern works")

    print(f"Global CB status: {cb1.get_status()}")

    print("\n" + "=" * 60)
    print("Global Circuit Breaker test passed!")
    print("=" * 60)


def test_agent_with_circuit_breaker():
    """Тест Agent с Circuit Breaker (без реального LLM)"""
    print("\n" + "=" * 60)
    print("Testing Agent with Circuit Breaker")
    print("=" * 60)

    agent = Agent(name="TestAgent", role="Test", llm_url="http://localhost:9999")  # Несуществующий URL

    # Сбрасываем глобальный CB для чистого теста
    global _llm_circuit_breaker
    from agent_runtime.orchestrator import agent as agent_module

    agent_module._llm_circuit_breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=5)

    cb = get_llm_circuit_breaker()
    print(f"Initial CB state: {cb.state}")

    # Первый вызов - ошибка соединения
    result1 = agent._call_llm([{"role": "user", "content": "test"}])
    print(f"\n1. First call result: {result1[:50]}...")
    print(f"   CB state: {cb.state}, failures: {cb.failure_count}")
    assert "[LLM_CONNECTION_ERROR]" in result1 or "[LLM_ERROR]" in result1

    # Второй вызов - ещё одна ошибка, CB переходит в OPEN
    result2 = agent._call_llm([{"role": "user", "content": "test"}])
    print(f"\n2. Second call result: {result2[:50]}...")
    print(f"   CB state: {cb.state}, failures: {cb.failure_count}")
    assert cb.state == "OPEN"

    # Третий вызов - CB блокирует
    result3 = agent._call_llm([{"role": "user", "content": "test"}])
    print(f"\n3. Third call (blocked): {result3[:60]}...")
    assert "[CIRCUIT_BREAKER_OPEN]" in result3
    assert cb.total_blocked >= 1
    print(f"   Blocked calls: {cb.total_blocked}")

    print("\n[OK] Agent correctly uses Circuit Breaker")

    # Проверяем статистику
    stats = agent.get_timing_stats()
    print(f"\nAgent timing stats with CB:")
    print(f"  circuit_breaker.state: {stats['circuit_breaker']['state']}")
    print(f"  circuit_breaker.total_blocked: {stats['circuit_breaker']['total_blocked']}")

    print("\n" + "=" * 60)
    print("Agent Circuit Breaker test passed!")
    print("=" * 60)


if __name__ == "__main__":
    test_circuit_breaker_states()
    test_circuit_breaker_metrics()
    test_circuit_breaker_half_open_failure()
    test_global_circuit_breaker()
    test_agent_with_circuit_breaker()

    print("\n" + "=" * 60)
    print("[SUCCESS] All Circuit Breaker tests passed!")
    print("=" * 60)
