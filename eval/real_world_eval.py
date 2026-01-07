#!/usr/bin/env python3
"""
Оценка LoRA модели на реальных задачах из проекта
"""

import json
import time
import ast
import re
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

MODEL_ID = "Qwen/Qwen2.5-Coder-1.5B"
LORA_PATH = "lora_qwen2_5_coder_1_5b_python"


def load_model():
    """Загрузка модели с LoRA"""
    print("Loading model...")
    
    tokenizer = AutoTokenizer.from_pretrained(LORA_PATH, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        device_map="cpu",
        trust_remote_code=True,
        torch_dtype=torch.float32,
        low_cpu_mem_usage=True,
    )
    
    model = PeftModel.from_pretrained(model, LORA_PATH)
    model.eval()
    
    return model, tokenizer


def generate_code(model, tokenizer, prompt, max_tokens=200):
    """Генерация кода"""
    inputs = tokenizer(prompt, return_tensors="pt")
    
    start_time = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=0.3,  # Более детерминированная генерация
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id,
        )
    gen_time = time.time() - start_time
    
    generated = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return generated, gen_time


def check_syntax(code):
    """Проверка синтаксиса Python"""
    try:
        ast.parse(code)
        return True, "Valid syntax"
    except SyntaxError as e:
        return False, f"Syntax error: {e}"


def analyze_code_quality(code, task_id):
    """Анализ качества кода для конкретной задачи"""
    issues = []
    
    # Общие проверки
    if len(code.strip()) < 50:
        issues.append("Code too short")
    
    if "pass" in code and len(code.strip()) < 100:
        issues.append("Placeholder implementation")
    
    # Специфичные проверки по задачам
    if task_id == "agent_health_check":
        if "return" not in code:
            issues.append("Missing return statement")
        if "dict" not in code and "{" not in code:
            issues.append("Should return dict")
    
    elif task_id == "circuit_breaker_pattern":
        if "self." not in code:
            issues.append("Missing instance variables")
        if "state" not in code.lower():
            issues.append("Missing state management")
    
    elif task_id == "sql_injection_validator":
        dangerous_patterns = ["drop", "delete", "union", "--", "/*"]
        if not any(pattern in code.lower() for pattern in dangerous_patterns):
            issues.append("Missing SQL injection checks")
    
    elif task_id == "rate_limiter_decorator":
        if "@" not in code or "def " not in code:
            issues.append("Not a proper decorator")
    
    elif task_id == "log_sanitizer":
        if "re" not in code and "replace" not in code:
            issues.append("Missing pattern matching for sanitization")
    
    return issues


def evaluate_task(model, tokenizer, task):
    """Оценка одной задачи"""
    print(f"\n{'='*60}")
    print(f"Task: {task['id']} ({task['domain']})")
    print(f"{'='*60}")
    print(f"Prompt:\n{task['prompt'][:200]}...")
    
    # Генерация
    generated, gen_time = generate_code(model, tokenizer, task['prompt'])
    
    # Извлекаем только новый код (после промпта)
    new_code = generated[len(task['prompt']):].strip()
    full_code = task['prompt'] + "\n" + new_code
    
    print(f"\nGenerated ({gen_time:.1f}s):")
    print("-" * 40)
    print(new_code)
    print("-" * 40)
    
    # Проверки
    syntax_ok, syntax_msg = check_syntax(full_code)
    quality_issues = analyze_code_quality(full_code, task['id'])
    
    # Оценка
    score = 0
    if syntax_ok:
        score += 3  # Синтаксис корректен
    if len(quality_issues) == 0:
        score += 2  # Нет проблем качества
    if len(new_code) > 100:
        score += 1  # Достаточно кода
    
    result = {
        'task_id': task['id'],
        'domain': task['domain'],
        'generated_code': new_code,
        'full_code': full_code,
        'generation_time': gen_time,
        'syntax_valid': syntax_ok,
        'syntax_message': syntax_msg,
        'quality_issues': quality_issues,
        'score': score,
        'max_score': 6
    }
    
    print(f"\nEvaluation:")
    print(f"  Syntax: {'✅' if syntax_ok else '❌'} {syntax_msg}")
    print(f"  Quality issues: {len(quality_issues)}")
    for issue in quality_issues:
        print(f"    - {issue}")
    print(f"  Score: {score}/6")
    
    return result


def main():
    print("Real-World Task Evaluation")
    print("="*60)
    
    # Загрузка задач
    tasks = []
    with open('eval/tasks.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            tasks.append(json.loads(line))
    
    print(f"Loaded {len(tasks)} tasks")
    
    # Загрузка модели
    model, tokenizer = load_model()
    
    # Оценка всех задач
    results = []
    for task in tasks:
        result = evaluate_task(model, tokenizer, task)
        results.append(result)
    
    # Итоговая статистика
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    
    total_score = sum(r['score'] for r in results)
    max_total = sum(r['max_score'] for r in results)
    
    syntax_ok = sum(1 for r in results if r['syntax_valid'])
    avg_time = sum(r['generation_time'] for r in results) / len(results)
    
    print(f"Overall Score: {total_score}/{max_total} ({total_score/max_total*100:.1f}%)")
    print(f"Syntax Valid: {syntax_ok}/{len(results)} ({syntax_ok/len(results)*100:.1f}%)")
    print(f"Avg Generation Time: {avg_time:.1f}s")
    
    # По доменам
    domains = {}
    for result in results:
        domain = result['domain']
        if domain not in domains:
            domains[domain] = {'count': 0, 'score': 0, 'max_score': 0}
        domains[domain]['count'] += 1
        domains[domain]['score'] += result['score']
        domains[domain]['max_score'] += result['max_score']
    
    print(f"\nBy Domain:")
    for domain, stats in domains.items():
        pct = stats['score'] / stats['max_score'] * 100
        print(f"  {domain}: {stats['score']}/{stats['max_score']} ({pct:.1f}%)")
    
    # Сохранение результатов
    with open('eval/real_world_results.json', 'w', encoding='utf-8') as f:
        json.dump({
            'summary': {
                'total_score': total_score,
                'max_score': max_total,
                'percentage': total_score/max_total*100,
                'syntax_valid': syntax_ok,
                'total_tasks': len(results),
                'avg_time': avg_time,
                'domains': domains
            },
            'results': results,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\nDetailed results saved to eval/real_world_results.json")


if __name__ == "__main__":
    main()