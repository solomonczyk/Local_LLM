#!/usr/bin/env python3
"""
Download required local model assets into ./models (out of git).

Default:
- Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF
  - qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
"""

from __future__ import annotations

from pathlib import Path

from huggingface_hub import hf_hub_download


def main() -> int:
    models_dir = Path(__file__).resolve().parents[1] / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    repo_id = "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF"
    filename = "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"

    print(f"Downloading {repo_id}/{filename} -> {models_dir}")
    path = hf_hub_download(repo_id=repo_id, filename=filename, local_dir=str(models_dir))
    print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

