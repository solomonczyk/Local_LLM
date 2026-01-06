import re

import requests

TOOL_BASE = "http://localhost:8001"


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
