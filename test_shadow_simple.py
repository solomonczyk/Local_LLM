#!/usr/bin/env python3
"""
Простой тест Shadow Director с мок данными
"""

import os
import json
from agent_system.shadow_director import ShadowDirector


def create_mock_consilium_result(task_id: int, task: str, domains: list):
    """Создаёт мок результат consilium"""
    
    opinions = {}
    for domain in domains:
        opinions[domain] = {
            "role": f"{domain.title()} Specialist",
            "opinion": f"Mock {domain} opinion for task: {task[:50]}... Recommendation: implement with best practices."
        }
    
    return {
        "task": task,
        "mode": "STANDARD" if len(domains) > 1 else "FAST",
        "opinions": opinions,
        "director_decision": None,
        "recommendation": f"Mock recommendation for {task[:30]}...",
        "routing": {
            "smart_routing": True,
            "confidence": 0.7 if "security" in domains else 0.8,
            "domains_matched": len(domains),
            "triggers_matched": {domain: ["mock_trigger"] for domain in domains},
            "downgraded": False,
            "reason": f"Task involves {', '.join(domains)} domains"
        },
        "timing": {
            "agents_parallel": 10.0 + task_id,
            "director": 0.0,
            "total": 10.0 + task_id
        },
        "kb_retrieval": {
            "config": {"top_k": 3, "max_chars": 6000},
            "per_agent": {domain: {"chunks_used": 2, "chars_used": 800} for domain in domains}
        }
    }


def run_10_shadow_tests():
    """Запускает 10 тестов shadow director"""
    
    print("="*60)
    print("Running 10 Shadow Director Tests")
    print("="*60)
    
    # Проверяем настройки
    shadow_enabled = os.getenv("SHADOW_DIRECTOR_ENABLED", "false").lower() == "true"
    openai_key = os.getenv("OPENAI_API_KEY", "")
    
    print(f"Shadow Director Enabled: {shadow_enabled}")
    print(f"OpenAI Key Set: {'Yes' if openai_key else 'No'}")
    
    if not shadow_enabled or not openai_key:
        print("❌ Shadow Director not properly configured")
        return
    
    # 10 разнообразных задач
    test_tasks = [
        {
            "task_id": 1,
            "task": "Implement JWT authentication with refresh tokens and rate limiting for API security",
            "domains": ["security", "dev"]
        },
        {
            "task_id": 2, 
            "task": "Create database migration to add user roles and permissions with proper indexing",
            "domains": ["architect", "dev", "security"]
        },
        {
            "task_id": 3,
            "task": "Add Stripe payment processing with webhook handling and fraud detection",
            "domains": ["dev", "security"]
        },
        {
            "task_id": 4,
            "task": "Fix responsive button alignment in user profile page for mobile devices",
            "domains": ["ux", "dev"]
        },
        {
            "task_id": 5,
            "task": "Perform comprehensive security audit of all API endpoints and authentication flows",
            "domains": ["security", "architect"]
        },
        {
            "task_id": 6,
            "task": "Optimize database queries for user dashboard with caching strategy",
            "domains": ["architect", "dev"]
        },
        {
            "task_id": 7,
            "task": "Implement automated testing suite with unit and integration tests",
            "domains": ["qa", "dev"]
        },
        {
            "task_id": 8,
            "task": "Design SEO-friendly URL structure and meta tags for better search ranking",
            "domains": ["seo", "architect"]
        },
        {
            "task_id": 9,
            "task": "Create user onboarding flow with progressive disclosure and accessibility",
            "domains": ["ux", "dev", "qa"]
        },
        {
            "task_id": 10,
            "task": "Set up CI/CD pipeline with automated deployment and rollback capabilities",
            "domains": ["architect", "dev", "security"]
        }
    ]
    
    shadow = ShadowDirector(enabled=True)
    results = []
    
    for test_case in test_tasks:
        print(f"\n--- Test {test_case['task_id']}: {test_case['domains']} ---")
        print(f"Task: {test_case['task'][:60]}...")
        
        try:
            # Создаём мок результат consilium
            mock_result = create_mock_consilium_result(
                test_case['task_id'],
                test_case['task'], 
                test_case['domains']
            )
            
            # Запускаем shadow анализ
            shadow_result = shadow.run_shadow_analysis(mock_result)
            
            if shadow_result and shadow_result.get('shadow_director_used'):
                director_response = shadow_result.get('director_response', {})
                print(f"✅ Director used: confidence={director_response.get('confidence', 0):.2f}")
                print(f"   Decision: {director_response.get('decision', 'N/A')[:60]}...")
                print(f"   Risks: {len(director_response.get('risks', []))}")
                print(f"   Cost: ${shadow_result.get('metrics', {}).get('total_cost', 0):.4f}")
            else:
                print(f"❌ Director not used: {shadow_result.get('reason', 'Unknown') if shadow_result else 'Error'}")
            
            results.append({
                'task_id': test_case['task_id'],
                'domains': test_case['domains'],
                'shadow_used': shadow_result.get('shadow_director_used', False) if shadow_result else False,
                'success': shadow_result is not None
            })
            
        except Exception as e:
            print(f"❌ Error: {e}")
            results.append({
                'task_id': test_case['task_id'],
                'domains': test_case['domains'],
                'error': str(e),
                'success': False
            })
    
    # Статистика
    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print("="*60)
    
    successful = sum(1 for r in results if r.get('success', False))
    shadow_used = sum(1 for r in results if r.get('shadow_used', False))
    
    print(f"Tests completed: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Shadow Director used: {shadow_used}")
    
    # Проверяем логи
    if os.path.exists('shadow_director.jsonl'):
        print(f"\nShadow logs created: shadow_director.jsonl")
        
        # Показываем последние записи
        with open('shadow_director.jsonl', 'r', encoding='utf-8') as f:
            lines = f.readlines()
            print(f"Total log entries: {len(lines)}")
            
            if lines:
                print(f"\nLast log entry (sample):")
                last_entry = json.loads(lines[-1])
                safe_entry = {
                    "task_id": "redacted",
                    "consilium_confidence": last_entry.get("consilium_confidence"),
                    "consilium_agents": last_entry.get("consilium_agents"),
                    "shadow_director_used": last_entry.get("shadow_director", {}).get("shadow_director_used"),
                    "director_confidence": last_entry.get("shadow_director", {}).get("director_response", {}).get("confidence"),
                    "cost": last_entry.get("shadow_director", {}).get("metrics", {}).get("total_cost")
                }
                print(json.dumps(safe_entry, indent=2))
    else:
        print("❌ No shadow logs found")


if __name__ == "__main__":
    run_10_shadow_tests()