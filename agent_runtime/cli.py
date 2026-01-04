"""
CLI для тестирования агентной системы
"""
import sys
import json
from .orchestrator import get_orchestrator


def main():
    print("Agent System CLI")
    print("=" * 50)
    
    orchestrator = get_orchestrator()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m agent_runtime.cli task <your task>")
        print("  python -m agent_runtime.cli twopass <your task>")
        print("  python -m agent_runtime.cli consilium <your task>")
        print("  python -m agent_runtime.cli analyze <file> <question>")
        print("  python -m agent_runtime.cli status")
        return
    
    command = sys.argv[1]
    
    if command == "status":
        status = orchestrator.get_agent_status()
        print("\n[STATUS] Agent Status:")
        print(json.dumps(status, indent=2, default=str))
    
    elif command == "task":
        if len(sys.argv) < 3:
            print("Error: Please provide a task")
            return
        
        task = " ".join(sys.argv[2:])
        print(f"\n📝 Task: {task}")
        print("\n🤔 Thinking...")
        
        result = orchestrator.execute_task(task)
        
        if result["success"]:
            print(f"\n[OK] Response from {result.get('agent', 'dev')}:")
            print(result["response"])
        else:
            print(f"\n[ERROR] {result['error']}")
    
    elif command == "twopass":
        if len(sys.argv) < 3:
            print("Error: Please provide a task")
            return
        
        task = " ".join(sys.argv[2:])
        print(f"\nTask: {task}")
        print("\nTwo-pass mode...")
        
        result = orchestrator.execute_task(task, two_pass=True)
        
        if result["success"]:
            print(f"\n[OK] Result:")
            print(json.dumps(result, indent=2, default=str)[:3000])
        else:
            print(f"\n[ERROR] {result['error']}")
    
    elif command == "consilium":
        if len(sys.argv) < 3:
            print("Error: Please provide a task")
            return
        
        task = " ".join(sys.argv[2:])
        print(f"\nTask: {task}")
        print("\nConsulting consilium...")
        
        result = orchestrator.execute_task(task, use_consilium=True)
        
        if result["success"]:
            print(f"\n[OK] Consilium result:")
            print(json.dumps(result, indent=2, default=str)[:2000])
        else:
            print(f"\n[ERROR] {result['error']}")
    
    elif command == "analyze":
        if len(sys.argv) < 4:
            print("Error: Please provide file path and question")
            return
        
        file_path = sys.argv[2]
        question = " ".join(sys.argv[3:])
        
        print(f"\nAnalyzing: {file_path}")
        print(f"Question: {question}")
        print("\nThinking...")
        
        result = orchestrator.analyze_file(file_path, question)
        
        if result["success"]:
            print(f"\n[OK] Answer from {result['agent']}:")
            print(result["answer"])
        else:
            print(f"\n[ERROR] {result['error']}")
    
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
