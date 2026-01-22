Логируется событие rollback_outcome (simulated/approved/applied/skipped)

Тренд считает ROLLBACK_OUTCOMES по окну

Считается ROLLBACK_PRESSURE (OK/HIGH) по simulated

ROLLBACK_PRESSURE выводится в trend отчёт и CI summary

ROLLBACK_FEEDBACK выводится (QUALITY_DEGRADATION_CONFIRMED / none)

Никакие из этих сигналов сами по себе не применяют rollback

Поведение покрыто тестами
