"""카탈로그 형식 검사(CI). 표준 라이브러리만 쓴다.

이름·경로·필수 키·별칭 규칙만 본다. Field 속성과 도구 시그니처 대조는 agent 로더가 서브모듈을 올릴 때
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
# 프리셋 match는 허용 — 빌더엔 안 나오지만 저장 노드 매칭(정적 검증 칸 규칙)에 쓰인다.
PRESET_FORBIDDEN = {"node_type", "builder", "event", "kind", "trigger_type", "slots", "allowed_config_fields"}


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
    return apps, events, _read(os.path.join(root, "presets.json")), _read(os.path.join(root, "aliases.json"))


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


def check(apps, events, presets, aliases):
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
        for k in ("triggerType", "serviceType"):
            if k in cfg:
                errs.append(f"{name}: fixed.config.{k}는 로더가 넣는다 — 파일에 쓰지 않는다.")
        if "event" in fixed:
            errs.append(f"{name}: fixed.event는 로더가 넣는다 — 파일에 쓰지 않는다.")
        errs += _options_errors(name, ev)

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

    for old, new in aliases.items():
        # 별칭은 고칠 수 없으니(check_against_base) 이름을 두 번 바꾸면 사슬이 된다: 끝까지 따라가 이벤트에 닿으면 된다.
        seen = set()
        while new not in events and new in aliases and new not in seen:
            seen.add(new)
            new = aliases[new]
        if new not in events:
            errs.append(f"aliases.json: '{old}' → '{aliases[old]}'가 이벤트로 이어지지 않는다.")
    return errs


def check_against_base(base, head):
    """base(병합 대상)에 있던 이름은 head에 남아 있거나 aliases로 이어져야 하고, 별칭은 지우거나 바꿀 수 없다.
    저장된 노드가 옛 이름을 들고 있어서다."""
    _, b_events, b_presets, b_aliases = base
    _, h_events, h_presets, h_aliases = head
    errs = []
    for old, new in b_aliases.items():
        if h_aliases.get(old) != new:
            errs.append(f"aliases.json: '{old}' → '{new}'를 지우거나 바꿀 수 없다.")
    h_names = set(h_events) | {p.get("id") for p in h_presets}
    for name in sorted(set(b_events) | {p.get("id") for p in b_presets}):
        if name not in h_names and name not in h_aliases:
            errs.append(f"'{name}'를 지우거나 이름을 바꾸려면 aliases.json에 '{name}': '<이어받을 이벤트>'가 필요하다.")
    return errs


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
            errs += check_against_base(base, head)
    for e in errs:
        print(e)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
