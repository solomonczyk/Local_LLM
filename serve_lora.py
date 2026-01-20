"""
Локальный OpenAI-совместимый сервер с обученной LoRA моделью
Запускает на http://localhost:8010
"""
import argparse
import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

# Импортируем BitsAndBytesConfig только если CUDA доступна
if torch.cuda.is_available():
    from transformers import BitsAndBytesConfig

# Пути
BASE_MODEL = "Qwen/Qwen2.5-Coder-1.5B"
LORA_PATH = "lora_qwen2_5_coder_1_5b_python"
ADAPTER_PATH = os.getenv("LORA_ADAPTER_PATH", LORA_PATH)

app = FastAPI()

# Загрузка модели при старте
print("Загрузка базовой модели...")

# Проверяем доступность CUDA
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Используем устройство: {device}")

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

if torch.cuda.is_available():
    # С CUDA используем квантизацию
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
else:
    # Без CUDA - обычная загрузка на CPU
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float32,
        device_map={"": "cpu"},
        trust_remote_code=True,
    )

print("Загрузка LoRA адаптера...")
model = PeftModel.from_pretrained(model, ADAPTER_PATH)
model.eval()
print("✅ Модель готова!")

class ChatRequest(BaseModel):
    model: str
    messages: list
    temperature: float = 0.7
    max_tokens: int = 512

class CompletionRequest(BaseModel):
    model: str
    prompt: str
    temperature: float = 0.7
    max_tokens: int = 512

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    # Формируем промпт из сообщений
    prompt = ""
    for msg in request.messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            prompt += f"{content}\n\n"
        elif role == "user":
            prompt += f"User: {content}\n"
        elif role == "assistant":
            prompt += f"Assistant: {content}\n"

    prompt += "Assistant:"

    # Генерация
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=request.max_tokens,
            temperature=request.temperature,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

    response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1] :], skip_special_tokens=True)

    return {
        "id": "local",
        "object": "chat.completion",
        "model": request.model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": response}, "finish_reason": "stop"}],
    }

@app.post("/v1/completions")
async def completions(request: CompletionRequest):
    inputs = tokenizer(request.prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=request.max_tokens,
            temperature=request.temperature,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

    response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1] :], skip_special_tokens=True)

    return {
        "id": "local",
        "object": "text_completion",
        "model": request.model,
        "choices": [{"text": response, "index": 0, "finish_reason": "stop"}],
    }

@app.get("/v1/models")
async def list_models():
    return {"object": "list", "data": [{"id": "qwen2.5-coder-lora", "object": "model", "owned_by": "local"}]}

@app.get("/health")
async def health_check():
    """Health check endpoint для проверки доступности сервера"""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "model_name": "qwen2.5-coder-lora",
        "backend": "peft",
        "lora": ADAPTER_PATH,
    }

@app.get("/v1/health")
async def health_check_v1():
    """Health check endpoint (OpenAI-style path)"""
    return await health_check()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LoRA inference server")
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    print(f"[LLM] backend=peft lora_adapter={ADAPTER_PATH}")
    print("\n🚀 Сервер запущен на http://localhost:8010")
    print("📝 OpenAI API endpoint: http://localhost:8010/v1")
    uvicorn.run(app, host="0.0.0.0", port=args.port)

