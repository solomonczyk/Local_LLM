"""
Smart Router for automatic selection of agents and Consilium mode.

Design goals:
- Prefer FAST (dev-only) when the task is narrow/clear.
- Escalate to STANDARD when one/two specialized domains are detected.
- Escalate to CRITICAL when multiple domains are strongly detected or there is a real incident/outage scenario.

Important:
- Triggers are intentionally substring-based ("in" checks). Keep them conservative to avoid false escalation.
- Russian + English triggers are supported (local-first UX).
"""

from typing import Any, Dict, List, Tuple

# Trigger lists per domain. These are simple substring matches against query.lower().
ROUTE_TRIGGERS: Dict[str, List[str]] = {
    # CRITICAL: only real incidents/outages/breaches (avoid generic "critical"/"urgent").
    "critical": [
        "incident",
        "outage",
        "breach",
        "attack",
        "compromised",
        "production down",
        "data loss",
        "leak",
        "incident response",
        # RU
        "инцидент",
        "инцидент безопасности",
        "атака",
        "взлом",
        "компрометация",
        "компрометирован",
        "утечка",
        "потеря данных",
        "прод упал",
        "прод лежит",
        "простой сервиса",
        "простой прод",
    ],
    "security": [
        "security",
        "auth",
        "token",
        "secret",
        "vuln",
        "vulnerability",
        "password",
        "credential",
        "injection",
        "xss",
        "csrf",
        "encrypt",
        "permission",
        "access control",
        "oauth",
        "jwt",
        # RU
        "безопасность",
        "аутентификация",
        "авторизация",
        "токен",
        "секрет",
        "уязвимость",
        "пароль",
        "учетные данные",
        "инъекция",
        "xss",
        "csrf",
        "шифрование",
        "доступ",
        "контроль доступа",
        "oauth",
        "jwt",
        "cve",
    ],
    "architect": [
        "architecture",
        "migration",
        "database",
        "db",
        "scale",
        "scaling",
        "performance",
        "perf",
        "refactor",
        "design pattern",
        "microservice",
        "infrastructure",
        "deploy",
        "ci/cd",
        "load balancer",
        "docker",
        "nginx",
        "kubernetes",
        "k8s",
        # RU
        "архитектура",
        "миграция",
        "база данных",
        "бд",
        "масштабирование",
        "производительность",
        "рефакторинг",
        "паттерн",
        "микросервис",
        "инфраструктура",
        "деплой",
        "ci/cd",
        "балансировщик",
        "docker",
        "nginx",
        "kubernetes",
        "k8s",
    ],
    "qa": [
        "test",
        "qa",
        "regression",
        "coverage",
        "bug",
        "edge case",
        "unit test",
        "integration test",
        "e2e",
        "mock",
        "fixture",
        # RU
        "тест",
        "тестирование",
        "регрессия",
        "покрытие",
        "баг",
        "юнит",
        "интеграционный",
        "e2e",
        "мок",
        "фикстура",
    ],
    "seo": [
        "seo",
        "search engine",
        "meta tag",
        "sitemap",
        "robots.txt",
        "canonical",
        "structured data",
        "schema.org",
        "lighthouse",
        # RU
        "поисковая оптимизация",
        "мета тег",
        "мета теги",
        "sitemap",
        "robots.txt",
        "канонический",
        "структурированные данные",
        "schema.org",
    ],
    "ux": [
        "ux",
        "ui",
        "user experience",
        "accessibility",
        "a11y",
        "wcag",
        "usability",
        "responsive",
        "mobile",
        "design system",
        # RU
        "пользовательский опыт",
        "доступность",
        "юзабилити",
        "адаптив",
        "мобильный",
        "дизайн система",
        "дизайн-система",
        "интерфейс",
        "wcag",
        "ui",
    ],
}

# Strong vs weak triggers: used only for confidence scoring, not for matching.
STRONG_TRIGGERS = {
    "security": {
        "vulnerability",
        "injection",
        "xss",
        "csrf",
        "oauth",
        "jwt",
        "credential",
        "cve",
        "уязвимость",
        "инъекция",
        "xss",
        "csrf",
        "oauth",
        "jwt",
    },
    "architect": {
        "architecture",
        "microservice",
        "migration",
        "infrastructure",
        "ci/cd",
        "kubernetes",
        "docker",
        "архитектура",
        "микросервис",
        "миграция",
        "инфраструктура",
        "ci/cd",
        "kubernetes",
        "docker",
    },
    "qa": {
        "regression",
        "coverage",
        "integration test",
        "e2e",
        "unit test",
        "регрессия",
        "покрытие",
        "интеграционный тест",
        "юнит тест",
        "e2e",
    },
    "seo": {"sitemap", "robots.txt", "schema.org", "canonical", "lighthouse", "канонический", "структурированные данные"},
    "ux": {
        "accessibility",
        "a11y",
        "wcag",
        "design system",
        "доступность",
        "юзабилити",
        "дизайн система",
        "дизайн-система",
        "пользовательский опыт",
    },
}

WEAK_TRIGGERS = {
    "security": {
        "security",
        "auth",
        "token",
        "secret",
        "password",
        "безопасность",
        "аутентификация",
        "авторизация",
        "токен",
        "секрет",
        "пароль",
        "учетные данные",
        "контроль доступа",
    },
    "architect": {
        "database",
        "db",
        "scale",
        "performance",
        "perf",
        "refactor",
        "deploy",
        "nginx",
        "docker",
        "база данных",
        "бд",
        "масштабирование",
        "производительность",
        "рефакторинг",
        "деплой",
        "инфраструктура",
    },
    "qa": {"test", "qa", "bug", "mock", "тест", "тестирование", "баг", "мок", "фикстура"},
    "seo": {"seo", "meta tag", "поисковая оптимизация", "мета тег", "мета теги"},
    "ux": {"ux", "ui", "mobile", "responsive", "мобильный", "адаптив", "интерфейс"},
}


def calculate_confidence(matched_triggers: Dict[str, List[str]]) -> Tuple[float, Dict[str, Any]]:
    if not matched_triggers:
        return 0.0, {}

    breakdown: Dict[str, Any] = {}
    domain_scores: List[float] = []

    for domain, triggers in matched_triggers.items():
        if domain == "critical":
            domain_scores.append(1.0)
            breakdown[domain] = {"score": 1.0, "strong": triggers, "weak": [], "reason": "CRITICAL always max"}
            continue

        strong = STRONG_TRIGGERS.get(domain, set())
        weak = WEAK_TRIGGERS.get(domain, set())

        strong_matched = [t for t in triggers if t in strong]
        weak_matched = [t for t in triggers if t in weak]
        strong_count = len(strong_matched)
        weak_count = len(weak_matched)

        if strong_count > 0:
            base_score = 0.8 + min(strong_count * 0.1, 0.2)  # 0.8-1.0
            reason = f"{strong_count} strong trigger(s)"
        elif weak_count > 0:
            base_score = 0.4 + min(weak_count * 0.1, 0.3)  # 0.4-0.7
            reason = f"{weak_count} weak trigger(s)"
        else:
            base_score = 0.3
            reason = "unknown trigger strength"

        domain_scores.append(base_score)
        breakdown[domain] = {
            "score": base_score,
            "strong": strong_matched,
            "weak": weak_matched,
            "reason": reason,
        }

    confidence = sum(domain_scores) / len(domain_scores) if domain_scores else 0.0
    breakdown["_summary"] = {"total_confidence": confidence, "domains": len(domain_scores)}
    return round(confidence, 3), breakdown


def route_agents(query: str) -> Dict[str, Any]:
    """
    Auto-select agents + mode from the text query.

    Escalation rules:
    - If CRITICAL triggers matched: CRITICAL + all agents + director
    - If 3+ domains and confidence >= 0.7: CRITICAL + director
    - If 3+ domains and confidence < 0.7: STANDARD (downgraded, no director)
    - If 2 domains: STANDARD
    - If 1 domain: STANDARD
    - Else: FAST (dev only)
    """
    query_lower = query.lower()
    matched_triggers: Dict[str, List[str]] = {}
    required_agents = {"dev"}  # dev always included

    # CRITICAL triggers
    for trigger in ROUTE_TRIGGERS["critical"]:
        if trigger in query_lower:
            matched_triggers.setdefault("critical", []).append(trigger)

    if "critical" in matched_triggers:
        _, breakdown = calculate_confidence(matched_triggers)
        return {
            "mode": "CRITICAL",
            "agents": ["dev", "security", "qa", "architect", "seo", "ux", "director"],
            "triggers_matched": matched_triggers,
            "domains_matched": len(matched_triggers),
            "confidence": 1.0,
            "confidence_breakdown": breakdown,
            "downgraded": False,
            "reason": f"CRITICAL triggers: {matched_triggers['critical']}",
        }

    # Domain triggers
    for agent_type, triggers in ROUTE_TRIGGERS.items():
        if agent_type == "critical":
            continue
        for trigger in triggers:
            if trigger in query_lower:
                matched_triggers.setdefault(agent_type, []).append(trigger)
                required_agents.add(agent_type)

    domains_matched = len(required_agents) - 1  # excluding dev
    confidence, confidence_breakdown = calculate_confidence(matched_triggers)

    downgraded = False
    if domains_matched >= 3:
        if confidence >= 0.7:
            mode = "CRITICAL"
            agents = list(required_agents) + ["director"]
            reason = f"Escalation: {domains_matched} domains, confidence={confidence} -> CRITICAL"
        else:
            mode = "STANDARD"
            agents = list(required_agents)
            reason = f"Downgrade: {domains_matched} domains but confidence={confidence} < 0.7 -> STANDARD"
            downgraded = True
    elif domains_matched == 2:
        mode = "STANDARD"
        agents = list(required_agents)
        reason = f"Escalation: {domains_matched} domains -> STANDARD"
    elif domains_matched == 1:
        mode = "STANDARD"
        agents = list(required_agents)
        reason = "Single domain matched -> STANDARD"
    else:
        mode = "FAST"
        agents = ["dev"]
        confidence = 1.0
        confidence_breakdown = {"_summary": {"total_confidence": 1.0, "reason": "FAST mode default"}}
        reason = "No specific triggers, using FAST mode"

    if matched_triggers:
        trigger_summary = ", ".join(f"{k}: {v[:2]}" for k, v in matched_triggers.items())
        reason = f"{reason} | Matched: {trigger_summary}"

    return {
        "mode": mode,
        "agents": agents,
        "triggers_matched": matched_triggers,
        "domains_matched": domains_matched,
        "confidence": confidence,
        "confidence_breakdown": confidence_breakdown,
        "downgraded": downgraded,
        "reason": reason,
    }
