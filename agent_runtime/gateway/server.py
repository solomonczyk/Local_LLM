import os
import requests
from fastapi import FastAPI
from pydantic import BaseModel
import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent_runtime.orchestrator.orchestrator import orchestrator

TOOL_BASE = os.getenv("TOOL_BASE", "http://localhost:8001")
LLM_BASE = os.getenv("LLM_BASE", "http://localhost:8000")

app = FastAPI(title="Agent Gateway", version="0.1")


@app.get("/health")
def health():
    tool = requests.get(f"{TOOL_BASE}/health", timeout=5).json()
    llm_ok = True
    try:
        # minimal check: just see if the endpoint is reachable (may 404 if not implemented)
        requests.get(f"{LLM_BASE}/", timeout=5)
    except Exception:
        llm_ok = False
    return {"status": "ok", "tool": tool, "llm_reachable": llm_ok}


class ChatRequest(BaseModel):
    model: str
    messages: list
    max_tokens: int = 512
    temperature: float = 0.2


@app.post("/v1/chat/completions")
def chat(req: ChatRequest):
    user_message = req.messages[-1]["content"]
    
    # Проверяем есть ли специальная команда для консилиума
    use_consilium = "consilium" in user_message.lower() or "team" in user_message.lower()
    
    result = orchestrator.execute_task(
        task=user_message,
        agent_name="dev",
        use_consilium=use_consilium
    )
    
    if not result.get("success"):
        return {
            "id": "chatcmpl-error",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"Error: {result.get('error')}"
                    },
                    "finish_reason": "error",
                }
            ],
        }
    
    # Форматируем ответ в зависимости от режима
    if result.get("mode") == "consilium":
        # Консилиум - показываем мнения и решение
        response_text = f"""🏛️ CONSILIUM DECISION

Director's Decision:
{result['director_decision']}

Team Opinions:
"""
        for agent_name, opinion in result["opinions"].items():
            response_text += f"\n{agent_name.upper()}: {opinion['opinion'][:200]}..."
        
        response_text += f"\n\nRecommendation: {result['recommendation']}"
    else:
        # Один агент
        response_text = result["response"]
    
    return {
        "id": "chatcmpl-agent",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop",
            }
        ],
    }


if __name__ == "__main__":
    import uvicorn
    print(f"🌐 Agent Gateway starting...")
    print(f"🔧 Tool Server: {TOOL_BASE}")
    print(f"🤖 LLM Server: {LLM_BASE}")
    uvicorn.run(app, host="0.0.0.0", port=8002)
