import os
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

# === CONFIG ===
WORKSPACE_ROOT = Path(os.getenv("AGENT_WORKSPACE", Path.cwd())).resolve()

app = FastAPI(title="Agent Tool Server", version="0.1")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "workspace": str(WORKSPACE_ROOT),
    }

class ReadFileRequest(BaseModel):
    path: str

@app.post("/tools/read_file")
def read_file(req: ReadFileRequest):
    target = (WORKSPACE_ROOT / req.path).resolve()

    if not str(target).startswith(str(WORKSPACE_ROOT)):
        raise ValueError("Access denied: path outside workspace")

    if not target.exists() or not target.is_file():
        raise ValueError("File not found")

    return {
        "path": req.path,
        "content": target.read_text(encoding="utf-8", errors="ignore"),
    }

class WriteFileRequest(BaseModel):
    path: str
    patch: str  # unified diff

@app.post("/tools/write_file_patch")
def write_file_patch(req: WriteFileRequest):
    target = (WORKSPACE_ROOT / req.path).resolve()

    if not str(target).startswith(str(WORKSPACE_ROOT)):
        raise ValueError("Access denied: path outside workspace")

    if not target.exists() or not target.is_file():
        raise ValueError("File not found")

    original = target.read_text(encoding="utf-8", errors="ignore")

    try:
        import difflib

        patched = "".join(difflib.restore(req.patch.splitlines(keepends=True), which=1))
    except Exception as e:
        raise ValueError(f"Invalid patch format: {e}")

    target.write_text(patched, encoding="utf-8")

    return {
        "status": "patched",
        "path": req.path,
    }

class ListDirRequest(BaseModel):
    path: str = "."

@app.post("/tools/list_dir")
def list_dir(req: ListDirRequest):
    target = (WORKSPACE_ROOT / req.path).resolve()

    if not str(target).startswith(str(WORKSPACE_ROOT)):
        raise ValueError("Access denied: path outside workspace")

    if not target.exists() or not target.is_dir():
        raise ValueError("Directory not found")

    items = []
    for p in target.iterdir():
        items.append({"name": p.name, "type": "dir" if p.is_dir() else "file"})

    # sort: dirs first then files
    items.sort(key=lambda x: (x["type"] != "dir", x["name"].lower()))
    return {"path": req.path, "items": items}

if __name__ == "__main__":
    import uvicorn

    print(f"🔧 Tool Server starting...")
    print(f"📁 Workspace: {WORKSPACE_ROOT}")
    uvicorn.run(app, host="0.0.0.0", port=8011)
