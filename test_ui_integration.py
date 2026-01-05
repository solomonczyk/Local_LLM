#!/usr/bin/env python3
"""
Тест интеграции UI с системой агентов
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from agent_runtime.orchestrator.consilium import get_consilium, route_agents
from agent_runtime.orchestrator.agent import get_llm_circuit_breaker


def test_system_status():
    """Тест статуса системы"""
    print("=== Testing System Status ===")
    
    try:
        # Circuit Breaker
        cb = get_llm_circuit_breaker()
        cb_status = cb.get_status()
        print(f"✓ Circuit Breaker: {cb_status['state']}")
        
        # Consilium
        consilium = get_consilium()
        print(f"✓ Consilium Mode: {consilium.mode}")
        print(f"✓ Active Agents: {consilium.active_agents}")
        print(f"✓ KB Version: {consilium.kb_version_hash}")
        
        # Health check
        health = consilium.check_llm_health(timeout=3.0)
        print(f"✓ LLM Health: {'OK' if health['healthy'] else 'UNAVAILABLE'}")
        
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_routing():
    """Тест роутинга"""
    print("\n=== Testing Routing ===")
    
    test_tasks = [
        "Create a REST API for user authentication",
        "Design database schema for e-commerce",
        "Write unit tests for payment module",
        "Optimize website performance",
        "Review code for security vulnerabilities"
    ]
    
    try:
        for task in test_tasks:
            routing = route_agents(task)
            print(f"✓ Task: {task[:50]}...")
            print(f"  Mode: {routing['mode']}, Agents: {routing['agents']}")
            print(f"  Confidence: {routing['confidence']}, Domains: {routing['domains_matched']}")
        
        return True
    except Exception as e:
        print(f"✗ Routing error: {e}")
        return False


def test_simple_consultation():
    """Тест простой консультации"""
    print("\n=== Testing Simple Consultation ===")
    
    try:
        consilium = get_consilium()
        
        # Простая задача в FAST режиме
        os.environ["CONSILIUM_MODE"] = "FAST"
        result = consilium.consult(
            "Explain the difference between REST and GraphQL APIs",
            use_smart_routing=True,
            check_health=True
        )
        
        if result.get("success") == False:
            print(f"✗ Consultation failed: {result.get('error')}")
            return False
        
        print("✓ Consultation successful")
        print(f"  Mode: {result.get('mode')}")
        print(f"  Agents used: {list(result.get('opinions', {}).keys())}")
        
        if result.get('director_decision'):
            decision = result['director_decision'][:200] + "..." if len(result['director_decision']) > 200 else result['director_decision']
            print(f"  Decision preview: {decision}")
        
        return True
    except Exception as e:
        print(f"✗ Consultation error: {e}")
        return False


def main():
    """Запуск всех тестов"""
    print("🤖 Agent System UI Integration Test")
    print("=" * 50)
    
    tests = [
        ("System Status", test_system_status),
        ("Routing", test_routing),
        ("Simple Consultation", test_simple_consultation)
    ]
    
    passed = 0
    total = len(tests)
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✅ {name}: PASSED")
            else:
                print(f"\n❌ {name}: FAILED")
        except Exception as e:
            print(f"\n💥 {name}: ERROR - {e}")
    
    print("\n" + "=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! UI should work correctly.")
        print(f"🌐 Open http://localhost:7864 to use the UI")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)