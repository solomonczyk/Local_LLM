--simulate-rollback не вносит изменений

при наличии rollback_plan.json печатает policy/action/affected_rules/expected_effect

affected_rules >= 1, expected_effect не пустой

есть режим PASS/FAIL + sys.exit(0/2)

включено в CI summary

поведение покрыто тестом (валидный и невалидный вывод)
