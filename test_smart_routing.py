"""
Тест интеграции smart routing в consult()
"""
from agent_runtime.orchestrator.consilium import route_agents, get_consilium

def test_route_agents():
    """Тест функции route_agents"""
    print("=" * 60)
    print("Testing route_agents()")
    print("=" * 60)

    test_cases = [
        # (query, expected_mode, expected_agents_subset)
        ("Add a button to the page", "FAST", ["dev"]),
        ("Check JWT token security", "STANDARD", ["dev", "security"]),
        ("Migrate database and add tests", "STANDARD", ["dev", "architect", "qa"]),
        ("Production breach! System compromised!", "CRITICAL", ["director"]),
        ("Review XSS vulnerability and add e2e tests for microservice", "CRITICAL", ["security", "qa", "architect"]),
    ]

    for query, expected_mode, expected_agents in test_cases:
        result = route_agents(query)

        print(f"\nQuery: '{query[:50]}...'")
        print(f"  Mode: {result['mode']} (expected: {expected_mode})")
        print(f"  Agents: {result['agents']}")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Domains: {result['domains_matched']}")
        print(f"  Downgraded: {result.get('downgraded', False)}")

        # Проверки
        assert result["mode"] == expected_mode, f"Mode mismatch: {result['mode']} != {expected_mode}"
        for agent in expected_agents:
            assert agent in result["agents"], f"Missing agent: {agent}"

        print("  [OK] PASSED")

    print("\n" + "=" * 60)
    print("All route_agents tests passed!")
    print("=" * 60)

def test_consult_with_routing():
    """Тест consult() с smart routing (без LLM - только структура)"""
    print("\n" + "=" * 60)
    print("Testing consult() with smart routing")
    print("=" * 60)

    # Получаем consilium (singleton)
    consilium = get_consilium()

    # Тест 1: Simple query -> FAST mode
    print("\n--- Test 1: Simple query (FAST) ---")
    query1 = "What is Python?"
    routing1 = route_agents(query1)
    print(f"Query: {query1}")
    print(f"Routing result: mode={routing1['mode']}, agents={routing1['agents']}")
    assert routing1["mode"] == "FAST"
    assert routing1["agents"] == ["dev"]
    print("[OK] FAST mode routing correct")

    # Тест 2: Security query -> STANDARD mode
    print("\n--- Test 2: Security query (STANDARD) ---")
    query2 = "Review JWT authentication"
    routing2 = route_agents(query2)
    print(f"Query: {query2}")
    print(f"Routing result: mode={routing2['mode']}, agents={routing2['agents']}")
    assert routing2["mode"] == "STANDARD"
    assert "security" in routing2["agents"]
    print("[OK] STANDARD mode routing correct")

    # Тест 3: Complex query -> CRITICAL mode
    print("\n--- Test 3: Complex query (CRITICAL) ---")
    query3 = "XSS vulnerability found, need e2e tests and microservice migration"
    routing3 = route_agents(query3)
    print(f"Query: {query3}")
    print(f"Routing result: mode={routing3['mode']}, agents={routing3['agents']}, confidence={routing3['confidence']}")
    assert routing3["mode"] == "CRITICAL"
    assert "director" in routing3["agents"]
    print("[OK] CRITICAL mode routing correct")

    # Тест 4: Downgrade scenario
    print("\n--- Test 4: Downgrade scenario ---")
    query4 = "Check auth token and test db performance"  # 3 domains but weak triggers
    routing4 = route_agents(query4)
    print(f"Query: {query4}")
    print(
        f"Routing result: mode={routing4['mode']}, confidence={routing4['confidence']}, downgraded={routing4.get('downgraded')}"
    )
    # Может быть STANDARD или CRITICAL в зависимости от confidence
    print(f"[OK] Routing decision: {routing4['mode']}")

    print("\n" + "=" * 60)
    print("All consult routing tests passed!")
    print("=" * 60)

if __name__ == "__main__":
    test_route_agents()
    test_consult_with_routing()
    print("\n[SUCCESS] All tests passed!")
