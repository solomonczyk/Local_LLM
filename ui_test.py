"""Minimal test UI"""
import gradio as gr
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from agent_runtime.orchestrator.consilium import get_consilium

def run_simple_task(task: str):
    """Simple task runner"""
    if not task.strip():
        return "Enter a task"
    
    try:
        consilium = get_consilium()
        result = consilium.consult(task, use_smart_routing=False, check_health=False)
        
        output = f"Mode: {result.get('mode')}\n\n"
        for agent, data in result.get("opinions", {}).items():
            output += f"[{agent}]: {data.get('opinion', 'N/A')[:200]}\n\n"
        
        return output
    except Exception as e:
        import traceback
        return f"Error: {e}\n\n{traceback.format_exc()}"

with gr.Blocks(title="Test UI") as demo:
    gr.Markdown("# Test UI")
    
    task_input = gr.Textbox(label="Task", placeholder="Enter task...")
    run_btn = gr.Button("Run")
    output = gr.Textbox(label="Output", lines=15)
    
    run_btn.click(fn=run_simple_task, inputs=task_input, outputs=output)

if __name__ == "__main__":
    demo.launch(server_port=7868)
