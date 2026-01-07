#!/usr/bin/env python3
"""
Тест Circuit Breaker для Director
"""

import os
import json
import time
from agent_system.director_circuit_breaker import DirectorCircuitBreaker


def test_circuit_breaker():
    """Тестирует circuit breaker с различными сценариями"""
    
    print("="*60)
    print("Testing Director Circuit Breaker")
    print("="*60)
    
    # Создаём новый circuit breaker для тестирования
    cb = DirectorCircuitBreaker()
    
    print(f"Initial mode: {cb.current_mode}")
    print(f"Limits: {cb.limits}")
    
    # Сценарий 1: Нормальная работа (должна остаться в active)
    print(f"\n--- Scenario 1: Normal Operation ---")
    for i in range(10):
        cb.record_director_call(
            override_applied=(i % 3 == 0),  # 33% override rate
            director_cost=0.0001,  # Низкая стоимость
            director_latency=2.5,  # Нормальная latency
            director_error=False,
            confidence_diff=0.15
        )
    
    status = cb.get_current_status()
    print(f"After normal calls: mode={cb.current_mode}")
    print(f"Rolling metrics: {json.dumps(status['rolling_metrics'], indent=2)}")
    
    # Сценарий 2: Высокий override rate (должен trigger rollback)
    print(f"\n--- Scenario 2: High Override Rate ---")
    for i in range(15):
        cb.record_director_call(
            override_applied=True,  # 100% override rate
            director_cost=0.0001,
            director_latency=2.0,
            director_error=False,
            confidence_diff=0.05
        )
    
    status = cb.get_current_status()
    print(f"After high override rate: mode={cb.current_mode}")
    print(f"Rolling metrics: {json.dumps(status['rolling_metrics'], indent=2)}")
    
    # Сценарий 3: Высокая стоимость (должен trigger rollback если ещё не сработал)
    print(f"\n--- Scenario 3: High Cost ---")
    for i in range(5):
        cb.record_director_call(
            override_applied=False,
            director_cost=0.005,  # Высокая стоимость
            director_latency=1.5,
            director_error=False,
            confidence_diff=0.10
        )
    
    status = cb.get_current_status()
    print(f"After high cost: mode={cb.current_mode}")
    print(f"Rolling metrics: {json.dumps(status['rolling_metrics'], indent=2)}")
    
    # Сценарий 4: Высокие ошибки
    print(f"\n--- Scenario 4: High Error Rate ---")
    for i in range(10):
        cb.record_director_call(
            override_applied=False,
            director_cost=0.0001,
            director_latency=1.0,
            director_error=(i % 2 == 0),  # 50% error rate
            confidence_diff=0.0
        )
    
    status = cb.get_current_status()
    print(f"After high errors: mode={cb.current_mode}")
    print(f"Rolling metrics: {json.dumps(status['rolling_metrics'], indent=2)}")
    
    # Сценарий 5: Высокая latency
    print(f"\n--- Scenario 5: High Latency ---")
    for i in range(10):
        cb.record_director_call(
            override_applied=False,
            director_cost=0.0001,
            director_latency=8.0,  # Высокая latency
            director_error=False,
            confidence_diff=0.10
        )
    
    status = cb.get_current_status()
    print(f"After high latency: mode={cb.current_mode}")
    print(f"Rolling metrics: {json.dumps(status['rolling_metrics'], indent=2)}")
    
    # Финальный статус
    print(f"\n--- Final Status ---")
    final_status = cb.get_current_status()
    print(f"Final mode: {cb.current_mode}")
    print(f"Total calls: {final_status['total_calls']}")
    print(f"Health: {final_status['health']}")
    
    # Проверяем логи
    if os.path.exists(cb.log_file):
        print(f"\nCircuit breaker logs created: {cb.log_file}")
        
        with open(cb.log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            print(f"Total log entries: {len(lines)}")
            
            # Показываем последние события
            print(f"\nLast 3 events:")
            for line in lines[-3:]:
                event = json.loads(line)
                if event.get("event") == "director_mode_change":
                    print(f"  MODE CHANGE: {event['old_mode']} → {event['new_mode']} ({event['reason']})")
                elif event.get("event") == "circuit_breaker_check":
                    decision = event.get("decision", "unknown")
                    violations = event.get("violations", [])
                    print(f"  CHECK: {decision} (violations: {len(violations)})")
    
    # Тестируем should_use_director
    print(f"\n--- Director Usage Test ---")
    use_director, reason = cb.should_use_director()
    print(f"Should use director: {use_director} ({reason})")
    
    return cb


def simulate_production_scenario():
    """Симулирует production сценарий с постепенной деградацией"""
    
    print(f"\n{'='*60}")
    print("Simulating Production Scenario")
    print("="*60)
    
    cb = DirectorCircuitBreaker()
    
    # Устанавливаем active mode принудительно
    cb.current_mode = "active"
    
    print("Phase 1: Healthy operation (10 calls)")
    for i in range(10):
        cb.record_director_call(
            override_applied=(i % 4 == 0),  # 25% override
            director_cost=0.0001,
            director_latency=2.0,
            director_error=False,
            confidence_diff=0.15
        )
        time.sleep(0.1)  # Небольшая задержка
    
    status = cb.get_current_status()
    print(f"After phase 1: mode={cb.current_mode}, health={status['health']}")
    
    print("\nPhase 2: Gradual degradation (15 calls)")
    for i in range(15):
        # Постепенно увеличиваем override rate и latency
        override_rate = 0.3 + (i * 0.04)  # От 30% до 86%
        latency = 2.0 + (i * 0.3)  # От 2s до 6.4s
        
        cb.record_director_call(
            override_applied=(i / 15) < override_rate,
            director_cost=0.0001 + (i * 0.00005),  # Растущая стоимость
            director_latency=latency,
            director_error=(i > 10 and i % 5 == 0),  # Ошибки в конце
            confidence_diff=0.10 - (i * 0.005)  # Падающая эффективность
        )
        time.sleep(0.1)
        
        # Показываем когда сработал circuit breaker
        if cb.current_mode != "active":
            print(f"  Circuit breaker triggered at call {i+1}")
            break
    
    final_status = cb.get_current_status()
    print(f"After phase 2: mode={cb.current_mode}, health={final_status['health']}")
    
    # Показываем финальные метрики
    metrics = final_status.get('rolling_metrics', {})
    print(f"\nFinal rolling metrics:")
    print(f"  Override rate (last 20): {metrics.get('override_rate_20', 0):.2f}")
    print(f"  Error rate (last 20): {metrics.get('error_rate_20', 0):.2f}")
    print(f"  Avg latency (last 20): {metrics.get('avg_latency_20', 0):.1f}s")
    print(f"  Daily cost: ${metrics.get('daily_cost', 0):.4f}")
    
    return cb


if __name__ == "__main__":
    # Основной тест
    cb1 = test_circuit_breaker()
    
    # Production сценарий
    cb2 = simulate_production_scenario()
    
    print(f"\n{'='*60}")
    print("CIRCUIT BREAKER TEST COMPLETE")
    print("="*60)
    print("Check director_circuit_breaker.jsonl for detailed logs")