# Postmortem: nginx agent-system upstream port

Root cause:
- nginx.conf for agent.* pointed to agent-system:7861 instead of agent-system:7864.

Impact:
- 443 listened and TLS/server_name were valid, but proxy traffic went nowhere,
  which produced 400/odd responses.

Why it took time:
- docker-compose had duplicate networks blocks (only the last one applied).
- Select-String output noise made it easy to misread config state.
- Symptoms resembled DNS/firewall/TLS issues.

What is correct now:
- agent/api/tools share the same backend (agent-system).
- agent -> 7864, api -> 8010, tools -> 8011.
- root_agent-network with alias agent-system keeps DNS stable.
- docker compose config renders cleanly (no warnings).

Follow-ups:
- Keep a short port map comment near proxy_pass (done).
- Consider adding explicit /health contracts for all services.
- Reduce host bloat (prune images/volumes, enable log rotation).
