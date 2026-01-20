"""
OpenAI-compatible proxy server that forwards requests to a local LLM backend.
"""
import os
from typing import Any, Dict, Optional

import requests
from fastapi import FastAPI, HTTPException, Request
import uvicorn

TARGET_V1 = os.getenv("LLM_PROXY_V1", os.getenv("AGENT_LLM_URL", "http://llm:8000/v1"))
if TARGET_V1.endswith("/"):
    TARGET_V1 = TARGET_V1[:-1]

if TARGET_V1.endswith("/v1"):
    TARGET_BASE = TARGET_V1[:-3]
else:
    TARGET_BASE = TARGET_V1

TIMEOUT = float(os.getenv("LLM_PROXY_TIMEOUT", "180"))

app = FastAPI()


def _build_headers(req: Request) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    auth = req.headers.get("authorization")
    if auth:
        headers["Authorization"] = auth
    else:
        api_key = os.getenv("AGENT_LLM_API_KEY") or os.getenv("AGENT_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _forward(method: str, url: str, json_body: Optional[Dict[str, Any]], headers: Dict[str, str]):
    try:
        resp = requests.request(method, url, json=json_body, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"LLM proxy error: {exc}") from exc

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    content_type = resp.headers.get("content-type", "")
    if "application/json" in content_type:
        return resp.json()
    return resp.text


@app.get("/health")
def health(request: Request):
    return _forward("GET", f"{TARGET_BASE}/health", None, _build_headers(request))


@app.get("/v1/health")
def health_v1(request: Request):
    return _forward("GET", f"{TARGET_V1}/health", None, _build_headers(request))


@app.get("/v1/models")
def list_models(request: Request):
    return _forward("GET", f"{TARGET_V1}/models", None, _build_headers(request))


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    payload = await request.json()
    return _forward("POST", f"{TARGET_V1}/chat/completions", payload, _build_headers(request))


@app.post("/v1/completions")
async def completions(request: Request):
    payload = await request.json()
    return _forward("POST", f"{TARGET_V1}/completions", payload, _build_headers(request))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8010, help="Port to run on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind")
    args = parser.parse_args()

    print(f"[proxy] Forwarding to {TARGET_V1}")
    uvicorn.run(app, host=args.host, port=args.port)
