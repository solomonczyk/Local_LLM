#!/usr/bin/env python3
import requests
import json

url = "http://localhost:8010/v1/chat/completions"
data = {
    "model": "gpt-5.2",
    "messages": [{"role": "user", "content": "Say hello"}],
    "max_tokens": 50
}

try:
    response = requests.post(url, json=data, timeout=60)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
