#!/usr/bin/env python3
"""
Тест Active Director Mode с override gating
"""

import os
import json
from agent_system.active_director import ActiveDirector


def create_test_consilium_result(task: str, confidence: float, domains: list, security_task: bool = False):
    """Создаёт тестовый результат consilium"""
    
    opinions = {}
    for domain in domains:
        opinions[domain] = {
            "role": f"{domain.title()} Specialist",
            "opinion": f"Mock {domain} opinion for task: {task[:50]}... Recommendation: implement with best practices."
        }
    
    return {
        "task": task,
        "mode": "STANDARD",
        "opinions": opinions,
        "director_decision": None,
        "recommendation": f"Mock consilium recommendation for {task[:30]}...",
        "routing": {
            "smart_routing": True,
            "confidence": confidence,
            "domains_matched": len(domains),
            "triggers_matched": {domain: ["mock_trigger"] for domain in domains},
            "downgraded": False,
            "reason": f"Task involves {', '.join(domains)} domains"
        },
        "timing": {
            "agents_parallel": 10.0,
            "director": 0.0,
            "total": 10.0
        },
        "kb_retrieval": {
            "config": {"top_k": 3, "max_chars": 6000},
            "per_agent": {domain: {"chunks_used": 2, "chars_used": 800} for domain in domains}
        }
    }


def test_active_mode():
    """Тестирует Active Mode с разными сценариями override"""
    
    print("="*60)
    print("Testing Active Director Mode with Override Gating")
    print("="*60)
    
    # Проверяем настройки
    active_enabled = os.getenv("DIRECTOR_ACTIVE_MODE", "false").lower() == "true"
    openai_key = os.getenv("OPENAI_API_KEY", "")
    
    print(f"Active Director Enabled: {active_enabled}")
    print(f"OpenAI Key Set: {'Yes' if openai_key else 'No'}")
    
    if not active_enabled or not openai_key:
        print("❌ Active Director not properly configured")
        print("Set DIRECTOR_ACTIVE_MODE=true and OPENAI_API_KEY")
        return
    
    # Тестовые сценарии
    test_cases = [
        {
            "name": "High Risk Security Task",
            "task": "Implement JWT authentication with refresh tokens",
            "confidence": 0.7,
            "domains": ["security", "dev"],
            "expected_override": True,
            "expected_reason": "high_risk"
        },
        {
            "name": "Low Confidence Task", 
            "task": "Optimize database queries with caching",
            "confidence": 0.65,
            "domains": ["architect", "dev"],
            "expected_override": True,
            "expected_reason": "low_consilium_confidence"
        },
        {
            "name": "Multi-domain Complex Task",
            "task": "Set up CI/CD pipeline with security and monitoring",
            "confidence": 0.75,
            "domains": ["architect", "dev", "security", "qa"],
            "expected_override": True,  # если director даст +0.10 confidence
            "expected_reason": "multi_domain_high_improvement"
        },
        {
            "name": "Simple UI Task (No Override)",
            "task": "Fix button alignment in user profile",
            "confidence": 0.85,
            "domains": ["ux", "dev"],
            "expected_override": False,
            "expected_reason": "no_override_needed"
        },
        {
            "name": "Good Consilium Result (No Override)",
            "task": "Add unit tests for user service",
            "confidence": 0.8,
            "domains": ["qa", "dev"],
            "expected_override": False,
            "expected_reason": "no_override_needed"
        }
    ]
    
    active_director = ActiveDirector(enabled=True)
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Test {i}: {test_case['name']} ---")
        print(f"Task: {test_case['task']}")
        print(f"Consilium confidence: {test_case['confidence']}")
        print(f"Domains: {test_case['domains']}")
        
        try:
            # Создаём mock consilium result
            consilium_result = create_test_consilium_result(
                test_case['task'],
                test_case['confidence'],
                test_case['domains'],
                "security" in test_case['domains']
            )
            
            # Запускаем active analysis
            result = active_director.run_active_analysis(consilium_result)
            
            active_info = result.get("active_director", {})
            
            if active_info.get("active_director_used"):
                override_applied = active_info.get("override_applied", False)
                override_reason = active_info.get("override_reason", "")
                director_confidence = active_info.get("director_response", {}).get("confidence", 0)
                
                print(f"✅ Director used: override={override_applied}")
                print(f"   Reason: {override_reason}")
                print(f"   Director confidence: {director_confidence:.2f}")
                
                if override_applied:
                    print(f"   🔄 Consilium answer REPLACED by Director")
                    print(f"   Original: {consilium_result.get('recommendation', '')[:50]}...")
                    print(f"   Director: {result.get('recommendation', '')[:50]}...")
                else:
                    print(f"   📝 Director as review only (consilium kept)")
                
                # Проверяем ожидания
                expected_override = test_case.get('expected_override', False)
                if override_applied == expected_override:
                    print(f"   ✅ Override expectation: CORRECT")
                else:
                    print(f"   ❌ Override expectation: WRONG (expected {expected_override})")
                
            else:
                reason = active_info.get("reason", "Unknown")
                print(f"❌ Director not used: {reason}")
            
            results.append({
                'test_name': test_case['name'],
                'director_used': active_info.get("active_director_used", False),
                'override_applied': active_info.get("override_applied", False),
                'override_reason': active_info.get("override_reason", ""),
                'expected_override': test_case.get('expected_override', False),
                'success': True
            })
            
        except Exception as e:
            print(f"❌ Error: {e}")
            results.append({
                'test_name': test_case['name'],
                'error': str(e),
                'success': False
            })
    
    # Статистика
    print(f"\n{'='*60}")
    print("ACTIVE MODE TEST RESULTS")
    print("="*60)
    
    successful = sum(1 for r in results if r.get('success', False))
    director_used = sum(1 for r in results if r.get('director_used', False))
    overrides_applied = sum(1 for r in results if r.get('override_applied', False))
    
    print(f"Tests completed: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Director used: {director_used}")
    print(f"Overrides applied: {overrides_applied}")
    
    # Проверяем логи
    if os.path.exists('active_director.jsonl'):
        print(f"\nActive logs created: active_director.jsonl")
        
        with open('active_director.jsonl', 'r', encoding='utf-8') as f:
            lines = f.readlines()
            print(f"Total log entries: {len(lines)}")
            
            if lines:
                print(f"\nLast log entry (sample):")
                last_entry = json.loads(lines[-1])
                safe_entry = {
                    "consilium_confidence": last_entry.get("consilium_confidence"),
                    "consilium_agents": last_entry.get("consilium_agents"),
                    "override_applied": last_entry.get("active_director", {}).get("override_applied"),
                    "override_reason": last_entry.get("active_director", {}).get("override_reason"),
                    "director_confidence": last_entry.get("active_director", {}).get("director_response", {}).get("confidence"),
                    "confidence_diff": last_entry.get("comparison", {}).get("confidence_diff"),
                    "cost": last_entry.get("active_director", {}).get("metrics", {}).get("total_cost")
                }
                print(json.dumps(safe_entry, indent=2))
    else:
        print("❌ No active logs found")


if __name__ == "__main__":
    test_active_mode()