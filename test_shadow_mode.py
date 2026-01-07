#!/usr/bin/env python3
"""
Тест Shadow Director Mode
Проверяет работу shadow mode без реального вызова OpenAI
"""

import os
import json
from agent_system.shadow_director import ShadowDirector


def test_shadow_mode():
    """Тест shadow mode с мок данными"""
    
    print("="*60)
    print("Testing Shadow Director Mode")
    print("="*60)
    
    # Создаём shadow director (без реального API)
    shadow = ShadowDirector(enabled=True)
    
    # Мок результат от consilium
    mock_consilium_result = {
        "task": "Implement JWT authentication for API endpoints with refresh tokens",
        "mode": "STANDARD",
        "opinions": {
            "security": {
                "role": "Security Specialist",
                "opinion": "Recommend implementing JWT with RS256 algorithm, short-lived access tokens (15 min), refresh tokens with rotation, rate limiting on auth endpoints, and secure storage of refresh tokens. Consider implementing proper token blacklisting mechanism."
            },
            "dev": {
                "role": "Developer", 
                "opinion": "Suggest using FastAPI dependency injection for auth middleware. Create auth decorators for different permission levels. Use Pydantic models for token validation. Implement proper error handling and logging for auth failures."
            },
            "architect": {
                "role": "Software Architect",
                "opinion": "Propose microservice auth pattern with centralized auth service. Consider OAuth2 flow for third-party integrations. Design token storage strategy (Redis for refresh tokens). Plan for horizontal scaling of auth service."
            }
        },
        "director_decision": None,
        "recommendation": "Implement JWT authentication with security best practices",
        "routing": {
            "smart_routing": True,
            "confidence": 0.65,
            "domains_matched": 3,
            "triggers_matched": {"security": ["auth", "jwt"], "dev": ["api"], "architect": ["service"]},
            "downgraded": False,
            "reason": "Security-related task with multiple domain expertise needed"
        },
        "timing": {
            "agents_parallel": 12.5,
            "director": 0.0,
            "total": 12.5
        },
        "kb_retrieval": {
            "config": {"top_k": 5, "max_chars": 6000},
            "per_agent": {
                "security": {"chunks_used": 3, "chars_used": 1200},
                "dev": {"chunks_used": 2, "chars_used": 800}
            }
        }
    }
    
    # Тест 1: Создание саммари
    print("1. Testing summary creation...")
    director_request = shadow.create_summary_from_consilium_result(mock_consilium_result)
    
    if director_request:
        print("✅ Summary created successfully")
        print(f"   Problem: {director_request.problem_summary[:100]}...")
        print(f"   Risk Level: {director_request.risk_level.value}")
        print(f"   Confidence: {director_request.confidence}")
        print(f"   Facts: {len(director_request.facts)}")
        print(f"   Agent Summaries: {len(director_request.agent_summaries)}")
    else:
        print("❌ Failed to create summary")
        return
    
    # Тест 2: Проверка триггеров
    print(f"\n2. Testing triggers...")
    task = mock_consilium_result["task"]
    confidence = mock_consilium_result["routing"]["confidence"]
    domains = list(mock_consilium_result["opinions"].keys())
    
    should_use = shadow.director_adapter.should_use_director(task, confidence, domains)
    print(f"   Task: {task[:50]}...")
    print(f"   Confidence: {confidence}")
    print(f"   Domains: {domains}")
    print(f"   Should use Director: {'✅' if should_use else '❌'}")
    
    # Тест 3: Мок shadow анализа (без реального API вызова)
    print(f"\n3. Testing shadow analysis (mock)...")
    
    # Создаём мок ответ Director
    mock_shadow_result = {
        "shadow_director_used": True,
        "director_request": {
            "problem_summary": director_request.problem_summary,
            "risk_level": director_request.risk_level.value,
            "confidence": director_request.confidence
        },
        "director_response": {
            "decision": "Implement JWT auth with RS256, 15min access tokens, refresh token rotation",
            "risks": ["Token storage security", "Refresh token leakage", "Rate limiting bypass"],
            "recommendations": ["Use Redis for token storage", "Implement proper logging", "Add monitoring"],
            "next_step": "Create auth service with FastAPI and JWT middleware",
            "confidence": 0.85,
            "reasoning": "Security-critical task requires robust authentication with industry best practices"
        },
        "timing": {"director_call": 1.2},
        "metrics": {"calls_today": 1, "total_cost": 0.0003}
    }
    
    print("✅ Mock shadow analysis completed")
    print(f"   Director Decision: {mock_shadow_result['director_response']['decision'][:60]}...")
    print(f"   Director Confidence: {mock_shadow_result['director_response']['confidence']}")
    print(f"   Risks identified: {len(mock_shadow_result['director_response']['risks'])}")
    print(f"   Recommendations: {len(mock_shadow_result['director_response']['recommendations'])}")
    
    # Тест 4: Сравнение результатов
    print(f"\n4. Testing result comparison...")
    comparison = shadow.compare_results(mock_consilium_result, mock_shadow_result)
    
    print("✅ Comparison completed")
    print(f"   Consilium length: {comparison.get('consilium_length', 0)} chars")
    print(f"   Director length: {comparison.get('director_length', 0)} chars")
    print(f"   Security focus alignment: {comparison.get('security_focus', {}).get('alignment', False)}")
    
    # Тест 5: Логирование (мок)
    print(f"\n5. Testing logging...")
    
    log_entry = {
        "timestamp": "2026-01-07 14:00:00",
        "task": mock_consilium_result["task"][:100],
        "consilium_mode": mock_consilium_result["mode"],
        "consilium_confidence": mock_consilium_result["routing"]["confidence"],
        "consilium_agents": list(mock_consilium_result["opinions"].keys()),
        "shadow_director": mock_shadow_result,
        "comparison": comparison
    }
    
    print("✅ Log entry created")
    print(f"   Timestamp: {log_entry['timestamp']}")
    print(f"   Task: {log_entry['task'][:50]}...")
    print(f"   Consilium agents: {log_entry['consilium_agents']}")
    
    # Показываем пример лога (сокращённый)
    print(f"\n{'='*60}")
    print("EXAMPLE SHADOW LOG (shortened for security)")
    print("="*60)
    
    safe_log = {
        "timestamp": log_entry["timestamp"],
        "task": "[TASK_SUMMARY_REDACTED]",
        "consilium_mode": log_entry["consilium_mode"],
        "consilium_confidence": log_entry["consilium_confidence"],
        "consilium_agents": log_entry["consilium_agents"],
        "consilium_timing": mock_consilium_result["timing"],
        "shadow_director": {
            "shadow_director_used": True,
            "director_confidence": mock_shadow_result["director_response"]["confidence"],
            "director_risks_count": len(mock_shadow_result["director_response"]["risks"]),
            "director_recommendations_count": len(mock_shadow_result["director_response"]["recommendations"]),
            "timing": mock_shadow_result["timing"],
            "cost_estimate": mock_shadow_result["metrics"]["total_cost"]
        },
        "comparison": {
            "consilium_length": comparison.get("consilium_length", 0),
            "director_length": comparison.get("director_length", 0),
            "security_alignment": comparison.get("security_focus", {}).get("alignment", False)
        }
    }
    
    print(json.dumps(safe_log, indent=2))
    
    print(f"\n{'='*60}")
    print("Shadow Mode Test Completed Successfully! ✅")
    print("="*60)
    print("Next steps:")
    print("1. Set OPENAI_API_KEY in environment")
    print("2. Set SHADOW_DIRECTOR_ENABLED=true")
    print("3. Run real tasks through consilium")
    print("4. Check shadow_director.jsonl for logs")
    print("5. Compare consilium vs director decisions")


if __name__ == "__main__":
    test_shadow_mode()