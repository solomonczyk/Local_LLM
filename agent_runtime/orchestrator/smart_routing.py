"""
Smart Router для автоматического выбора агентов и режима консилиума
"""
from typing import Any, Dict, List, Tuple

# Триггеры для автоматического выбора режима и агентов
ROUTE_TRIGGERS = {
    # CRITICAL triggers - инциденты, аварии
    "critical": [
        "incident",
        "outage",
        "breach",
        "attack",
        "compromised",
        "emergency",
        "critical",
        "urgent",
        "production down",
    ],
    # Security triggers
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
    ],
    # Architecture triggers
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
    ],
    # QA triggers
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
    ],
    # SEO triggers
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
    ],
    # UX triggers
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
    ],
}

# Сильные триггеры (высокий confidence) vs слабые (низкий confidence)
STRONG_TRIGGERS = {
    "security": {"vulnerability", "injection", "xss", "csrf", "oauth", "jwt", "credential"},
    "architect": {"architecture", "microservice", "migration", "infrastructure", "ci/cd"},
    "qa": {"regression", "coverage", "integration test", "e2e", "unit test"},
    "seo": {"sitemap", "robots.txt", "schema.org", "canonical", "lighthouse"},
    "ux": {"accessibility", "a11y", "wcag", "design system"},
}

# Слабые триггеры (могут быть ложными срабатываниями)
WEAK_TRIGGERS = {
    "security": {"security", "auth", "token", "secret", "password"},
    "architect": {"database", "db", "scale", "performance", "perf", "refactor", "deploy"},
    "qa": {"test", "qa", "bug", "mock"},
    "seo": {"seo", "meta tag"},
    "ux": {"ux", "ui", "mobile", "responsive"},
}

def calculate_confidence(matched_triggers: Dict[str, List[str]]) -> Tuple[float, Dict[str, Any]]:
    """
    Рассчитать confidence (0-1) на основе силы триггеров.

    Returns:
        (confidence, breakdown) где breakdown содержит вклад каждого домена
    """
    if not matched_triggers:
        return 0.0, {}

    breakdown: Dict[str, Any] = {}
    domain_scores = []

    for domain, triggers in matched_triggers.items():
        if domain == "critical":
            domain_scores.append(1.0)
            breakdown[domain] = {
                "score": 1.0,
                "strong": triggers,
                "weak": [],
                "reason": "CRITICAL trigger always max",
            }
            continue

        strong = STRONG_TRIGGERS.get(domain, set())
        weak = WEAK_TRIGGERS.get(domain, set())

        strong_matched = [t for t in triggers if t in strong]
        weak_matched = [t for t in triggers if t in weak]
        strong_count = len(strong_matched)
        weak_count = len(weak_matched)

        # Базовый score домена
        if strong_count > 0:
            base_score = 0.8 + min(strong_count * 0.1, 0.2)  # 0.8-1.0
            reason = f"{strong_count} strong trigger(s)"
        elif weak_count > 0:
            base_score = 0.4 + min(weak_count * 0.1, 0.2)  # 0.4-0.6
            reason = f"{weak_count} weak trigger(s) only"
        else:
            base_score = 0.5
            reason = "unknown triggers"

        domain_scores.append(base_score)
        breakdown[domain] = {
            "score": round(base_score, 2),
            "strong": strong_matched,
            "weak": weak_matched,
            "reason": reason,
        }

    # Итоговый confidence = среднее по доменам
    confidence = round(sum(domain_scores) / len(domain_scores), 2) if domain_scores else 0.0

    # Добавляем итоговую информацию
    breakdown["_summary"] = {
        "total_confidence": confidence,
        "domains_count": len(domain_scores),
        "formula": "avg(domain_scores)",
    }

    return confidence, breakdown

def route_agents(query: str) -> Dict[str, Any]:
    """
    Умный роутер: выбирает режим и агентов по содержимому запроса.

    Правила эскалации:
    - CRITICAL triggers (incident/breach/etc) → сразу CRITICAL + все агенты
    - 3+ доменов + confidence >= 0.7 → CRITICAL + director
    - 3+ доменов + confidence < 0.7 → STANDARD (понижение, без director)
    - 2 домена → STANDARD
    - 1 домен или 0 → FAST (только dev)

    Returns:
        {
            "mode": "FAST|STANDARD|CRITICAL",
            "agents": ["dev", ...],
            "triggers_matched": {"security": ["token", "auth"], ...},
            "domains_matched": 2,
            "confidence": 0.85,
            "reason": "..."
        }
    """
    query_lower = query.lower()
    matched_triggers: Dict[str, List[str]] = {}
    required_agents = {"dev"}  # dev всегда включён

    # Проверяем CRITICAL триггеры
    for trigger in ROUTE_TRIGGERS["critical"]:
        if trigger in query_lower:
            matched_triggers.setdefault("critical", []).append(trigger)

    # Если CRITICAL trigger - возвращаем сразу все агенты
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

    # Проверяем остальные триггеры (домены)
    for agent_type, triggers in ROUTE_TRIGGERS.items():
        if agent_type == "critical":
            continue
        for trigger in triggers:
            if trigger in query_lower:
                matched_triggers.setdefault(agent_type, []).append(trigger)
                required_agents.add(agent_type)

    # Считаем количество доменов и confidence
    domains_matched = len(required_agents) - 1  # минус dev
    confidence, confidence_breakdown = calculate_confidence(matched_triggers)

    # Правила эскалации по количеству доменов + confidence
    downgraded = False
    if domains_matched >= 3:
        if confidence >= 0.7:
            # 3+ домена + высокий confidence → CRITICAL + director
            mode = "CRITICAL"
            agents = list(required_agents) + ["director"]
            reason = f"Escalation: {domains_matched} domains, confidence={confidence} → CRITICAL"
        else:
            # 3+ домена + низкий confidence → понижаем до STANDARD
            mode = "STANDARD"
            agents = list(required_agents)
            reason = f"Downgrade: {domains_matched} domains but confidence={confidence} < 0.7 → STANDARD"
            downgraded = True
    elif domains_matched == 2:
        mode = "STANDARD"
        agents = list(required_agents)
        reason = f"Escalation: {domains_matched} domains → STANDARD"
    elif domains_matched == 1:
        mode = "STANDARD"
        agents = list(required_agents)
        reason = f"Single domain matched → STANDARD"
    else:
        mode = "FAST"
        agents = ["dev"]
        confidence = 1.0  # FAST всегда уверен
        confidence_breakdown = {"_summary": {"total_confidence": 1.0, "reason": "FAST mode default"}}
        reason = "No specific triggers, using FAST mode"

    # Добавляем детали триггеров в reason
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
