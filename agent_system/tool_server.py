"""
Tool Server - FastAPI сервис для безопасного выполнения инструментов
Запуск: python -m agent_system.tool_server
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

from .tools import ToolExecutor
from .config import AgentConfig, SecurityConfig
from .audit import audit_logger

app = FastAPI(title="Agent Tool Server", version="1.0.0")

# Глобальный executor
tool_executor = ToolExecutor(agent_name="api")


class ReadFileRequest(BaseModel):
    path: str


class WriteFileRequest(BaseModel):
    path: str
    content: str
    mode: str = "overwrite"


class ListDirRequest(BaseModel):
    path: str = "."
    pattern: str = "*"


class SearchRequest(BaseModel):
    query: str
    globs: Optional[List[str]] = None


class GitRequest(BaseModel):
    cmd: str


class ShellRequest(BaseModel):
    command: str


@app.get("/")
async def root():
    return {
        "service": "Agent Tool Server",
        "version": "1.0.0",
        "workspace": str(SecurityConfig.WORKSPACE_ROOT),
        "access_level": AgentConfig.CURRENT_ACCESS_LEVEL
    }


@app.post("/tools/read_file")
async def read_file(request: ReadFileRequest):
    """Чтение файла"""
    result = tool_executor.read_file(request.path)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/tools/write_file")
async def write_file(request: WriteFileRequest):
    """Запись файла"""
    result = tool_executor.write_file(request.path, request.content, request.mode)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/tools/list_dir")
async def list_dir(request: ListDirRequest):
    """Список файлов"""
    result = tool_executor.list_dir(request.path, request.pattern)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/tools/search")
async def search(request: SearchRequest):
    """Поиск в файлах"""
    result = tool_executor.search(request.query, request.globs)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/tools/git")
async def git(request: GitRequest):
    """Git команды"""
    result = tool_executor.git(request.cmd)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/tools/shell")
async def shell(request: ShellRequest):
    """Shell команды"""
    result = tool_executor.shell(request.command)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/audit/recent")
async def get_recent_audit(limit: int = 100):
    """Получить последние действия из audit log"""
    return {"actions": audit_logger.get_recent_actions(limit)}


@app.get("/config")
async def get_config():
    """Текущая конфигурация"""
    return {
        "workspace": str(SecurityConfig.WORKSPACE_ROOT),
        "access_level": AgentConfig.CURRENT_ACCESS_LEVEL,
        "max_file_size": SecurityConfig.MAX_FILE_SIZE,
        "shell_timeout": SecurityConfig.SHELL_TIMEOUT,
        "allowed_commands": list(SecurityConfig.ALLOWED_SHELL_COMMANDS),
        "safe_git_commands": list(SecurityConfig.SAFE_GIT_COMMANDS)
    }


if __name__ == "__main__":
    print(f"🔧 Tool Server starting...")
    print(f"📁 Workspace: {SecurityConfig.WORKSPACE_ROOT}")
    print(f"🔒 Access Level: {AgentConfig.CURRENT_ACCESS_LEVEL}")
    print(f"🌐 Server: http://localhost:{AgentConfig.TOOL_SERVER_PORT}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=AgentConfig.TOOL_SERVER_PORT,
        log_level="info"
    )
