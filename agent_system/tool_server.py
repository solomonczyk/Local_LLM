"""
Tool Server - FastAPI сервис для безопасного выполнения инструментов
Запуск: python -m agent_system.tool_server
"""
import os

# Импортируем rate limiter
import sys
from typing import List, Optional

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .audit import audit_logger
from .config import AgentConfig, SecurityConfig
from .database_tools import db_manager
from .tools import ToolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from rate_limiter import rate_limit_middleware

try:
    from .memory_postgres import postgres_memory

    MEMORY_POSTGRES_AVAILABLE = True
except ImportError:
    MEMORY_POSTGRES_AVAILABLE = False

# Конфигурация безопасности
API_KEY = os.getenv("AGENT_API_KEY")
if not API_KEY:
    raise ValueError("AGENT_API_KEY environment variable is required")
security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Проверка API ключа"""
    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials

app = FastAPI(title="Agent Tool Server", version="1.0.0")

# Rate limiting middleware
app.middleware("http")(rate_limit_middleware)

# CORS middleware для безопасности
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://152.53.227.37.nip.io",
        "https://agent.152.53.227.37.nip.io",
        "https://tools.152.53.227.37.nip.io",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Глобальный executor
tool_executor = ToolExecutor(agent_name="api")

class ReadFileRequest(BaseModel):
    path: str

class WriteFileRequest(BaseModel):
    path: str
    content: str
    mode: str = "overwrite"
    dry_run: bool = False
    expected_sha256: Optional[str] = None
    expected_exists: Optional[bool] = None

class ListDirRequest(BaseModel):
    path: str = "."
    pattern: str = "*"

class SearchRequest(BaseModel):
    query: str
    globs: Optional[List[str]] = None
    max_results: Optional[int] = None
    max_files: Optional[int] = None

class GitRequest(BaseModel):
    cmd: str

class ShellRequest(BaseModel):
    command: str

class SystemInfoRequest(BaseModel):
    info_type: str = "disks"

class NetworkInfoRequest(BaseModel):
    pass

class DeleteFileRequest(BaseModel):
    path: str
    dry_run: bool = False
    expected_sha256: Optional[str] = None
    expected_exists: Optional[bool] = None

class EditFileRequest(BaseModel):
    path: str
    old_text: str
    new_text: str
    dry_run: bool = False
    expected_sha256: Optional[str] = None
    expected_exists: Optional[bool] = None

class CopyFileRequest(BaseModel):
    source_path: str
    dest_path: str
    dry_run: bool = False
    expected_source_sha256: Optional[str] = None
    expected_dest_sha256: Optional[str] = None
    expected_source_exists: Optional[bool] = None
    expected_dest_exists: Optional[bool] = None

class MoveFileRequest(BaseModel):
    source_path: str
    dest_path: str
    dry_run: bool = False
    expected_source_sha256: Optional[str] = None
    expected_dest_sha256: Optional[str] = None
    expected_source_exists: Optional[bool] = None
    expected_dest_exists: Optional[bool] = None

class DatabaseConnectionRequest(BaseModel):
    name: str
    host: str
    database: str
    user: str
    password: str
    port: int = 5432

class DatabaseQueryRequest(BaseModel):
    connection_name: str
    query: str
    params: Optional[List] = None

class DatabaseSchemaRequest(BaseModel):
    connection_name: str
    table_name: Optional[str] = None

class MemoryInitRequest(BaseModel):
    connection_name: str = "agent_memory"

class MemorySearchRequest(BaseModel):
    session_id: str
    query: str
    limit: int = 20

@app.get("/")
async def root():
    return {
        "service": "Agent Tool Server",
        "version": "1.0.0",
        "workspace": str(SecurityConfig.WORKSPACE_ROOT),
        "access_level": AgentConfig.CURRENT_ACCESS_LEVEL,
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Agent Tool Server",
        "version": "1.0.0",
        "workspace": str(SecurityConfig.WORKSPACE_ROOT),
        "access_level": AgentConfig.CURRENT_ACCESS_LEVEL,
        "postgres_memory": MEMORY_POSTGRES_AVAILABLE,
        "authentication": "enabled",
        "rate_limiting": "enabled",
    }

@app.post("/tools/read_file")
async def read_file(request: ReadFileRequest, api_key: str = Depends(verify_api_key)):
    """Чтение файла"""
    result = tool_executor.read_file(request.path)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/tools/write_file")
async def write_file(request: WriteFileRequest, api_key: str = Depends(verify_api_key)):
    """Запись файла"""
    result = tool_executor.write_file(
        request.path,
        request.content,
        request.mode,
        request.dry_run,
        request.expected_sha256,
        request.expected_exists,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/tools/list_dir")
async def list_dir(request: ListDirRequest, api_key: str = Depends(verify_api_key)):
    """Список файлов"""
    result = tool_executor.list_dir(request.path, request.pattern)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/tools/search")
async def search(request: SearchRequest, api_key: str = Depends(verify_api_key)):
    """Поиск в файлах"""
    result = tool_executor.search(request.query, request.globs, request.max_results, request.max_files)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/tools/git")
async def git(request: GitRequest, api_key: str = Depends(verify_api_key)):
    """Git команды"""
    result = tool_executor.git(request.cmd)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/tools/shell")
async def shell(request: ShellRequest, api_key: str = Depends(verify_api_key)):
    """Shell команды"""
    result = tool_executor.shell(request.command)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/tools/system_info")
async def system_info(request: SystemInfoRequest, api_key: str = Depends(verify_api_key)):
    """Системная информация"""
    result = tool_executor.system_info(request.info_type)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/tools/network_info")
async def network_info(request: NetworkInfoRequest, api_key: str = Depends(verify_api_key)):
    """Сетевая информация"""
    result = tool_executor.network_info()
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/tools/delete_file")
async def delete_file(request: DeleteFileRequest, api_key: str = Depends(verify_api_key)):
    """Удаление файла"""
    result = tool_executor.delete_file(request.path, request.dry_run, request.expected_sha256, request.expected_exists)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/tools/edit_file")
async def edit_file(request: EditFileRequest, api_key: str = Depends(verify_api_key)):
    """Редактирование файла"""
    result = tool_executor.edit_file(
        request.path,
        request.old_text,
        request.new_text,
        request.dry_run,
        request.expected_sha256,
        request.expected_exists,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/tools/copy_file")
async def copy_file(request: CopyFileRequest, api_key: str = Depends(verify_api_key)):
    """Копирование файла"""
    result = tool_executor.copy_file(
        request.source_path,
        request.dest_path,
        request.dry_run,
        request.expected_source_sha256,
        request.expected_dest_sha256,
        request.expected_source_exists,
        request.expected_dest_exists,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/tools/move_file")
async def move_file(request: MoveFileRequest, api_key: str = Depends(verify_api_key)):
    """Перемещение/переименование файла"""
    result = tool_executor.move_file(
        request.source_path,
        request.dest_path,
        request.dry_run,
        request.expected_source_sha256,
        request.expected_dest_sha256,
        request.expected_source_exists,
        request.expected_dest_exists,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/tools/db_add_connection")
async def db_add_connection(request: DatabaseConnectionRequest, api_key: str = Depends(verify_api_key)):
    """Добавить подключение к БД"""
    connection_params = {
        "host": request.host,
        "database": request.database,
        "user": request.user,
        "password": request.password,
        "port": request.port,
    }
    result = db_manager.add_connection(request.name, connection_params)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/tools/db_execute_query")
async def db_execute_query(request: DatabaseQueryRequest, api_key: str = Depends(verify_api_key)):
    """Выполнить SQL запрос"""
    result = db_manager.execute_query(request.connection_name, request.query, request.params)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/tools/db_get_schema")
async def db_get_schema(request: DatabaseSchemaRequest, api_key: str = Depends(verify_api_key)):
    """Получить схему БД"""
    result = db_manager.get_schema_info(request.connection_name, request.table_name)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/tools/memory_init")
async def memory_init(request: MemoryInitRequest, api_key: str = Depends(verify_api_key)):
    """Инициализация схемы памяти в PostgreSQL"""
    if not MEMORY_POSTGRES_AVAILABLE:
        raise HTTPException(status_code=400, detail="PostgreSQL memory not available")

    # Устанавливаем подключение для памяти
    postgres_memory.connection_name = request.connection_name
    result = postgres_memory.initialize_schema()

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/tools/memory_search")
async def memory_search(request: MemorySearchRequest, api_key: str = Depends(verify_api_key)):
    """Поиск в памяти агента"""
    if not MEMORY_POSTGRES_AVAILABLE:
        raise HTTPException(status_code=400, detail="PostgreSQL memory not available")

    result = postgres_memory.search_messages(request.session_id, request.query, request.limit)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.get("/tools/memory_status")
async def memory_status(api_key: str = Depends(verify_api_key)):
    """Статус системы памяти"""
    return {
        "postgres_available": MEMORY_POSTGRES_AVAILABLE,
        "memory_type": "PostgreSQL" if MEMORY_POSTGRES_AVAILABLE else "File-based",
        "features": {
            "persistent_storage": True,
            "full_text_search": MEMORY_POSTGRES_AVAILABLE,
            "knowledge_base": MEMORY_POSTGRES_AVAILABLE,
            "session_management": True,
        },
    }

@app.get("/audit/recent")
async def get_recent_audit(limit: int = 100, api_key: str = Depends(verify_api_key)):
    """Получить последние действия из audit log"""
    return {"actions": audit_logger.get_recent_actions(limit)}

@app.get("/config")
async def get_config(api_key: str = Depends(verify_api_key)):
    """Текущая конфигурация"""
    return {
        "workspace": str(SecurityConfig.WORKSPACE_ROOT),
        "access_level": AgentConfig.CURRENT_ACCESS_LEVEL,
        "max_file_size": SecurityConfig.MAX_FILE_SIZE,
        "shell_timeout": SecurityConfig.SHELL_TIMEOUT,
        "allowed_commands": list(SecurityConfig.ALLOWED_SHELL_COMMANDS),
        "safe_git_commands": list(SecurityConfig.SAFE_GIT_COMMANDS),
    }

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=AgentConfig.TOOL_SERVER_PORT, help="Port to run on")
    args = parser.parse_args()

    print(f"🔧 Tool Server starting...")
    print(f"📁 Workspace: {SecurityConfig.WORKSPACE_ROOT}")
    print(f"🔒 Access Level: {AgentConfig.CURRENT_ACCESS_LEVEL}")
    print(f"🌐 Server: http://localhost:{args.port}")

    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")
