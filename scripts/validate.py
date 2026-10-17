"""카탈로그 형식 검사(CI). 표준 라이브러리만 쓴다.

이름·경로·필수 키·금지 키만 본다. Field 속성과 도구 시그니처 대조는 agent 로더가 서브모듈을 올릴 때
pytest로 검사한다(도구 모듈이 agent에 있다)."""
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
OPTIONS_SOURCE_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
KINDS = {"trigger", "action", "search"}
NODE_TYPES = {"TRIGGER", "AI", "HTTP", "CONDITION", "TRANSFORM", "APPROVAL", "ACTION"}
APP_KEYS = {"provider", "title", "brand", "serviceType", "auth"}
# 경로·로더가 정하는 값 — 파일에 쓰면 두 군데가 어긋난다.
EVENT_FORBIDDEN = {"id", "app", "slots", "allowed_config_fields"}
# 프리셋 match는 허용 — AI 노드에 한해 프리셋 칸 규칙(정적 검증)을 고르는 데 쓴다. 이벤트는 event로만 판정해 match가 없다.
PRESET_FORBIDDEN = {"node_type", "builder", "event", "kind", "trigger_type", "slots", "allowed_config_fields"}
# 노드에서 지운 옛 필드 — 정의 fixed에도 golden_snippet에도 쓰지 않는다.
OLD_CONFIG_KEYS = ("triggerType", "serviceType")
ACTION_FIXED = {"type": "ACTION", "config": {}}  # 칸은 정의 fields, 도구는 tool_key — 골격에 남길 것이 없다
PRESET_EVENT = "ai.agent"  # 프리셋으로 만든 노드의 event


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load(root):
    apps = _read(os.path.join(root, "apps.json"))
    events = {}
    events_dir = os.path.join(root, "events")
    for app in sorted(os.listdir(events_dir)):
        app_dir = os.path.join(events_dir, app)
        if not os.path.isdir(app_dir):
            continue
        for name in sorted(os.listdir(app_dir)):
            if name.endswith(".json"):
                events[f"{app}.{name[:-5]}"] = _read(os.path.join(app_dir, name))
    return apps, events, _read(os.path.join(root, "presets.json"))


def _options_errors(where, entry):
    fields = list(entry.get("inputFields") or []) + [dict(v, key=k) for k, v in (entry.get("fields") or {}).items()
                                                     if isinstance(v, dict)]
    errs = []
    while fields:
        f = fields.pop()
        if not isinstance(f, dict):
            continue
        src = f.get("optionsSource")
        if src is not None and not (isinstance(src, str) and OPTIONS_SOURCE_RE.match(src)):
            errs.append(f"{where}: '{f.get('key')}'의 optionsSource '{src}'는 '<공급원>.<목록>' 형식이어야 한다.")
        fields.extend(f.get("children") or [])
    return errs


def _snippet_errors(where, snip, event, node_type):
    if snip is None:
        return []
    if not isinstance(snip, dict):
        return [f"{where}: golden_snippet은 JSON 객체다."]
    errs = []
    if snip.get("event") != event:
        errs.append(f"{where}: golden_snippet.event는 '{event}'여야 한다(지금 {snip.get('event')!r}).")
    if snip.get("type") != node_type:
        errs.append(f"{where}: golden_snippet.type은 '{node_type}'여야 한다(지금 {snip.get('type')!r}).")
    cfg = snip.get("config", {})
    if not isinstance(cfg, dict):
        errs.append(f"{where}: golden_snippet.config는 JSON 객체다.")
        cfg = {}
    for k in OLD_CONFIG_KEYS:
        if k in cfg:
            errs.append(f"{where}: golden_snippet.config.{k}는 지운 옛 필드다 — 노드 종류는 event로 정한다.")
    if node_type == "ACTION" and "tools" in cfg:
        errs.append(f"{where}: ACTION golden_snippet은 칸을 config.<칸>에 쓴다 — config.tools를 쓰지 않는다.")
    return errs


def check(apps, events, presets):
    errs = []
    for key, app in apps.items():
        if not NAME_RE.match(key):
            errs.append(f"apps.json: 앱 키 '{key}'는 소문자·숫자·밑줄이어야 한다.")
        if not isinstance(app, dict) or set(app) != APP_KEYS:
            errs.append(f"apps.json: '{key}'는 키 {sorted(APP_KEYS)}를 정확히 가져야 한다.")
            continue
        for k in ("provider", "title", "brand"):
            if not (isinstance(app[k], str) and app[k]):
                errs.append(f"apps.json: '{key}'.{k}는 빈 문자열일 수 없다.")
        for k in ("serviceType", "auth"):
            if app[k] is not None and not (isinstance(app[k], str) and app[k]):
                errs.append(f"apps.json: '{key}'.{k}는 문자열 또는 null이다.")

    for name, ev in events.items():
        app, _, event = name.partition(".")
        if not (NAME_RE.match(app) and NAME_RE.match(event)):
            errs.append(f"{name}: 경로는 events/<앱>/<이벤트>.json, 각 부분은 소문자·숫자·밑줄이다.")
        if app not in apps:
            errs.append(f"{name}: 앱 '{app}'가 apps.json에 없다.")
        if not isinstance(ev, dict):
            errs.append(f"{name}: 정의는 JSON 객체다.")
            continue
        bad = sorted(EVENT_FORBIDDEN & ev.keys())
        if bad:
            errs.append(f"{name}: {bad}는 경로·로더가 정한다 — 파일에 쓰지 않는다.")
        if ev.get("node_type") not in NODE_TYPES:
            errs.append(f"{name}: node_type '{ev.get('node_type')}'이 {sorted(NODE_TYPES)}에 없다.")
        if ev.get("kind") not in KINDS:
            errs.append(f"{name}: kind '{ev.get('kind')}'이 {sorted(KINDS)}에 없다.")
        is_trigger = ev.get("node_type") == "TRIGGER"
        if is_trigger != (ev.get("kind") == "trigger"):
            errs.append(f"{name}: TRIGGER 노드와 kind 'trigger'는 함께 다닌다.")
        if is_trigger and not (isinstance(ev.get("trigger_type"), str) and ev["trigger_type"]):
            errs.append(f"{name}: 트리거는 trigger_type이 필요하다.")
        if not is_trigger and "trigger_type" in ev:
            errs.append(f"{name}: trigger_type은 트리거만 쓴다.")
        fixed = ev.get("fixed") if isinstance(ev.get("fixed"), dict) else {}
        cfg = fixed.get("config") if isinstance(fixed.get("config"), dict) else {}
        for k in OLD_CONFIG_KEYS:
            if k in cfg:
                errs.append(f"{name}: fixed.config.{k}는 지운 옛 필드다 — 파일에 쓰지 않는다.")
        if "event" in fixed:
            errs.append(f"{name}: fixed.event는 로더가 넣는다 — 파일에 쓰지 않는다.")
        if ev.get("node_type") == "ACTION" and "tools" in cfg:
            errs.append(f"{name}: ACTION 도구는 tool_key로 정한다 — fixed.config.tools를 쓰지 않는다.")
        if ev.get("node_type") == "ACTION" and ev.get("fixed") != ACTION_FIXED:
            errs.append(f"{name}: ACTION fixed는 정확히 {json.dumps(ACTION_FIXED)}다(지금 {ev.get('fixed')!r}).")
        if "match" in ev:
            errs.append(f"{name}: 이벤트는 match를 쓰지 않는다 — 노드는 event로만 판정한다(AI 칸 규칙용 match는 presets.json).")
        errs += _options_errors(name, ev)
        errs += _snippet_errors(name, ev.get("golden_snippet"), name, ev.get("node_type"))

    seen = set()
    for p in presets:
        pid = p.get("id") if isinstance(p, dict) else None
        if not (isinstance(pid, str) and pid):
            errs.append(f"presets.json: id 없는 프리셋 {p!r:.60}")
            continue
        if pid in seen or pid in events:
            errs.append(f"presets.json: '{pid}'가 다른 프리셋·이벤트와 겹친다.")
        seen.add(pid)
        bad = sorted(PRESET_FORBIDDEN & p.keys())
        if bad:
            errs.append(f"presets.json: '{pid}'의 {bad}는 로더가 정한다(프리셋은 늘 AI·빌더 비노출·event ai.agent).")
        if "app" in p and p["app"] not in apps:
            errs.append(f"presets.json: '{pid}'의 앱 '{p['app']}'가 apps.json에 없다.")
        errs += _options_errors(pid, p)
        errs += _snippet_errors(pid, p.get("golden_snippet"), PRESET_EVENT, "AI")
    return errs


def check_against_base(base, head):
    """base(병합 대상)에 있던 이벤트가 head에서 사라지면(삭제·이름 변경) 경고만 한다. 지금은 저장 데이터가 없어
    막지 않는다 — 저장 노드가 생기면 그 event가 모르는 event가 되니 그때 규칙을 다시 정한다.
    프리셋은 노드에 저장되지 않아(노드 event는 ai.agent) 보지 않는다."""
    return [f"경고: 이벤트 '{name}'가 사라졌다(삭제 또는 이름 변경). 이 event를 저장한 노드는 모르는 event가 된다."
            for name in sorted(set(base[1]) - set(head[1]))]


def _snapshot(ref):
    """git ref의 카탈로그를 임시 폴더에 풀어 읽는다. ref가 없거나 그 ref에 카탈로그가 아직 없으면 None."""
    try:
        tar = subprocess.run(["git", "archive", ref], cwd=ROOT, check=True, capture_output=True).stdout
    except subprocess.CalledProcessError:
        return None  # 새 브랜치 푸시(before = 0000…)·첫 커밋
    tmp = tempfile.mkdtemp()
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(tmp, filter="data")
    try:
        return load(tmp)
    except FileNotFoundError:
        return None


def main(argv):
    head = load(ROOT)
    errs = check(*head)
    if len(argv) == 2 and argv[0] == "--base":
        base = _snapshot(argv[1])
        if base is not None:
            for w in check_against_base(base, head):
                print(w)
    for e in errs:
        print(e)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
