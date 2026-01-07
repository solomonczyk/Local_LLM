#!/usr/bin/env python3
"""
Запуск реальных задач через consilium с shadow director
"""

import os
import sys
import json
from agent_runtime.orchestrator.consilium import get_consilium


def test_real_tasks_with_shadow():
    """Тестирует реальные задачи с shadow director"""
    
    print("="*60)
    print("Real Tasks with Shadow Director")
    print("="*60)
    
    # Проверяем настройки
    shadow_enabled = os.getenv("SHADOW_DIRECTOR_ENABLED", "false").lower() == "true"
    openai_key = os.getenv("OPENAI_API_KEY", "")
    
    print(f"Shadow Director Enabled: {shadow_enabled}")
    print(f"OpenAI Key Set: {'Yes' if openai_key else 'No'}")
    
    if not shadow_enabled:
        print("\n⚠️  Shadow Director disabled. Set SHADOW_DIRECTOR_ENABLED=true to enable.")
        print("Running without shadow mode...")
    
    # Тестовые задачи из нашего eval
    test_tasks = [
        {
            "name": "JWT Authentication",
            "task": "Implement JWT authentication for API endpoints with refresh tokens and rate limiting",
            "expected_triggers": ["security", "auth"]
        },
        {
            "name": "Database Migration", 
            "task": "Create database migration to add user roles and permissions table",
            "expected_triggers": ["migration", "database"]
        },
        {
            "name": "Payment Processing",
            "task": "Add payment processing with Stripe integration and webhook handling",
            "expected_triggers": ["payment"]
        },
        {
            "name": "Simple UI Fix",
            "task": "Fix button alignment in the user profile page",
            "expected_triggers": []  # Should not trigger Director
        },
        {
            "name": "Security Audit",
            "task": "Perform security audit of API endpoints and fix vulnerabilities",
            "expected_triggers": ["security", "vuln"]
        }
    ]
    
    consilium = get_consilium()
    results = []
    
    for i, test_case in enumerate(test_tasks, 1):
        print(f"\n{'='*60}")
        print(f"Test {i}: {test_case['name']}")
        print("="*60)
        print(f"Task: {test_case['task']}")
        
        try:
            # Запускаем consilium с shadow director
            result = consilium.consult(
                test_case['task'],
                use_smart_routing=True,
                check_health=False  # Отключаем health check для тестирования
            )
            
            # Анализируем результат
            shadow_info = result.get("shadow_director", {})
            routing_info = result.get("routing", {})
            
            print(f"\nConsilium Result:")
            print(f"  Mode: {result.get('mode')}")
            print(f"  Agents: {list(result.get('opinions', {}).keys())}")
            print(f"  Confidence: {routing_info.get('confidence', 'N/A')}")
            print(f"  Timing: {result.get('timing', {}).get('total', 0)}s")
            
            if shadow_info:
                print(f"\nShadow Director:")
                print(f"  Used: {shadow_info.get('shadow_director_used', False)}")
                
                if shadow_info.get('shadow_director_used'):
                    director_response = shadow_info.get('director_response', {})
                    print(f"  Decision: {director_response.get('decision', 'N/A')[:80]}...")
                    print(f"  Confidence: {director_response.get('confidence', 'N/A')}")
                    print(f"  Risks: {len(director_response.get('risks', []))}")
                    print(f"  Timing: {shadow_info.get('timing', {}).get('director_call', 0)}s")
                    
                    # Проверяем метрики
                    metrics = shadow_info.get('metrics', {})
                    print(f"  Cost: ${metrics.get('total_cost', 0):.4f}")
                else:
                    print(f"  Reason: {shadow_info.get('reason', 'N/A')}")
            else:
                print(f"\nShadow Director: Not available (disabled or error)")
            
            # Сохраняем результат для анализа
            results.append({
                'test_name': test_case['name'],
                'task': test_case['task'],
                'expected_triggers': test_case['expected_triggers'],
                'consilium_mode': result.get('mode'),
                'consilium_agents': list(result.get('opinions', {}).keys()),
                'consilium_confidence': routing_info.get('confidence'),
                'consilium_timing': result.get('timing', {}),
                'shadow_used': shadow_info.get('shadow_director_used', False),
                'shadow_reason': shadow_info.get('reason', ''),
                'director_confidence': shadow_info.get('director_response', {}).get('confidence'),
                'director_timing': shadow_info.get('timing', {}).get('director_call', 0),
                'cost': shadow_info.get('metrics', {}).get('total_cost', 0)
            })
            
        except Exception as e:
            print(f"❌ Error: {e}")
            results.append({
                'test_name': test_case['name'],
                'error': str(e)
            })
    
    # Итоговая статистика
    print(f"\n{'='*60}")
    print("SUMMARY")
    print("="*60)
    
    successful_tests = [r for r in results if 'error' not in r]
    shadow_used_count = sum(1 for r in successful_tests if r.get('shadow_used'))
    total_cost = sum(r.get('cost', 0) for r in successful_tests)
    
    print(f"Tests completed: {len(results)}")
    print(f"Successful: {len(successful_tests)}")
    print(f"Shadow Director used: {shadow_used_count}/{len(successful_tests)}")
    print(f"Total cost: ${total_cost:.4f}")
    
    if successful_tests:
        avg_consilium_time = sum(r.get('consilium_timing', {}).get('total', 0) for r in successful_tests) / len(successful_tests)
        avg_director_time = sum(r.get('director_timing', 0) for r in successful_tests if r.get('shadow_used')) / max(1, shadow_used_count)
        
        print(f"Avg consilium time: {avg_consilium_time:.1f}s")
        if shadow_used_count > 0:
            print(f"Avg director time: {avg_director_time:.1f}s")
    
    # Сохраняем результаты
    with open('shadow_test_results.json', 'w', encoding='utf-8') as f:
        json.dump({
            'summary': {
                'total_tests': len(results),
                'successful': len(successful_tests),
                'shadow_used': shadow_used_count,
                'total_cost': total_cost,
                'shadow_enabled': shadow_enabled
            },
            'results': results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to shadow_test_results.json")
    
    # Показываем пример лога
    if shadow_used_count > 0:
        print(f"\n{'='*60}")
        print("EXAMPLE SHADOW LOG")
        print("="*60)
        
        shadow_result = next(r for r in successful_tests if r.get('shadow_used'))
        safe_log = {
            "test_name": shadow_result['test_name'],
            "consilium_mode": shadow_result['consilium_mode'],
            "consilium_confidence": shadow_result['consilium_confidence'],
            "consilium_agents": shadow_result['consilium_agents'],
            "shadow_director_used": True,
            "director_confidence": shadow_result['director_confidence'],
            "timing_comparison": {
                "consilium_total": shadow_result['consilium_timing'].get('total', 0),
                "director_call": shadow_result['director_timing']
            },
            "cost": shadow_result['cost']
        }
        
        print(json.dumps(safe_log, indent=2))


if __name__ == "__main__":
    test_real_tasks_with_shadow()