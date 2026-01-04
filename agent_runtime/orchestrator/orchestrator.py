"""
Orchestrator - управление циклом работы агента
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
from .agent import Agent
from .consilium import get_consilium


class Orchestrator:
    """Оркестратор для управления агентами и выполнения задач"""
    
    def __init__(
        self,
        llm_url: str = "http://localhost:8000/v1",
        tool_url: str = "http://localhost:8001"
    ):
        self.llm_url = llm_url
        self.tool_url = tool_url
        self.agents: Dict[str, Agent] = {}
        self._consilium = None  # Lazy init
        self._init_agents()
    
    @property
    def consilium(self):
        """Lazy singleton для консилиума"""
        if self._consilium is None:
            self._consilium = get_consilium()
        return self._consilium
    
    def _init_agents(self):
        """Инициализация базовых агентов"""
        # Пока только один базовый агент
        self.agents["dev"] = Agent(
            name="Dev",
            role="Software Developer",
            llm_url=self.llm_url,
            tool_url=self.tool_url
        )
    
    def execute_task(self, task: str, agent_name: str = "dev", use_consilium: bool = False, two_pass: bool = False) -> Dict[str, Any]:
        """
        Выполнить задачу
        
        Параметры:
        - task: задача
        - agent_name: имя агента (если use_consilium=False)
        - use_consilium: использовать ли консилиум (несколько агентов)
        - two_pass: использовать two-pass режим (Pass 1: triage, Pass 2: escalate if needed)
        """
        
        if two_pass:
            # Two-pass режим: сначала triage, потом escalate если нужно
            if agent_name not in self.agents:
                return {
                    "success": False,
                    "error": f"Agent {agent_name} not found"
                }
            
            agent = self.agents[agent_name]
            
            try:
                # Pass 1: Triage
                print(f"🔍 Pass 1 (Triage): {agent_name}")
                triage = agent.think_triage(task)
                
                print(f"  needs_consilium: {triage['needs_consilium']}")
                print(f"  reason: {triage['reason']}")
                if triage['suggested_agents']:
                    print(f"  suggested_agents: {triage['suggested_agents']}")
                
                if not triage['needs_consilium']:
                    # Не нужен consilium - возвращаем быстрый ответ
                    return {
                        "success": True,
                        "mode": "two_pass_fast",
                        "agent": agent_name,
                        "task": task,
                        "response": triage['response'],
                        "triage": triage,
                        "escalated": False
                    }
                
                # Pass 2: Escalate to consilium
                print(f"🚀 Pass 2 (Escalate): consilium")
                result = self.consilium.consult(task)
                
                return {
                    "success": True,
                    "mode": "two_pass_escalated",
                    "task": task,
                    "triage": triage,
                    "escalated": True,
                    "opinions": result["opinions"],
                    "director_decision": result["director_decision"],
                    "recommendation": result["recommendation"]
                }
            
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        
        if use_consilium:
            # Консилиум - несколько агентов голосуют
            result = self.consilium.consult(task)
            return {
                "success": True,
                "mode": "consilium",
                "task": task,
                "opinions": result["opinions"],
                "director_decision": result["director_decision"],
                "recommendation": result["recommendation"]
            }
        else:
            # Один агент
            if agent_name not in self.agents:
                return {
                    "success": False,
                    "error": f"Agent {agent_name} not found"
                }
            
            agent = self.agents[agent_name]
            
            try:
                response = agent.think(task)
                
                return {
                    "success": True,
                    "mode": "single",
                    "agent": agent_name,
                    "task": task,
                    "response": response,
                    "actions": []
                }
            
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
    
    def analyze_file(self, file_path: str, question: str, agent_name: str = "dev") -> Dict[str, Any]:
        """Анализ файла"""
        if agent_name not in self.agents:
            return {
                "success": False,
                "error": f"Agent {agent_name} not found"
            }
        
        agent = self.agents[agent_name]
        
        try:
            response = agent.analyze_code(file_path, question)
            
            return {
                "success": True,
                "agent": agent_name,
                "file": file_path,
                "question": question,
                "answer": response
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Статус всех агентов с метриками времени"""
        # Собираем timing от агентов orchestrator
        orchestrator_timing = {}
        all_llm_ms = []
        all_retrieval_ms = []
        
        for name, agent in self.agents.items():
            stats = agent.get_timing_stats()
            orchestrator_timing[name] = stats
            if stats["llm_samples"] > 0:
                all_llm_ms.append(stats["avg_llm_ms"])
            if stats["retrieval_samples"] > 0:
                all_retrieval_ms.append(stats["avg_retrieval_ms"])
        
        avg_llm_ms = round(sum(all_llm_ms) / len(all_llm_ms), 1) if all_llm_ms else 0
        avg_retrieval_ms = round(sum(all_retrieval_ms) / len(all_retrieval_ms), 1) if all_retrieval_ms else 0
        
        return {
            "avg_llm_ms": avg_llm_ms,
            "avg_retrieval_ms": avg_retrieval_ms,
            "timing_per_agent": orchestrator_timing,
            "agents": {
                name: {
                    "name": agent.name,
                    "role": agent.role,
                    "history_length": len(agent.conversation_history),
                    "repo_snapshot_cached": agent.repo_snapshot is not None
                }
                for name, agent in self.agents.items()
            },
            "consilium": self.consilium.get_status()
        }


# Lazy singleton для orchestrator
_orchestrator_instance: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """Получить singleton экземпляр оркестратора"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = Orchestrator()
    return _orchestrator_instance


# Для обратной совместимости
orchestrator = None
