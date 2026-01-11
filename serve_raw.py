import os
import time
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import uvicorn

# API key auth (shared pattern with serve_enhanced)
API_KEY = os.getenv("AGENT_API_KEY")
if not API_KEY:
    raise ValueError("AGENT_API_KEY environment variable is required")
security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials

app = FastAPI()

@app.post("/v1/chat/completions")
async def chat_completions(api_key: str = Depends(verify_api_key)):
    return {
        "id": f"raw-{int(time.time())}",
        "object": "chat.completion",
        "model": "raw-llm",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "RAW_LLM_OK"},
                "finish_reason": "stop",
            }
        ],
    }

@app.get("/v1/models")
async def list_models():
    return {"object": "list", "data": [{"id": "raw-llm", "object": "model", "owned_by": "local"}]}

@app.get("/health")
async def health():
    return {"status": "ok", "mode": "raw"}

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000, help="Port to run on")
    args = parser.parse_args()

    uvicorn.run(app, host="0.0.0.0", port=args.port)
