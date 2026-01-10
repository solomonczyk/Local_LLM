"""
OpenAI-совместимый прокси сервер
Проксирует запросы к OpenAI API
"""
import os
import asyncio
from pathlib import Path

# Load .env file
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import openai
from typing import Optional

app = FastAPI()

# Инициализация OpenAI клиента
client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Модель по умолчанию
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class ChatRequest(BaseModel):
    model: str = DEFAULT_MODEL
    messages: list
    temperature: float = 0.7
    max_tokens: int = 1024


class CompletionRequest(BaseModel):
    model: str = DEFAULT_MODEL
    prompt: str
    temperature: float = 0.7
    max_tokens: int = 1024


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "model_loaded": True,
        "model_name": DEFAULT_MODEL,
        "backend": "openai"
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    """OpenAI Chat Completions API"""
    try:
        model = request.model or DEFAULT_MODEL
        
        # GPT-5.x uses max_completion_tokens instead of max_tokens
        if model.startswith("gpt-5") or model.startswith("o1") or model.startswith("o3"):
            response = await client.chat.completions.create(
                model=model,
                messages=request.messages,
                temperature=request.temperature,
                max_completion_tokens=request.max_tokens
            )
        else:
            response = await client.chat.completions.create(
                model=model,
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
        
        return {
            "id": response.id,
            "object": "chat.completion",
            "created": response.created,
            "model": response.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response.choices[0].message.content
                    },
                    "finish_reason": response.choices[0].finish_reason
                }
            ],
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }
    except openai.APIError as e:
        raise HTTPException(status_code=500, detail=f"OpenAI API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/v1/completions")
async def completions(request: CompletionRequest):
    """OpenAI Completions API (legacy)"""
    messages = [{"role": "user", "content": request.prompt}]
    model = request.model or DEFAULT_MODEL
    
    try:
        if model.startswith("gpt-5") or model.startswith("o1") or model.startswith("o3"):
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=request.temperature,
                max_completion_tokens=request.max_tokens
            )
        else:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
        
        return {
            "id": response.id,
            "object": "text_completion",
            "created": response.created,
            "model": response.model,
            "choices": [
                {
                    "text": response.choices[0].message.content,
                    "index": 0,
                    "finish_reason": response.choices[0].finish_reason
                }
            ],
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    
    print(f"🚀 OpenAI Proxy Server starting on http://{args.host}:{args.port}")
    print(f"📝 Using model: {DEFAULT_MODEL}")
    
    uvicorn.run(app, host=args.host, port=args.port)
