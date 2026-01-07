#!/usr/bin/env python3
"""
Тест Director Adapter без реального вызова OpenAI
"""

import os
from agent_system.director_adapter import DirectorAdapter, DirectorRequest, RiskLevel


def test_director_logic():
    """Тест логики Director без API вызовов"""
    
    adapter = DirectorAdapter()
    
    print("="*60)
    print("Testing Director Adapter Logic")
    print("="*60)
    
    # Тест 1: Жёсткие триггеры
    test_cases = [
        ("Implement user authentication", 0.8, ["dev"]),  # security trigger
        ("Add database migration", 0.9, ["dev"]),        # migration trigger
        ("Simple UI button", 0.9, ["dev"]),              # no trigger
        ("Fix payment processing", 0.8, ["dev"]),        # payment trigger
        ("Regular task", 0.6, ["dev", "qa"]),            # confidence trigger
        ("Complex task", 0.8, ["dev", "qa", "security", "architect"]),  # domain trigger
    ]
    
    for task, confidence, domains in test_cases:
        should_use = adapter.should_use_director(task, confidence, domains)
        print(f"Task: {task[:30]:<30} | Confidence: {confidence} | Domains: {len(domains)} | Director: {'✅' if should_use else '❌'}")
    
    # Тест 2: Валидация контракта
    print(f"\n{'='*60}")
    print("Testing Contract Validation")
    print("="*60)
    
    # Валидный запрос
    valid_request = DirectorRequest(
        problem_summary="Short task description",
        facts=["Fact 1", "Fact 2"],
        agent_summaries={"dev": "Summary", "security": "Summary"},
        risk_level=RiskLevel.MEDIUM,
        confidence=0.75
    )
    
    print(f"Valid request: {'✅' if valid_request.validate() else '❌'}")
    
    # Невалидный запрос (слишком длинный summary)
    invalid_request = DirectorRequest(
        problem_summary="x" * 600,  # Слишком длинный
        facts=["Fact 1"],
        agent_summaries={"dev": "Summary"},
        risk_level=RiskLevel.LOW,
        confidence=1.5  # Невалидная confidence
    )
    
    print(f"Invalid request: {'❌' if not invalid_request.validate() else '✅'}")
    
    # Тест 3: Санитизация данных
    print(f"\n{'='*60}")
    print("Testing Data Sanitization")
    print("="*60)
    
    sensitive_data = """
    API_KEY=sk-1234567890abcdef
    password=mysecret123
    email=user@example.com
    token=jwt.token.here
    """
    
    sanitized = adapter.sanitize_for_openai(sensitive_data)
    print("Original data contains sensitive info")
    print(f"Sanitized: {sanitized}")
    print(f"Contains API key: {'❌' if 'sk-1234567890abcdef' not in sanitized else '✅'}")
    
    # Тест 4: Метрики
    print(f"\n{'='*60}")
    print("Testing Metrics")
    print("="*60)
    
    metrics = adapter.get_metrics()
    print(f"Calls today: {metrics['calls_today']}")
    print(f"Total cost: ${metrics['total_cost']:.4f}")
    print(f"Cost per call: ${metrics['cost_per_call']:.4f}")
    
    print(f"\n{'='*60}")
    print("All tests completed!")
    print("="*60)


def test_prompt_generation():
    """Тест генерации промпта"""
    
    adapter = DirectorAdapter()
    
    request = DirectorRequest(
        problem_summary="Implement JWT authentication for API endpoints",
        facts=[
            "Current API has no authentication",
            "Multiple sensitive endpoints exposed",
            "Security audit flagged this as critical"
        ],
        agent_summaries={
            "security": "Recommends JWT with refresh tokens and rate limiting",
            "dev": "Suggests FastAPI middleware implementation",
            "architect": "Proposes microservice auth pattern"
        },
        risk_level=RiskLevel.HIGH,
        confidence=0.65
    )
    
    prompt = adapter.create_director_prompt(request)
    
    print("Generated Director Prompt:")
    print("="*60)
    print(prompt)
    print("="*60)
    
    # Проверяем что промпт содержит нужные элементы
    checks = [
        ("Task summary", "JWT authentication" in prompt),
        ("Facts included", "Security audit" in prompt),
        ("Agent summaries", "FastAPI middleware" in prompt),
        ("Risk level", "HIGH" in prompt),
        ("JSON format", "JSON format" in prompt),
    ]
    
    print("\nPrompt validation:")
    for check_name, passed in checks:
        print(f"  {check_name}: {'✅' if passed else '❌'}")


if __name__ == "__main__":
    test_director_logic()
    print("\n")
    test_prompt_generation()