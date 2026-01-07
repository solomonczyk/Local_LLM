#!/usr/bin/env python3
"""
Оценка LoRA модели на CPU (без квантизации)
Для машин без CUDA
"""

import os
import torch
import json
import time
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
from datasets import load_from_disk
import math

MODEL_ID = "Qwen/Qwen2.5-Coder-1.5B"
LORA_PATH = "lora_qwen2_5_coder_1_5b_python"
DATA_DIR = "codesearchnet_python_1pct_filtered"


def load_model(use_lora=True):
    """Загрузка модели на CPU"""
    print(f"Loading model on CPU (LoRA: {use_lora})...")
    print("This may take a while and use significant RAM (~6GB)...")
    
    tokenizer = AutoTokenizer.from_pretrained(
        LORA_PATH if use_lora else MODEL_ID, 
        use_fast=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # Загрузка без квантизации на CPU
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        device_map="cpu",
        trust_remote_code=True,
        torch_dtype=torch.float32,  # CPU работает лучше с float32
        low_cpu_mem_usage=True,
    )
    
    if use_lora:
        model = PeftModel.from_pretrained(model, LORA_PATH)
        print("LoRA adapter loaded!")
    
    model.eval()
    return model, tokenizer


def generate_code(model, tokenizer, prompt, max_new_tokens=100):
    """Генерация кода"""
    inputs = tokenizer(prompt, return_tensors="pt")
    
    start_time = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    gen_time = time.time() - start_time
    
    generated = tokenizer.decode(outputs[0], skip_special_tokens=True)
    new_tokens = outputs.shape[1] - inputs["input_ids"].shape[1]
    
    return generated, gen_time, new_tokens


def calculate_perplexity(model, tokenizer, texts, max_samples=20):
    """Perplexity на небольшой выборке"""
    print(f"\nCalculating perplexity on {min(len(texts), max_samples)} samples...")
    
    total_loss = 0
    total_tokens = 0
    
    for i, text in enumerate(texts[:max_samples]):
        if i % 5 == 0:
            print(f"  Processing {i}/{min(len(texts), max_samples)}...")
        
        try:
            inputs = tokenizer(
                text, 
                return_tensors="pt", 
                truncation=True, 
                max_length=256  # Меньше для CPU
            )
            
            with torch.no_grad():
                outputs = model(**inputs, labels=inputs["input_ids"])
                loss = outputs.loss.item()
                
            num_tokens = inputs["input_ids"].shape[1]
            total_loss += loss * num_tokens
            total_tokens += num_tokens
            
        except Exception as e:
            print(f"  Error: {e}")
            continue
    
    avg_loss = total_loss / total_tokens if total_tokens > 0 else float('inf')
    perplexity = math.exp(avg_loss)
    
    return perplexity, avg_loss


def main():
    print("="*60)
    print("LoRA Model Evaluation (CPU Mode)")
    print("="*60)
    print("WARNING: CPU inference is slow. Be patient!")
    print("="*60)
    
    # Тестовые кейсы (меньше токенов для CPU)
    test_cases = [
        {
            'name': 'Function definition',
            'prompt': 'def fibonacci(n):',
            'max_tokens': 80
        },
        {
            'name': 'Class definition', 
            'prompt': 'class User:\n    def __init__(self, name):',
            'max_tokens': 80
        },
        {
            'name': 'List comprehension',
            'prompt': '# Square even numbers\nnumbers = [1,2,3,4,5]\nresult =',
            'max_tokens': 50
        },
        {
            'name': 'Error handling',
            'prompt': 'def safe_read(filename):\n    try:',
            'max_tokens': 80
        },
    ]
    
    # Загружаем модель
    model, tokenizer = load_model(use_lora=True)
    
    # 1. Code completion
    print("\n" + "="*60)
    print("1. CODE COMPLETION TESTS")
    print("="*60)
    
    results = []
    for i, case in enumerate(test_cases):
        print(f"\n--- Test {i+1}: {case['name']} ---")
        print(f"Prompt: {case['prompt']}")
        
        generated, gen_time, new_tokens = generate_code(
            model, tokenizer, case['prompt'], case['max_tokens']
        )
        
        print(f"\nGenerated ({gen_time:.1f}s, {new_tokens} tokens):")
        print(generated)
        
        results.append({
            'name': case['name'],
            'prompt': case['prompt'],
            'generated': generated,
            'time': gen_time,
            'tokens': new_tokens,
            'tokens_per_sec': new_tokens / gen_time if gen_time > 0 else 0
        })
    
    # 2. Perplexity (небольшая выборка)
    print("\n" + "="*60)
    print("2. PERPLEXITY (small sample)")
    print("="*60)
    
    try:
        ds = load_from_disk(DATA_DIR)
        texts = [item['text'] for item in ds]
        
        ppl, loss = calculate_perplexity(model, tokenizer, texts, max_samples=20)
        print(f"\nPerplexity: {ppl:.2f}")
        print(f"Avg Loss: {loss:.4f}")
    except Exception as e:
        print(f"Could not calculate perplexity: {e}")
        ppl = None
    
    # 3. Итоги
    print("\n" + "="*60)
    print("EVALUATION SUMMARY")
    print("="*60)
    print(f"Model: {MODEL_ID} + LoRA")
    print(f"Device: CPU")
    if ppl:
        print(f"Perplexity: {ppl:.2f}")
    print(f"Tests completed: {len(results)}")
    
    avg_time = sum(r['time'] for r in results) / len(results)
    avg_tps = sum(r['tokens_per_sec'] for r in results) / len(results)
    print(f"Avg generation time: {avg_time:.1f}s")
    print(f"Avg tokens/sec: {avg_tps:.1f}")
    
    # Оценка качества
    print("\n" + "="*60)
    print("QUALITY ASSESSMENT")
    print("="*60)
    
    if ppl:
        if ppl < 10:
            quality = "Excellent"
        elif ppl < 20:
            quality = "Good"
        elif ppl < 50:
            quality = "Acceptable"
        else:
            quality = "Needs improvement"
        print(f"Perplexity rating: {quality}")
    
    print("\nManual review needed for:")
    print("- Syntax correctness")
    print("- Logic coherence")
    print("- Code style")
    print("="*60)
    
    # Сохранение
    with open('evaluation_results_cpu.json', 'w') as f:
        json.dump({
            'model': MODEL_ID,
            'lora': LORA_PATH,
            'device': 'cpu',
            'perplexity': ppl,
            'results': results,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, indent=2)
    
    print("\nResults saved to evaluation_results_cpu.json")


if __name__ == "__main__":
    main()
