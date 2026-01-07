#!/usr/bin/env python3
"""
Интерактивное тестирование обученной LoRA модели
Быстрый способ проверить качество генерации кода
"""

import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

MODEL_ID = "Qwen/Qwen2.5-Coder-1.5B"
LORA_PATH = "lora_qwen2_5_coder_1_5b_python"

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

def load_model():
    print("Loading model with LoRA...")
    
    tokenizer = AutoTokenizer.from_pretrained(LORA_PATH, use_fast=True)
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
    
    model = PeftModel.from_pretrained(model, LORA_PATH)
    model.eval()
    
    print("Model loaded!")
    return model, tokenizer


def generate(model, tokenizer, prompt, max_tokens=200, temperature=0.7):
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id,
        )
    
    return tokenizer.decode(outputs[0], skip_special_tokens=True)


def main():
    model, tokenizer = load_model()
    
    print("\n" + "="*50)
    print("Interactive LoRA Model Testing")
    print("="*50)
    print("Commands:")
    print("  /quit - exit")
    print("  /temp <value> - set temperature (default 0.7)")
    print("  /tokens <value> - set max tokens (default 200)")
    print("="*50)
    
    temperature = 0.7
    max_tokens = 200
    
    while True:
        print("\n")
        prompt = input("Enter prompt (or /quit): ").strip()
        
        if prompt == "/quit":
            break
        elif prompt.startswith("/temp "):
            temperature = float(prompt.split()[1])
            print(f"Temperature set to {temperature}")
            continue
        elif prompt.startswith("/tokens "):
            max_tokens = int(prompt.split()[1])
            print(f"Max tokens set to {max_tokens}")
            continue
        elif not prompt:
            continue
        
        print("\nGenerating...")
        result = generate(model, tokenizer, prompt, max_tokens, temperature)
        
        print("\n" + "-"*50)
        print("Generated:")
        print("-"*50)
        print(result)
        print("-"*50)


if __name__ == "__main__":
    main()
