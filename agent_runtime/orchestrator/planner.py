import os
import re

import requests

TOOL_BASE = os.getenv("TOOL_SERVER_URL", "http://localhost:8011")
TOOL_API_KEY = os.getenv("AGENT_API_KEY")

def _tool_headers():
    headers = {}
    if TOOL_API_KEY:
        headers["Authorization"] = f"Bearer {TOOL_API_KEY}"
    return headers

def run_planner(messages: list) -> list:
    """
    Very simple planner:
    - If model asks READ_FILE: path
    - We fetch file content and inject it back into context
    """

    last = messages[-1]["content"]

    read_matches = re.findall(r"READ_FILE:\s*(.+)", last)

    new_messages = messages[:]

    for path in read_matches:
        resp = requests.post(
            f"{TOOL_BASE}/tools/read_file",
            json={"path": path.strip()},
            headers=_tool_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        content = resp.json()["content"]

        new_messages.append(
            {
                "role": "system",
                "content": f"File `{path}` content:\n\n{content}",
            }
        )

    return new_messages
