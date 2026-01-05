"""
Простой GUI для Agent System
Запуск: python ui.py
"""
import gradio as gr
import json
import os
import sys
from pathlib import Path

# Добавляем путь для импорта
sys.path.insert(0, os.path.dirname(__file__))

from agent_runtime.orchestrator.consilium import get_consilium, route_agents
from agent_runtime.orchestrator.orchestrator import get_orchestrator
from agent_runtime.orchestrator.agent import get_llm_circuit_breaker


# Глобальные переменные для контекста
additional_context = ""
uploaded_files_content = {}


def get_system_status():
    """Получить статус системы"""
    try:
        cb = get_llm_circuit_breaker()
        cb_status = cb.get_status()
        
        consilium = get_consilium()
        health = consilium.check_llm_health(timeout=3.0)
        
        status_lines = [
            "=== System Status ===",
            f"LLM Health: {'OK' if health['healthy'] else 'UNAVAILABLE'}",
            f"Circuit Breaker: {cb_status['state']}",
            f"  - Failures: {cb_status['failure_count']}/{cb_status['config']['failure_threshold']}",
            f"  - Blocked: {cb_status['total_blocked']}",
            f"Consilium Mode: {consilium.mode}",
            f"Active Agents: {consilium.active_agents}",
            f"KB Version: {consilium.kb_version_hash}",
        ]
        
        if cb_status['time_until_retry']:
            status_lines.append(f"  - Retry in: {cb_status['time_until_retry']}s")
        
        return "\n".join(status_lines)
    except Exception as e:
        return f"Error getting status: {e}"


def preview_routing(task: str):
    """Предпросмотр роутинга без вызова LLM"""
    if not task.strip():
        return "Enter a task to preview routing"
    
    try:
        routing = route_agents(task)
        
        lines = [
            "=== Routing Preview ===",
            f"Mode: {routing['mode']}",
            f"Agents: {routing['agents']}",
            f"Confidence: {routing['confidence']}",
            f"Domains: {routing['domains_matched']}",
            f"Downgraded: {routing.get('downgraded', False)}",
            "",
            "Triggers matched:"
        ]
        
        for domain, triggers in routing.get('triggers_matched', {}).items():
            lines.append(f"  {domain}: {triggers}")
        
        lines.append("")
        lines.append(f"Reason: {routing['reason']}")
        
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def run_task(
    task: str,
    mode: str,
    use_smart_routing: bool,
    check_health: bool,
    include_context: bool
):
    """Выполнить задачу"""
    if not task.strip():
        return "Please enter a task"
    
    # Добавляем контекст если нужно
    full_task = task
    if include_context and additional_context:
        full_task = f"{task}\n\n=== Additional Context ===\n{additional_context}"
    
    # Добавляем содержимое загруженных файлов
    if include_context and uploaded_files_content:
        files_text = "\n\n".join([
            f"=== File: {name} ===\n{content[:5000]}"
            for name, content in uploaded_files_content.items()
        ])
        full_task = f"{full_task}\n\n{files_text}"
    
    try:
        # Устанавливаем режим
        os.environ["CONSILIUM_MODE"] = mode
        
        output_lines = [
            f"=== Task Execution ===",
            f"Mode: {mode}",
            f"Smart Routing: {use_smart_routing}",
            f"Health Check: {check_health}",
            f"Context included: {include_context}",
            "",
            f"Task: {task[:200]}{'...' if len(task) > 200 else ''}",
            "",
            "Processing...",
            ""
        ]
        
        yield "\n".join(output_lines)
        
        # Выполняем
        consilium = get_consilium()
        result = consilium.consult(
            full_task,
            use_smart_routing=use_smart_routing,
            check_health=check_health
        )
        
        # Форматируем результат
        output_lines.pop()  # Убираем "Processing..."
        output_lines.pop()
        
        if result.get("success") == False:
            output_lines.append(f"[ERROR] {result.get('error', 'Unknown error')}")
            if "health_check" in result:
                output_lines.append(f"Health: {result['health_check']}")
        else:
            output_lines.append(f"Result Mode: {result.get('mode', 'N/A')}")
            output_lines.append("")
            
            # Routing info
            if "routing" in result:
                r = result["routing"]
                output_lines.append("=== Routing ===")
                output_lines.append(f"Smart: {r.get('smart_routing', False)}")
                if r.get('smart_routing'):
                    output_lines.append(f"Confidence: {r.get('confidence', 'N/A')}")
                    output_lines.append(f"Domains: {r.get('domains_matched', 0)}")
                output_lines.append("")
            
            # Opinions
            output_lines.append("=== Agent Opinions ===")
            for agent, data in result.get("opinions", {}).items():
                output_lines.append(f"\n[{agent.upper()}] ({data.get('role', '')})")
                opinion = data.get("opinion", "No opinion")
                # Показываем первые 500 символов
                if len(opinion) > 500:
                    opinion = opinion[:500] + "..."
                output_lines.append(opinion)
            
            # Director decision
            if result.get("director_decision"):
                output_lines.append("\n=== Director Decision ===")
                decision = result["director_decision"]
                if len(decision) > 1000:
                    decision = decision[:1000] + "..."
                output_lines.append(decision)
            
            # Timing
            if "timing" in result:
                t = result["timing"]
                output_lines.append(f"\n=== Timing ===")
                output_lines.append(f"Agents: {t.get('agents_parallel', 0)}s")
                output_lines.append(f"Director: {t.get('director', 0)}s")
                output_lines.append(f"Total: {t.get('total', 0)}s")
        
        yield "\n".join(output_lines)
        
    except Exception as e:
        yield f"Error: {e}"


def update_context(text: str):
    """Обновить дополнительный контекст"""
    global additional_context
    additional_context = text
    return f"Context updated ({len(text)} chars)"


def handle_file_upload(files):
    """Обработать загруженные файлы"""
    global uploaded_files_content
    
    if not files:
        uploaded_files_content = {}
        return "No files uploaded"
    
    uploaded_files_content = {}
    results = []
    
    for file in files:
        try:
            with open(file.name, 'r', encoding='utf-8') as f:
                content = f.read()
            
            filename = Path(file.name).name
            uploaded_files_content[filename] = content
            results.append(f"[OK] {filename} ({len(content)} chars)")
        except Exception as e:
            results.append(f"[ERROR] {file.name}: {e}")
    
    return "\n".join(results)


def clear_files():
    """Очистить загруженные файлы"""
    global uploaded_files_content
    uploaded_files_content = {}
    return "Files cleared"


# Создаём интерфейс
with gr.Blocks(title="Agent System UI", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🤖 Agent System UI")
    gr.Markdown("Multi-agent consilium with smart routing")
    
    with gr.Row():
        # Левая колонка - управление
        with gr.Column(scale=1):
            gr.Markdown("### ⚙️ Settings")
            
            mode_select = gr.Radio(
                choices=["FAST", "STANDARD", "CRITICAL"],
                value="FAST",
                label="Consilium Mode",
                info="FAST=1 agent, STANDARD=3, CRITICAL=all+director"
            )
            
            smart_routing = gr.Checkbox(
                value=True,
                label="Smart Routing",
                info="Auto-select agents by task content"
            )
            
            health_check = gr.Checkbox(
                value=True,
                label="Health Check",
                info="Check LLM before execution"
            )
            
            include_context = gr.Checkbox(
                value=False,
                label="Include Context",
                info="Add context and files to task"
            )
            
            gr.Markdown("### 📊 Status")
            status_btn = gr.Button("Refresh Status", size="sm")
            status_output = gr.Textbox(
                label="System Status",
                lines=8,
                interactive=False
            )
            
        # Центральная колонка - задача и результат
        with gr.Column(scale=2):
            gr.Markdown("### 📝 Task")
            
            task_input = gr.Textbox(
                label="Enter your task",
                placeholder="e.g., Design REST API for user authentication",
                lines=3
            )
            
            with gr.Row():
                preview_btn = gr.Button("Preview Routing", variant="secondary")
                run_btn = gr.Button("Run Task", variant="primary")
            
            preview_output = gr.Textbox(
                label="Routing Preview",
                lines=8,
                interactive=False
            )
            
            gr.Markdown("### 📤 Output")
            output = gr.Textbox(
                label="Result",
                lines=20,
                interactive=False
            )
        
        # Правая колонка - контекст и файлы
        with gr.Column(scale=1):
            gr.Markdown("### 📎 Additional Context")
            
            context_input = gr.Textbox(
                label="Context (requirements, specs, etc.)",
                placeholder="Paste additional context here...",
                lines=8
            )
            context_btn = gr.Button("Update Context", size="sm")
            context_status = gr.Textbox(
                label="Context Status",
                lines=1,
                interactive=False
            )
            
            gr.Markdown("### 📁 Upload Files")
            file_upload = gr.File(
                label="Upload files (.py, .md, .txt, etc.)",
                file_count="multiple",
                file_types=[".py", ".md", ".txt", ".json", ".yaml", ".yml"]
            )
            files_status = gr.Textbox(
                label="Uploaded Files",
                lines=4,
                interactive=False
            )
            clear_btn = gr.Button("Clear Files", size="sm")
    
    # Event handlers
    status_btn.click(
        fn=get_system_status,
        outputs=status_output
    )
    
    preview_btn.click(
        fn=preview_routing,
        inputs=task_input,
        outputs=preview_output
    )
    
    run_btn.click(
        fn=run_task,
        inputs=[task_input, mode_select, smart_routing, health_check, include_context],
        outputs=output
    )
    
    context_btn.click(
        fn=update_context,
        inputs=context_input,
        outputs=context_status
    )
    
    file_upload.change(
        fn=handle_file_upload,
        inputs=file_upload,
        outputs=files_status
    )
    
    clear_btn.click(
        fn=clear_files,
        outputs=files_status
    )
    
    # Загружаем статус при старте
    demo.load(
        fn=get_system_status,
        outputs=status_output
    )


if __name__ == "__main__":
    import argparse
    import socket
    
    def find_free_port(start_port=7861):
        for port in range(start_port, start_port + 100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('0.0.0.0', port))
                    return port
            except OSError:
                continue
        return start_port
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Agent System UI')
    parser.add_argument('--server_port', type=int, default=None, help='Port to run the server on')
    parser.add_argument('--server_name', type=str, default='0.0.0.0', help='Server name/IP to bind to')
    args = parser.parse_args()
    
    # Determine port
    if args.server_port:
        port = args.server_port
    else:
        port = find_free_port()
    
    print("Starting Agent System UI...")
    print(f"Server will be available at http://{args.server_name}:{port}")
    
    try:
        demo.launch(
            server_name=args.server_name,
            server_port=port,
            share=False,
            show_error=True
        )
    except Exception as e:
        print(f"Failed to start UI server: {e}")
        import traceback
        traceback.print_exc()
