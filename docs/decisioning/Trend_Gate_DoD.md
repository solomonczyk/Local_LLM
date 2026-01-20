# Trend Gate v1 — Definition of Done

Trend gate в CI запускается по окну 24h: --windows-minutes 1440

Исключается legacy: --exclude-class legacy_unknown

Policy выключена для чистой оценки: --policy-off

Вывод сохраняется в data/reports/decision_trend.txt и публикуется как artifact

Если TREND: INSUFFICIENT_DATA -> TREND_GATE: SOFT (insufficient_data) и CI не падает

Если TREND: FAIL -> CI падает (exit != 0)

Если TREND: PASS/WARN -> CI проходит

Поведение покрыто тестом (минимум 2 кейса: insufficient_data и fail)
