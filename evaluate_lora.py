#!/usr/bin/env python3
"""
Скрипт для оценки обученной LoRA модели Qwen2.5-Coder-1.5B

Методы оценки:
1. Perplexity на тестовых данных
2. Качество генерации кода (ручная проверка)
3. Сравнение с базовой моделью
4. Code completion benchmarks
"""

import os
import torch
import json
import time
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel
from datasets import load_from_disk
import math

# Пути
MODEL_ID = "Qwen/Qwen2.5-Coder-1.5B"
LORA_PATH = "lora_qwen2_5_coder_1_5b_python"
DATA_DIR = "codesearchnet_python_1pct_filtered"

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"


def load_model(use_lora=True):
    """Загрузка модели с или без LoRA"""
    print(f"Loading model (LoRA: {use_lora})...")
    
    tokenizer = AutoTokenizer.from_pretrained(
        LORA_PATH if use_lora else MODEL_ID, 
        use_fast=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.float16,
    )
    
    if use_lora:
        model = PeftModel.from_pretrained(model, LORA_PATH)
        print("LoRA adapter loaded!")
    
    model.eval()
    return model, tokenizer


def calculate_perplexity(model, tokenizer, texts, max_samples=100):
    """Вычисление perplexity на тестовых данных"""
    print(f"\nCalculating perplexity on {min(len(texts), max_samples)} samples...")
    
    total_loss = 0
    total_tokens = 0
    
    for i, text in enumerate(texts[:max_samples]):
        if i % 20 == 0:
            print(f"  Processing {i}/{min(len(texts), max_samples)}...")
        
        try:
            inputs = tokenizer(
                text, 
                return_tensors="pt", 
                truncation=True, 
                max_length=512
            ).to(model.device)
            
            with torch.no_grad():
                outputs = model(**inputs, labels=inputs["input_ids"])
                loss = outputs.loss.item()
                
            num_tokens = inputs["input_ids"].shape[1]
            total_loss += loss * num_tokens
            total_tokens += num_tokens
            
        except Exception as e:
            print(f"  Error on sample {i}: {e}")
            continue
    
    avg_loss = total_loss / total_tokens if total_tokens > 0 else float('inf')
    perplexity = math.exp(avg_loss)
    
    return perplexity, avg_loss


def generate_code(model, tokenizer, prompt, max_new_tokens=150):
    """Генерация кода по промпту"""
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    
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


def evaluate_code_completion(model, tokenizer, test_cases):
    """Оценка качества code completion"""
    results = []
    
    for i, case in enumerate(test_cases):
        print(f"\n{'='*60}")
        print(f"Test Case {i+1}: {case['name']}")
        print(f"{'='*60}")
        print(f"Prompt:\n{case['prompt']}")
        
        generated, gen_time, new_tokens = generate_code(
            model, tokenizer, case['prompt'], 
            max_new_tokens=case.get('max_tokens', 150)
        )
        
        print(f"\nGenerated:\n{generated}")
        print(f"\nTime: {gen_time:.2f}s, Tokens: {new_tokens}")
        
        results.append({
            'name': case['name'],
            'prompt': case['prompt'],
            'generated': generated,
            'time': gen_time,
            'tokens': new_tokens
        })
    
    return results


def main():
    print("="*60)
    print("LoRA Model Evaluation Script")
    print("="*60)
    
    # Тестовые кейсы для code completion
    test_cases = [
        {
            'name': 'Function definition',
            'prompt': 'def calculate_fibonacci(n):',
            'max_tokens': 200
        },
        {
            'name': 'Class definition',
            'prompt': 'class DatabaseConnection:\n    def __init__(self, host, port):',
            'max_tokens': 200
        },
        {
            'name': 'List comprehension',
            'prompt': '# Filter even numbers and square them\nnumbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]\nresult =',
            'max_tokens': 100
        },
        {
            'name': 'Error handling',
            'prompt': 'def safe_divide(a, b):\n    try:',
            'max_tokens': 150
        },
        {
            'name': 'API endpoint',
            'prompt': 'from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get("/users/{user_id}")\nasync def get_user(user_id: int):',
            'max_tokens': 150
        },
        {
            'name': 'Data processing',
            'prompt': 'import pandas as pd\n\ndef clean_dataframe(df):\n    """Remove duplicates and null values"""',
            'max_tokens': 200
        },
    ]
    
    # Загружаем модель с LoRA
    model_lora, tokenizer = load_model(use_lora=True)
    
    # 1. Оценка code completion
    print("\n" + "="*60)
    print("1. CODE COMPLETION EVALUATION")
    print("="*60)
    
    results_lora = evaluate_code_completion(model_lora, tokenizer, test_cases)
    
    # 2. Perplexity на тестовых данных
    print("\n" + "="*60)
    print("2. PERPLEXITY EVALUATION")
    print("="*60)
    
    try:
        ds = load_from_disk(DATA_DIR)
        texts = [item['text'] for item in ds]
        
        ppl_lora, loss_lora = calculate_perplexity(model_lora, tokenizer, texts, max_samples=50)
        print(f"\nLoRA Model Perplexity: {ppl_lora:.2f}")
        print(f"LoRA Model Avg Loss: {loss_lora:.4f}")
        
    except Exception as e:
        print(f"Could not calculate perplexity: {e}")
        ppl_lora = None
    
    # 3. Сравнение с базовой моделью (опционально)
    print("\n" + "="*60)
    print("3. COMPARISON WITH BASE MODEL (Optional)")
    print("="*60)
    
    compare = input("Compare with base model? (y/n): ").strip().lower()
    
    if compare == 'y':
        # Освобождаем память
        del model_lora
        torch.cuda.empty_cache()
        
        model_base, tokenizer_base = load_model(use_lora=False)
        
        print("\nBase model code completion:")
        results_base = evaluate_code_completion(model_base, tokenizer_base, test_cases[:3])
        
        if ppl_lora:
            ppl_base, loss_base = calculate_perplexity(model_base, tokenizer_base, texts, max_samples=50)
            print(f"\nBase Model Perplexity: {ppl_base:.2f}")
            print(f"Improvement: {((ppl_base - ppl_lora) / ppl_base * 100):.1f}%")
    
    # 4. Сохранение результатов
    print("\n" + "="*60)
    print("4. SAVING RESULTS")
    print("="*60)
    
    evaluation_results = {
        'model': MODEL_ID,
        'lora_path': LORA_PATH,
        'perplexity': ppl_lora,
        'test_cases': results_lora,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    with open('evaluation_results.json', 'w', encoding='utf-8') as f:
        json.dump(evaluation_results, f, indent=2, ensure_ascii=False)
    
    print("Results saved to evaluation_results.json")
    
    # Итоговый отчет
    print("\n" + "="*60)
    print("EVALUATION SUMMARY")
    print("="*60)
    print(f"Model: {MODEL_ID} + LoRA")
    print(f"LoRA Path: {LORA_PATH}")
    if ppl_lora:
        print(f"Perplexity: {ppl_lora:.2f}")
    print(f"Test Cases Evaluated: {len(results_lora)}")
    print(f"Average Generation Time: {sum(r['time'] for r in results_lora)/len(results_lora):.2f}s")
    print("="*60)


if __name__ == "__main__":
    main()
