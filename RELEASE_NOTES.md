# v1.0.19

## Новое
- feat(talent): add the nine Mistras resources (green/blue/purple)
- feat(treasury): flag and freeze periods dwar no longer serves
- feat(clan): separate ui_structure_role, it wins over imported clan_role

## Исправления
- fix(ui): coverage months in chronological order, not in JS key order
- fix(treasury): say it out loud when an import is cut short
- fix(treasury): re-estimate from the learned boundary, not from the request
- fix(deps): pin SQLAlchemy <2.1 — CI could not connect to PostgreSQL
- fix(treasury): parse every report row — half the operations were dropped
- fix: deputies/council come from saved JSON, not from clan_role
- fix(ui): editable clan-structure deputies/council with delete + cleanup
- fix: clan role parsing + enforce single-leader invariant on imports
- fix(ui): clan members table — separate roles and trial badge

## Прочее
- refactor(ui): shorter Mistras column labels
- test: make ui_structure_role tests hermetic
- Revert "feat: treasury analytics flags characters missing from the clan roster"
- Revert "chore(release): v1.0.18 [skip ci]"

