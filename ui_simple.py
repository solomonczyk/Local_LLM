#!/usr/bin/env python3
"""
Упрощенный UI для тестирования Agent System
"""
import gradio as gr
import json
import os
import sys
import traceback
from pathlib import Path

def test_imports():
    """Тестирование импортов"""
    results = []
    
    # Тестируем базовые импорты
    try:
        import gradio
        results.append(f"✅ Gradio {gradio.__version__}")
    except Exception as e:
        results.append(f"❌ Gradio: {e}")
    
    try:
        import fastapi
        results.append(f"✅ FastAPI {fastapi.__version__}")
    except Exception as e:
        results.append(f"❌ FastAPI: {e}")
    
    # Тестируем наши модули
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from agent_runtime.orchestrator.consilium import get_consilium
        results.append("✅ Consilium import OK")
    except Exception as e:
        results.append(f"❌ Consilium: {e}")
        
    try:
        from agent_runtime.orchestrator.orchestrator import get_orchestrator
        results.append("✅ Orchestrator import OK")
    except Exception as e:
        results.append(f"❌ Orchestrator: {e}")
        
    try:
        from agent_runtime.orchestrator.agent import get_llm_circuit_breaker
        results.append("✅ Circuit Breaker import OK")
    except Exception as e:
        results.append(f"❌ Circuit Breaker: {e}")
    
    return "\n".join(results)

def simple_test(message: str):
    """Простой тест"""
    if not message.strip():
        return "Please enter a message"
    
    try:
        # Пробуем импортировать и использовать consilium
        sys.path.insert(0, os.path.dirname(__file__))
        from agent_runtime.orchestrator.consilium import get_consilium
        
        consilium = get_consilium()
        result = consilium.consult(message, use_smart_routing=False, check_health=False)
        
        return f"Success! Result: {json.dumps(result, indent=2)}"
        
    except Exception as e:
        return f"Error: {e}\n\nTraceback:\n{traceback.format_exc()}"

def get_system_info():
    """Получить информацию о системе"""
    info = []
    info.append(f"Python: {sys.version}")
    info.append(f"Working directory: {os.getcwd()}")
    info.append(f"Python path: {sys.path[:3]}...")
    
    # Проверяем файлы
    files_to_check = [
        "agent_runtime/orchestrator/consilium.py",
        "agent_runtime/orchestrator/orchestrator.py", 
        "agent_runtime/orchestrator/agent.py"
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            info.append(f"✅ {file_path}")
        else:
            info.append(f"❌ {file_path}")
    
    return "\n".join(info)

# Создаём простой интерфейс
with gr.Blocks(title="Agent System Test UI") as demo:
    gr.Markdown("# 🧪 Agent System Test UI")
    gr.Markdown("Simple UI for testing the agent system")
    
    with gr.Tab("System Info"):
        info_btn = gr.Button("Get System Info")
        info_output = gr.Textbox(label="System Information", lines=10)
        
        imports_btn = gr.Button("Test Imports")
        imports_output = gr.Textbox(label="Import Results", lines=10)
    
    with gr.Tab("Simple Test"):
        message_input = gr.Textbox(label="Test Message", placeholder="Hello, test the system")
        test_btn = gr.Button("Run Test")
        test_output = gr.Textbox(label="Test Result", lines=15)
    
    # Event handlers
    info_btn.click(fn=get_system_info, outputs=info_output)
    imports_btn.click(fn=test_imports, outputs=imports_output)
    test_btn.click(fn=simple_test, inputs=message_input, outputs=test_output)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple Agent System UI")
    parser.add_argument("--port", type=int, default=7865, help="Port to run on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to")
    args = parser.parse_args()
    
    print(f"Starting Simple UI on http://{args.host}:{args.port}")
    
    try:
        demo.launch(
            server_name=args.host,
            server_port=args.port,
            share=False,
            show_error=True,
            debug=True
        )
    except Exception as e:
        print(f"Failed to start: {e}")
        traceback.print_exc()