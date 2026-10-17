# ieum-node-catalog

IEUM 노드 이벤트 정의의 원본. ieum-backend·ieum-agent가 `catalog/` 서브모듈로 특정 커밋에 고정해 읽는다.
형식은 SCHEMA.md, 설계는 ieum-backend `docs/superpowers/specs/2026-10-13-node-event-catalog-design.md`.

- 검사: `python scripts/validate.py` (PR은 `--base origin/main`으로 이벤트 삭제·이름 변경을 **경고** — 실패시키지 않는다)
- 노드 칸 경로: ACTION `config.<key>`, AI 프리셋 도구 칸 `config.tools.0.config.<key>`, 그 밖의 직속 칸 `config.<key>`(트리거 `config.cron` 등)
- 테스트: `python -m unittest discover -s tests`
- 버전 규칙: BE 카탈로그 ⊇ agent 카탈로그. 이벤트 추가는 BE 서브모듈을 먼저, 삭제·이름 변경은 agent를 먼저 올린다.
