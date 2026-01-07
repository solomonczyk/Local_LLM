#!/usr/bin/env python3
"""Test script to check Agent class on remote server"""
import sys
sys.path.insert(0, '/app')

from agent_runtime.orchestrator.agent import Agent

# Test instantiation
try:
    a = Agent(name='test', role='test')
    print('Agent created OK')
    print(f'Has repo_snapshot: {hasattr(a, "repo_snapshot")}')
    print(f'Has conversation_history: {hasattr(a, "conversation_history")}')
    print(f'Has _retrieval_times: {hasattr(a, "_retrieval_times")}')
    print(f'Has _retry_base_delay: {hasattr(a, "_retry_base_delay")}')
except Exception as e:
    print(f'Error creating Agent: {e}')

# Check for import re
try:
    import agent_runtime.orchestrator.agent as agent_module
    has_re = hasattr(agent_module, 're') or 're' in dir(agent_module)
    print(f'Module has re imported: {has_re}')
except Exception as e:
    print(f'Error checking re: {e}')
