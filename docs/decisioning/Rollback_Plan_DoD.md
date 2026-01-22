# Rollback Plan — Definition of Done

Rollback считается реализованным, если:

- [x] Rollback определяется как dry-run (без автоматического применения)
- [x] Выводится строка ROLLBACK_PLAN: ...
- [x] ROLLBACK отображается в CI summary
- [x] При наличии плана создаётся rollback_plan.json
- [x] При отсутствии плана файл не создаётся
- [x] rollback_plan.json публикуется как CI artifact (conditional)
- [x] Поведение покрыто автотестами
- [x] Rollback не блокирует CI, а информирует

Rollback = управляемый, воспроизводимый путь отката.
