"""
CLI для тестирования агентной системы
"""
import json
import logging
import sys

from .orchestrator import get_orchestrator

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("Agent System CLI")
    logger.info("=" * 50)

    orchestrator = get_orchestrator()

    if len(sys.argv) < 2:
        logger.info("Usage:")
        logger.info("  python -m agent_runtime.cli task <your task>")
        logger.info("  python -m agent_runtime.cli twopass <your task>")
        logger.info("  python -m agent_runtime.cli consilium <your task>")
        logger.info("  python -m agent_runtime.cli analyze <file> <question>")
        logger.info("  python -m agent_runtime.cli status")
        return

    command = sys.argv[1]

    if command == "status":
        status = orchestrator.get_agent_status()
        logger.info("\n[STATUS] Agent Status:")
        logger.info(json.dumps(status, indent=2, default=str))

    elif command == "task":
        if len(sys.argv) < 3:
            logger.error("Error: Please provide a task")
            return

        task = " ".join(sys.argv[2:])
        logger.info(f"\n📝 Task: {task}")
        logger.info("\n🤔 Thinking...")

        result = orchestrator.execute_task(task)

        if result["success"]:
            logger.info(f"\n[OK] Response from {result.get('agent', 'dev')}:")
            logger.info(result["response"])
        else:
            logger.error(f"\n[ERROR] {result['error']}")

    elif command == "twopass":
        if len(sys.argv) < 3:
            logger.error("Error: Please provide a task")
            return

        task = " ".join(sys.argv[2:])
        logger.info(f"\nTask: {task}")
        logger.info("\nTwo-pass mode...")

        result = orchestrator.execute_task(task, two_pass=True)

        if result["success"]:
            logger.info(f"\n[OK] Result:")
            logger.info(json.dumps(result, indent=2, default=str)[:3000])
        else:
            logger.error(f"\n[ERROR] {result['error']}")

    elif command == "consilium":
        if len(sys.argv) < 3:
            logger.error("Error: Please provide a task")
            return

        task = " ".join(sys.argv[2:])
        logger.info(f"\nTask: {task}")
        logger.info("\nConsulting consilium...")

        result = orchestrator.execute_task(task, use_consilium=True)

        if result["success"]:
            logger.info(f"\n[OK] Consilium result:")
            logger.info(json.dumps(result, indent=2, default=str)[:2000])
        else:
            logger.error(f"\n[ERROR] {result['error']}")

    elif command == "analyze":
        if len(sys.argv) < 4:
            logger.error("Error: Please provide file path and question")
            return

        file_path = sys.argv[2]
        question = " ".join(sys.argv[3:])

        logger.info(f"\nAnalyzing: {file_path}")
        logger.info(f"Question: {question}")
        logger.info("\nThinking...")

        result = orchestrator.analyze_file(file_path, question)

        if result["success"]:
            logger.info(f"\n[OK] Answer from {result['agent']}:")
            logger.info(result["answer"])
        else:
            logger.error(f"\n[ERROR] {result['error']}")

    else:
        logger.error(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
