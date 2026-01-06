#!/usr/bin/env python3
"""
Минимальный UI для Agent System - только для тестирования
"""
import gradio as gr
import sys
import os

# Добавляем путь
sys.path.insert(0, os.path.dirname(__file__))

def test_function(message):
    """Простая тестовая функция"""
    return f"Echo: {message}"

def get_status():
    """Получить статус"""
    return "System is running"

# Создаём минимальный интерфейс
with gr.Blocks(title="Minimal Test UI") as demo:
    gr.Markdown("# 🧪 Minimal Test UI")
    
    with gr.Row():
        input_text = gr.Textbox(label="Test Input", placeholder="Enter test message")
        output_text = gr.Textbox(label="Output")
    
    with gr.Row():
        test_btn = gr.Button("Test")
        status_btn = gr.Button("Status")
    
    test_btn.click(fn=test_function, inputs=input_text, outputs=output_text)
    status_btn.click(fn=get_status, outputs=output_text)

if __name__ == "__main__":
    print("Starting minimal UI...")
    demo.launch(
        server_name="127.0.0.1",
        server_port=7866,
        share=False,
        show_error=True,
        debug=True
    )