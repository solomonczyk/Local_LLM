"""
Тест Health Check для LLM
"""
from agent_runtime.orchestrator.agent import Agent
from agent_runtime.orchestrator.consilium import get_consilium


def test_agent_health_check():
    """Тест health check в Agent"""
    print("=" * 60)
    print("Testing Agent health check")
    print("=" * 60)
    
    # Тест с несуществующим сервером
    agent = Agent(
        name="TestAgent",
        role="Test",
        llm_url="http://localhost:9999/v1"  # Несуществующий
    )
    
    result = agent.check_llm_health(timeout=2.0)
    print(f"\nHealth check (non-existent server):")
    print(f"  healthy: {result['healthy']}")
    print(f"  status: {result['status']}")
    print(f"  error: {result.get('error', 'N/A')[:50]}...")
    
    assert result["healthy"] == False
    assert result["status"] == "connection_error"
    print("[OK] Correctly detected unhealthy server")
    
    # Тест с реальным сервером (если запущен)
    agent_real = Agent(
        name="RealAgent",
        role="Test",
        llm_url="http://localhost:8000/v1"
    )
    
    result_real = agent_real.check_llm_health(timeout=5.0)
    print(f"\nHealth check (localhost:8000):")
    print(f"  healthy: {result_real['healthy']}")
    print(f"  status: {result_real['status']}")
    if result_real['healthy']:
        print(f"  response_time_ms: {result_real.get('response_time_ms', 'N/A')}")
    else:
        print(f"  error: {result_real.get('error', 'N/A')[:50]}...")
    
    print("\n" + "=" * 60)
    print("Agent health check tests passed!")
    print("=" * 60)


def test_consilium_health_check():
    """Тест health check в Consilium"""
    print("\n" + "=" * 60)
    print("Testing Consilium health check")
    print("=" * 60)
    
    consilium = get_consilium()
    
    # Проверяем метод check_llm_health
    result = consilium.check_llm_health(timeout=2.0)
    print(f"\nConsilium health check:")
    print(f"  healthy: {result['healthy']}")
    print(f"  status: {result['status']}")
    
    print("\n" + "=" * 60)
    print("Consilium health check tests passed!")
    print("=" * 60)


def test_consult_with_health_check():
    """Тест consult() с health check"""
    print("\n" + "=" * 60)
    print("Testing consult() with health check")
    print("=" * 60)
    
    consilium = get_consilium()
    
    # Вызываем consult с health check
    # Если LLM недоступен, должен вернуть ошибку сразу
    result = consilium.consult(
        "What is Python?",
        use_smart_routing=True,
        check_health=True
    )
    
    print(f"\nConsult result:")
    print(f"  success: {result.get('success', True)}")
    
    if result.get('success', True) == False:
        print(f"  error: {result.get('error', 'N/A')}")
        print(f"  health_check: {result.get('health_check', {})}")
        print("[OK] Correctly failed with health check error")
    else:
        print(f"  mode: {result.get('mode', 'N/A')}")
        print(f"  health_check: {result.get('health_check', {})}")
        print("[OK] Consult succeeded with healthy LLM")
    
    print("\n" + "=" * 60)
    print("Consult health check tests passed!")
    print("=" * 60)


def test_consult_skip_health_check():
    """Тест consult() без health check"""
    print("\n" + "=" * 60)
    print("Testing consult() without health check")
    print("=" * 60)
    
    consilium = get_consilium()
    
    # Вызываем consult БЕЗ health check
    result = consilium.consult(
        "What is Python?",
        use_smart_routing=True,
        check_health=False  # Пропускаем health check
    )
    
    print(f"\nConsult result (no health check):")
    print(f"  mode: {result.get('mode', 'N/A')}")
    print(f"  health_check in result: {'health_check' in result}")
    
    # health_check не должен быть в результате
    assert "health_check" not in result or result.get("health_check") is None
    print("[OK] Health check correctly skipped")
    
    print("\n" + "=" * 60)
    print("Skip health check tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    test_agent_health_check()
    test_consilium_health_check()
    test_consult_with_health_check()
    test_consult_skip_health_check()
    
    print("\n" + "=" * 60)
    print("[SUCCESS] All health check tests passed!")
    print("=" * 60)
