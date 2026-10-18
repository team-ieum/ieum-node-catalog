# 노드 카탈로그 스키마 (SSOT)

이 레포가 노드 이벤트 정의의 원본이다. BE·agent가 `catalog/` 서브모듈로 읽는다. 설계: ieum-backend
`docs/superpowers/specs/2026-10-13-node-event-catalog-design.md`.

항목은 두 곳에서 쓰인다.
- **생성(LLM)** — `generation: true` 항목. 로더가 필드에서 `slots`(LLM이 채울 자리)와
  `allowed_config_fields`(검증 화이트리스트)를 **파생**한다. 파일에 직접 쓰지 않는다.
- **빌더(FE)** — `builder: true` 항목. 카탈로그 API(`GET /v1/nodes/catalog`)가 `inputFields`를 내보낸다.

## 파일

- `events/<앱>/<이벤트>.json` — 이벤트 하나. 이름 = 경로(`gmail.new_email`). `id`·`app`을 쓰지 않는다.
- `apps.json` — 앱 키 → `provider`(공급자, 계정 연결·UI 묶음 단위. 내장은 `ieum`), `title`, `brand`(아이콘 키),
  `serviceType`(BE 표시 분류, 내장은 null), `auth`(BE 인증 준비 키, 내장은 null).
- `presets.json` — AI 프리셋 배열. 이벤트가 아니다: 생성 메뉴·슬롯 카탈로그·hydrate만 읽고, 빌더에는 나오지 않는다.
  프리셋으로 만든 노드의 `event`는 `ai.agent`. `node_type`·`builder`를 쓰지 않는다. `match`(`config.tools`·`agentType` 기준)는
  **AI 노드에 한해** 프리셋 칸 규칙(정적 검증)을 고르는 데만 쓴다. 노드 종류 판정은 `event`가 한다.
  앱 도구 프리셋은 `app`(앱 키)으로 provider·brand를 얻는다.

## 항목 필드

이벤트 파일 기준. 프리셋은 `node_type`·`kind`·`trigger_type`·`builder`를 쓰지 않는다(로더가 정한다).

| 필드 | 필수 | 설명 |
|---|---|---|
| `node_type` | ✅ | `TRIGGER` `AI` `ACTION` `HTTP` `CONDITION` `TRANSFORM` `APPROVAL` |
| `kind` | ✅ | `trigger`\|`action`\|`search`. 찾기·읽기·목록·조회는 `search` |
| `trigger_type` | 트리거만 ✅ | BE `TriggerType` 값 (예: `WEBHOOK`, `GMAIL_NEW_EMAIL`) |
| `tool_key` | ✅ | 바인딩하는 도구 키, 없으면 `null`. `_TOOL_MAP` 키, 또는 ACTION 전용 키 — `builtin:github_*`(동적 서비스 액션)·`_ACTION_ONLY_TOOLS`(되돌릴 수 없는 일이라 AI 노드에 안 싣는 도구, 예 `builtin:google_calendar_delete`). 둘 다 `tools.registry.resolve_action_fn`이 푼다 |
| `fixed` | ✅ | 불변 노드 골격(`type` + `config` 불변 키). `event`는 로더가 넣는다. 지운 옛 필드 `config.triggerType`·`config.serviceType`와 ACTION `config.tools`(도구는 `tool_key`)는 쓰지 않는다(쓰면 CI 거부). ACTION은 정확히 `{"type":"ACTION","config":{}}`(다른 키가 있으면 CI 거부) |
| `builder` / `generation` | ⬜ | 기본 `true`. 액션과 앱 트리거(`gmail.new_email`·`github.new_issue`)는 `generation: false`, 실행할 수 없는 액션(`gmail.send_email` — SMTP 자격증명 주입 경로 없음)은 `builder: false`. 프리셋은 `builder`를 쓰지 않는다(늘 빌더 비노출) |
| `title` / `description` | builder면 ✅ | 빌더에 보이는 항목 이름·한 문장 설명 |
| `tags` / `menu` | generation이면 ✅ | LLM 태그 검색·항상층 메뉴 |
| `inputFields` | ⬜ | config 직속 필드(Field 목록). AI 항목은 공통 필드(llmProvider·model·prompt·credentialId·systemMessage) 뒤에 붙고, 같은 key를 쓰면 공통 필드에 병합된다(예: 템플릿별 prompt `llm.hint`) |
| `outputFields` | ⬜ | 출력 필드(Field 목록). AI 항목은 공통 출력(output)이 앞에 붙는다. 액션은 도구 성공 반환 키와 같아야 한다(성공 테스트의 `assert_matches_outputs`) |
| `outputDynamic` | ⬜ | 최상위 출력 키가 실행마다 다름(수동·웹훅 트리거) |
| `outputsFrom` | ⬜ | 출력 키를 노드 config에서 읽음(`config.mappings` = 그 dict의 키, `config.outputFields` = 원소의 `key`). 경로 값이 비어 있지 않으면 정적 `outputFields` **전체를 대체**하고(합치지 않는다), 비었거나 없으면 정적 `outputFields`를 쓴다 |
| `match` | ⬜ | 프리셋만. AI 노드 → 프리셋 매칭 `{경로: 값}`(값 null = 없거나 빔). 평가 때 `type`은 노드 표기가 아니라 event가 정한 `AI`로 보고, 문자열 tools 원소는 정규화하지 않는다(agent Task 3·5). 조건 수 내림차순으로 평가하고, 프리셋끼리 같으면 거부. 이벤트에 쓰면 CI 거부(노드는 `event`로만 판정) |
| `fields` | ⬜ | 도구 필드 덮어쓰기 `{파라미터: 부분 Field}`. **도구당 한 항목만**(액션이 있으면 액션, 없으면 그 AI 항목). 시그니처 밖 키는 title·type 포함 전체 정의 |
| `golden_snippet` | ⬜ | 완성형 노드 예시(검색층 few-shot). `event` 필수: 이벤트는 자기 이름, 프리셋은 `ai.agent`. `type` 필수: 정의의 `node_type`(프리셋은 `AI`). `config`는 있으면 JSON 객체. `config.triggerType`·`config.serviceType`, ACTION `config.tools`를 쓰지 않는다(CI 거부). ACTION 칸은 `config.<칸>`. 그 자체로 검증을 통과해야 함 |
| `app` | ⬜ | 프리셋만. 앱 키(apps.json 키) — provider·brand를 얻는다 |
| `service` | ⬜ | 동적 서브에이전트 서비스명(ai.github_query) |

`slots`·`allowed_config_fields`를 파일에 쓰면 로더가 거부한다.

## Field

```jsonc
{"key": "spreadsheet_id", "title": "스프레드시트", "type": "string",
 "description": "대상 스프레드시트", "required": true, "default": "primary",
 "choices": [{"id": "page", "name": "페이지"}], "optionsSource": "google.spreadsheets",
 "optionsInputs": ["spreadsheet_id"], "list": false, "children": [], "dynamic": false, "ref": true,
 "path": "config.custom.path",                       // 직속 필드의 예외 경로만
 "llm": {"hint": "…", "slot": true, "name": "…", "kind": "expr", "inject": "model"}}
```
- `type`: `string` `text` `integer` `number` `boolean` `datetime` `cron` `json` `dict` `object`
- 도구 필드의 type·required·default는 시그니처에서 파생(덮어쓰기 가능). 실행 시 주입 인자(`RUNTIME_INJECTED_PARAMS`)는 빠진다.
- `default`는 키가 없을 때 실행이 쓰는 값이다. FE는 저장하지 않는다(키 있음 = 고정).
- `llm`은 생성 전용이다. `hint`=슬롯 설명, `slot: false`=슬롯 만들지 않음, `name`=표시 이름 슬롯
  `<key>_name`(경로 `…_names.<key>`), `kind`=기존 슬롯 kind 고정, `inject`=시스템 주입(provider|model).

## 파생 규칙 (core/node_fields.py)

- 경로: 직속 `config.<key>`. ACTION의 도구 필드도 `config.<key>`(ACTION config가 곧 칸). AI 프리셋 도구 필드는 `config.tools.0.config.<key>`. 정적 검증 에러 `field`도 이 경로를 그대로 쓴다.
- 슬롯 = label·description + 직속 필드 + `optionsSource`가 있는 도구 필드(항상 선택). `llm.slot: false` 제외.
- 슬롯 kind = `llm.kind` → `llm.inject` → choices면 enum → cron → dict면 mapping → string.
- 허용 config 키 = fixed.config 키 ∪ 직속 필드 최상위 키 ∪ (직속 optionsSource 필드가 있으면 `_names`).
- 카탈로그 응답의 `fixed.config.brand`는 로더가 계산한다: 이벤트와 앱 프리셋은 apps.json `brand`, 앱 없는 프리셋은 `service` → `SERVICE_BRAND`(없으면 `openai`). 로더 안에서는 intent 경로(`subagent_service_for_node`)를 타지 않는다 — `load_templates` 재진입으로 기동이 무한 재귀한다. 레지스트리 항목의 `fixed`에는 넣지 않고 응답 복사본에만 얹는다(생성 경로가 같은 `fixed`를 쓴다).

## 앱 이벤트 약속

앱마다 자기 도구 파일에서 구현하고 공용 코드는 두지 않는다. 맞추는 것은 아래 두 가지다. 새로 만들거나 손대는 이벤트부터 적용한다(기존 `notion.query_database`·`github.list_issues` 등은 그 앱 차례에).

1. **Search 이벤트 출력**: `found`(boolean)·`total`(integer)·`items`(list)가 필수다. 0건은 에러가 아니라 `{found:false, total:0, items:[]}` 성공이다. 출력 키는 늘 같다(0건 전용 키 없음 — 성공 테스트의 `assert_matches_outputs`가 `outputFields`와 대조한다).
2. **드롭다운 검색어 파라미터 이름은 `q`**: BE `IntegrationOptionService`는 `cursor` 밖의 쿼리를 전부 `inputs`로 넘기고, 검색을 지원하는 공급원만 `inputs.get("q")`를 읽는다. 공백뿐인 `q`는 없음으로 본다. `OptionSource` 인터페이스는 바꾸지 않는다. `q`를 `optionsInputs` 칸 key로 쓰지 않는다(CI 거부).

## 불변 규칙

1. 이름 = 경로, 프리셋 id는 이벤트 이름과 겹치지 않는다.
2. `tool_key`와 AI 항목 `fixed.config.tools[*].name`은 `_TOOL_MAP` 키이거나 `resolve_action_fn`이 푸는 ACTION 전용 키(`builtin:github_*`, `_ACTION_ONLY_TOOLS`)다(`mcp` 센티넬 제외). AI 항목 tools에는 `_TOOL_MAP` 키만 쓴다.
3. 도구 하나의 `fields`는 한 항목에만.
4. `optionsInputs`는 같은 항목의 필드 key만 가리킨다.
5. `golden_snippet`은 단독으로 `WorkflowValidator` 노드 검증을 통과해야 한다.
6. 프리셋의 match는 서로 달라야 한다(평가 순서: 조건 수 내림차순). 이벤트는 match를 쓰지 않는다.

## 버전 규칙

BE 카탈로그 ⊇ agent 카탈로그. 이벤트 추가는 BE 서브모듈을 먼저 올리고, 삭제·이름 변경은 agent를 먼저 올린다. 삭제·이름 변경은 CI(`--base`)가 경고만 한다. 저장 데이터가 생기면 규칙을 다시 정한다.
