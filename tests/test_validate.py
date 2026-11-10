import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import validate  # noqa: E402

# 앱 이벤트 약속 1(Search 출력)을 지키는 GitHub search 이벤트. list_issues·get_pr_files는 옛 모양이라 뺀다.
GITHUB_SEARCH_EVENTS = {"github.find_issue", "github.find_pull_request", "github.get_pr_reviews",
                        "github.find_branch", "github.get_file", "github.find_repo", "github.find_org",
                        "github.check_org_membership", "github.find_user"}

SHEETS_SEARCH_EVENTS = {"google_sheets.lookup_row", "google_sheets.read", "google_sheets.lookup_rows",
                        "google_sheets.get_rows", "google_sheets.get_row", "google_sheets.find_spreadsheet",
                        "google_sheets.find_worksheet", "google_sheets.get_spreadsheet"}

SHEETS_ROW_EVENTS = {
    "google_sheets.append_rows": ["spreadsheet_id", "sheet_id", "rows", "column_map", "value_input_option"],
    "google_sheets.update_rows": ["spreadsheet_id", "sheet_id", "rows", "column_map", "overwrite_all",
                                  "value_input_option"],
    "google_sheets.clear_rows": ["spreadsheet_id", "sheet_id", "row_numbers"],
    "google_sheets.delete_rows": ["spreadsheet_id", "sheet_id", "row_numbers", "confirm_delete"],
    "google_sheets.format_rows": ["spreadsheet_id", "sheet_id", "row_numbers", "background_color", "text_color",
                                  "bold", "italic", "strikethrough"],
}

# 시트·파일 ACTION 이벤트 → (입력 칸 순서 = 도구 시그니처, 출력 칸 순서).
SHEETS_SHEET_EVENTS = {
    "google_sheets.create_worksheet": (["spreadsheet_id", "title", "headers"], ["spreadsheet_id", "sheet_id", "title"]),
    "google_sheets.copy_worksheet": (["spreadsheet_id", "sheet_id", "destination_spreadsheet_id", "new_title"],
                                     ["spreadsheet_id", "sheet_id", "title"]),
    "google_sheets.rename_worksheet": (["spreadsheet_id", "sheet_id", "new_title"], ["sheet_id", "title", "previous_title"]),
    "google_sheets.update_worksheet": (["spreadsheet_id", "sheet_id", "frozen_rows", "frozen_columns", "position", "visibility"],
                                       ["sheet_id", "title", "updated"]),
    "google_sheets.delete_worksheet": (["spreadsheet_id", "sheet_id", "confirm_delete"], ["deleted", "sheet_id", "title"]),
    "google_sheets.create_spreadsheet": (["title", "folder_id", "copy_from", "headers"], ["spreadsheet_id", "title", "url"]),
    "google_sheets.find_or_create_spreadsheet": (["title", "folder_id", "copy_from", "headers"],
                                                 ["created", "spreadsheet_id", "title", "url"]),
    "google_sheets.find_or_create_worksheet": (["spreadsheet_id", "title", "headers"], ["created", "sheet_id", "title"]),
}

GMAIL_SEND_KEYS = ["to", "cc", "bcc", "from_email", "from_name", "reply_to", "subject", "body_format", "body",
                   "include_signature", "label_ids"]
GMAIL_MAIL_KEYS = ["messageId", "threadId", "from", "to", "subject", "snippet", "bodyText", "receivedAt", "labels"]
SHEETS_RANGE_FIELDS = {
    "google_sheets.add_column": ["spreadsheet_id", "sheet_id", "title", "before_column"],
    "google_sheets.copy_range": ["spreadsheet_id", "sheet_id", "source_range", "destination_range", "paste_type",
                                 "paste_orientation"],
    "google_sheets.sort_range": ["spreadsheet_id", "sheet_id", "sort_column", "sort_order", "cell_range"],
    "google_sheets.format_range": ["spreadsheet_id", "sheet_id", "cell_range", "number_format", "number_pattern",
                                   "background_color", "text_color", "bold", "italic", "strikethrough",
                                   "horizontal_alignment", "vertical_alignment", "wrap_strategy"],
    "google_sheets.add_conditional_format": ["spreadsheet_id", "sheet_id", "cell_range", "condition", "value_1",
                                             "value_2", "relative_date", "background_color", "text_color", "bold",
                                             "italic", "strikethrough"],
    "google_sheets.set_data_validation": ["spreadsheet_id", "sheet_id", "cell_range", "condition", "value_1",
                                          "value_2", "values", "input_message", "strict", "show_dropdown"],
}
SHEETS_RANGE_OUTPUTS = {"google_sheets.add_column": ["column", "title"],
                        "google_sheets.copy_range": ["source", "destination"]}  # 나머지 4개는 ["range"]
_NO_REF = {"spreadsheet_id", "sheet_id", "before_column", "sort_column", "bold", "italic", "strikethrough",
           "strict", "show_dropdown"}
FORMS_RESPONSE_KEYS = ["responseId", "submittedAt", "createdAt", "respondentEmail", "answers", "answerList", "totalScore"]

APP = {"provider": "google", "title": "Gmail", "brand": "gmail", "serviceType": "GOOGLE", "auth": "google_oauth"}


def _event(**over):
    ev = {"node_type": "ACTION", "kind": "action", "tool_key": "gmail",
          "fixed": {"type": "ACTION", "config": {}}}
    ev.update(over)
    return ev


def _trigger(**over):
    ev = {"node_type": "TRIGGER", "kind": "trigger", "trigger_type": "GMAIL_NEW_EMAIL", "tool_key": None,
          "fixed": {"type": "TRIGGER", "config": {}}}
    ev.update(over)
    return ev


class CheckTest(unittest.TestCase):
    def ok(self, apps=None, events=None, presets=None):
        return validate.check(apps if apps is not None else {"gmail": APP},
                              events if events is not None else {"gmail.send_email": _event()},
                              presets or [])

    def test_valid_catalog_has_no_errors(self):
        self.assertEqual(self.ok(), [])

    def test_event_name_must_be_lower_snake(self):
        errs = self.ok(events={"gmail.SendEmail": _event()})
        self.assertTrue(any("gmail.SendEmail" in e for e in errs), errs)

    def test_event_app_must_exist_in_apps(self):
        errs = self.ok(events={"slack.send_message": _event()})
        self.assertTrue(any("apps.json" in e for e in errs), errs)

    def test_event_must_not_carry_id_or_app(self):
        errs = self.ok(events={"gmail.send_email": _event(id="x", app="gmail")})
        self.assertTrue(any("id" in e and "app" in e for e in errs), errs)

    def test_kind_must_be_known(self):
        errs = self.ok(events={"gmail.send_email": _event(kind="read")})
        self.assertTrue(any("kind" in e for e in errs), errs)

    def test_trigger_needs_trigger_type_and_kind_trigger(self):
        errs = self.ok(events={"gmail.new_email": _trigger(trigger_type=None)})
        self.assertTrue(any("trigger_type" in e for e in errs), errs)
        errs = self.ok(events={"gmail.new_email": _trigger(kind="action")})
        self.assertTrue(any("kind" in e for e in errs), errs)

    def test_non_trigger_must_not_have_trigger_type(self):
        errs = self.ok(events={"gmail.send_email": _event(trigger_type="MANUAL")})
        self.assertTrue(any("trigger_type" in e for e in errs), errs)

    def test_old_fixed_keys_must_not_be_written(self):
        for cfg in ({"triggerType": "GMAIL_NEW_EMAIL"}, {"serviceType": "GOOGLE"}):
            errs = self.ok(events={"gmail.new_email": _trigger(fixed={"type": "TRIGGER", "config": cfg})})
            self.assertTrue(errs, cfg)
        errs = self.ok(events={"gmail.new_email": _trigger(fixed={"type": "TRIGGER", "event": "x", "config": {}})})
        self.assertTrue(any("event" in e for e in errs), errs)

    def test_event_must_not_have_match(self):
        errs = self.ok(events={"gmail.new_email": _trigger(match={"type": "TRIGGER"})})
        self.assertTrue(any("match" in e for e in errs), errs)

    def test_action_fixed_config_tools_forbidden(self):
        bad = _event(fixed={"type": "ACTION", "config": {"tools": [{"name": "gmail"}]}})
        errs = self.ok(events={"gmail.send_email": bad})
        self.assertTrue(any("fixed.config.tools" in e for e in errs), errs)

    def test_ai_event_fixed_tools_still_allowed(self):
        ai = {"node_type": "AI", "kind": "action", "tool_key": None,
              "fixed": {"type": "AI", "config": {"agentType": "react", "credentialId": "", "tools": []}}}
        self.assertEqual(self.ok(apps={"ai": APP}, events={"ai.agent": ai}), [])

    def test_action_fixed_must_be_exact(self):
        for fixed in ({"type": "ACTION", "config": {"credentialId": ""}}, {"type": "ACTION", "config": {}, "tool": "x"},
                      {"type": "ACTION"}):
            errs = self.ok(events={"gmail.send_email": _event(fixed=fixed)})
            self.assertTrue(any("ACTION fixed" in e for e in errs), (fixed, errs))

    def test_options_source_format(self):
        bad = _event(inputFields=[{"key": "a", "optionsSource": "Google Calendars"}])
        self.assertTrue(self.ok(events={"gmail.send_email": bad}))
        nested = _event(fields={"a": {"children": [{"key": "b", "optionsSource": "nope"}]}})
        self.assertTrue(self.ok(events={"gmail.send_email": nested}))
        good = _event(inputFields=[{"key": "a", "optionsSource": "google.calendars"}])
        self.assertEqual(self.ok(events={"gmail.send_email": good}), [])

    def test_options_inputs_must_not_use_q(self):
        """q는 드롭다운 검색어 파라미터 이름이다(SCHEMA 앱 이벤트 약속 2) — 칸 key로 넘기면 검색어와 섞인다."""
        bad = _event(fields={"a": {"optionsSource": "google.events", "optionsInputs": ["q"]}})
        errs = self.ok(events={"gmail.send_email": bad})
        self.assertTrue(any("'q'" in e for e in errs), errs)
        good = _event(fields={"a": {"optionsSource": "google.events", "optionsInputs": ["calendar_id"]}})
        self.assertEqual(self.ok(events={"gmail.send_email": good}), [])

    def test_fields_source_format(self):
        bad = _event(fields={"props": {"type": "dict", "fieldsSource": "Notion Properties"}})
        errs = self.ok(events={"gmail.send_email": bad})
        self.assertTrue(any("fieldsSource" in e and "형식" in e for e in errs), errs)
        good = _event(fields={"props": {"type": "dict", "fieldsSource": "notion.properties",
                                        "fieldsInputs": ["data_source_id"]}})
        self.assertEqual(self.ok(events={"gmail.send_email": good}), [])

    def test_fields_source_only_on_dict(self):
        """fieldsSource는 dict 칸의 안쪽 칸 목록이다 — 시그니처 파생 type(object)을 dict로 덮지 않으면 거부한다."""
        for over in ({"type": "object"}, {}):
            bad = _event(fields={"props": {**over, "fieldsSource": "notion.properties"}})
            errs = self.ok(events={"gmail.send_email": bad})
            self.assertTrue(any("type 'dict'" in e for e in errs), (over, errs))

    def test_fields_inputs_needs_fields_source(self):
        bad = _event(fields={"props": {"type": "dict", "fieldsInputs": ["data_source_id"]}})
        errs = self.ok(events={"gmail.send_email": bad})
        self.assertTrue(any("fieldsInputs는 fieldsSource와 함께" in e for e in errs), errs)

    def test_fields_inputs_must_not_use_q(self):
        bad = _event(fields={"props": {"type": "dict", "fieldsSource": "notion.properties", "fieldsInputs": ["q"]}})
        errs = self.ok(events={"gmail.send_email": bad})
        self.assertTrue(any("fieldsInputs에 'q'" in e for e in errs), errs)

    def test_output_fields_source_format(self):
        bad = _event(outputFields=[{"key": "answers", "title": "답", "type": "dict", "fieldsSource": "Form Q"}])
        errs = self.ok(events={"gmail.send_email": bad})
        self.assertTrue(any("fieldsSource" in e and "형식" in e for e in errs), errs)

    def test_output_fields_source_only_on_dict(self):
        """Sheets values처럼 object+dynamic으로 적고 fieldsSource를 달면 agent validate_field가 거부한다 — CI에서 먼저 막는다."""
        bad = _event(fields={"form_id": {"title": "폼"}},
                     outputFields=[{"key": "answers", "title": "답", "type": "object", "dynamic": True,
                                    "fieldsSource": "google.form_questions", "fieldsInputs": ["form_id"]}])
        errs = self.ok(events={"gmail.send_email": bad})
        self.assertTrue(any("type 'dict'" in e for e in errs), errs)

    def test_output_fields_inputs_must_be_input_key(self):
        out = {"key": "answers", "title": "답", "type": "dict", "dynamic": True, "fieldsSource": "google.form_questions"}
        bad = _event(fields={"form_id": {"title": "폼"}},
                     outputFields=[{"key": "responseId", "title": "응답 ID", "type": "string"},
                                   dict(out, fieldsInputs=["responseId"])])
        errs = self.ok(events={"gmail.send_email": bad})
        self.assertTrue(any("'answers'" in e and "입력 칸" in e for e in errs), errs)
        good_action = _event(fields={"form_id": {"title": "폼"}}, outputFields=[dict(out, fieldsInputs=["form_id"])])
        self.assertEqual(self.ok(events={"gmail.send_email": good_action}), [])
        good_trigger = _trigger(inputFields=[{"key": "form_id", "title": "폼", "type": "string"}],
                                outputFields=[dict(out, fieldsInputs=["form_id"])])
        self.assertEqual(self.ok(events={"gmail.new_email": good_trigger}), [])

    def test_output_fields_inputs_must_not_use_q(self):
        bad = _event(fields={"q": {"title": "검색"}},
                     outputFields=[{"key": "answers", "title": "답", "type": "dict",
                                    "fieldsSource": "google.form_questions", "fieldsInputs": ["q"]}])
        errs = self.ok(events={"gmail.send_email": bad})
        self.assertTrue(any("fieldsInputs에 'q'" in e for e in errs), errs)

    def test_output_dynamic_rules_apply_in_children(self):
        """S1·S2 items[].answers — 목록 안쪽 출력 칸도 같은 규칙."""
        def items(answers):
            return [{"key": "items", "title": "응답", "type": "object", "list": True, "children": [answers]}]
        bad = _event(fields={"form_id": {"title": "폼"}},
                     outputFields=items({"key": "answers", "title": "답", "type": "dict",
                                         "fieldsSource": "google.form_questions", "fieldsInputs": ["nope"]}))
        errs = self.ok(events={"gmail.send_email": bad})
        self.assertTrue(any("'answers'" in e and "입력 칸" in e for e in errs), errs)
        good = _event(fields={"form_id": {"title": "폼"}},
                      outputFields=items({"key": "answers", "title": "답", "type": "dict", "dynamic": True,
                                          "fieldsSource": "google.form_questions", "fieldsInputs": ["form_id"]}))
        self.assertEqual(self.ok(events={"gmail.send_email": good}), [])

    def test_preset_rules(self):
        m = {"type": "AI"}
        self.assertEqual(self.ok(presets=[{"id": "ai.web_search", "app": "gmail", "match": m}]), [])
        self.assertTrue(self.ok(presets=[{"id": "gmail.send_email", "match": m}]))           # 이벤트와 이름 충돌
        self.assertTrue(self.ok(presets=[{"id": "p", "match": m}, {"id": "p", "match": {"type": "AI", "x": 1}}]))  # 중복
        self.assertTrue(self.ok(presets=[{"id": "p", "match": m, "builder": True}]))         # 로더가 정하는 키
        self.assertTrue(self.ok(presets=[{"id": "p", "match": m, "app": "nope"}]))           # 없는 앱
        self.assertTrue(self.ok(presets=[{"id": "p"}]))                                      # match 없음

    def test_generation_only_keys_are_rejected(self):
        for key in ("tags", "menu", "golden_snippet", "generation"):
            errs = self.ok(events={"gmail.send_email": _event(**{key: []})})
            self.assertTrue(any(key in e for e in errs), (key, errs))
            errs = self.ok(presets=[{"id": "p", "match": {"type": "AI"}, key: []}])
            self.assertTrue(any(key in e for e in errs), (key, errs))

    def test_field_llm_is_rejected(self):
        field = {"key": "to", "title": "받는 사람", "type": "string", "llm": {"hint": "x"}}
        errs = self.ok(events={"gmail.send_email": _event(inputFields=[field])})
        self.assertTrue(any("llm" in e for e in errs), errs)
        errs = self.ok(events={"gmail.send_email": _event(fields={"to": {"llm": {"hint": "x"}}})})
        self.assertTrue(any("llm" in e for e in errs), errs)

    def test_app_shape(self):
        self.assertTrue(self.ok(apps={"gmail": {**APP, "brand": ""}}))
        self.assertTrue(self.ok(apps={"gmail": {k: v for k, v in APP.items() if k != "auth"}}))
        self.assertEqual(self.ok(apps={"gmail": {**APP, "serviceType": None, "auth": None}}), [])


class RepoCatalogTest(unittest.TestCase):
    def test_repo_catalog_passes(self):
        self.assertEqual(validate.check(*validate.load(validate.ROOT)), [])

    def test_formatter_events_are_transform_actions(self):
        _, events, _ = validate.load(validate.ROOT)
        fmt = {n: e for n, e in events.items() if n.startswith("formatter.")}
        self.assertEqual(len(fmt), 22, sorted(fmt))
        for name, ev in fmt.items():
            self.assertEqual(ev["node_type"], "TRANSFORM", name)
            self.assertEqual(ev["kind"], "action", name)
            self.assertIsNone(ev["tool_key"], name)
            inp = [f for f in ev.get("inputFields", []) if f["key"] == "input"]
            self.assertEqual(len(inp), 1, name)
            self.assertIs(inp[0].get("required"), True, name)

    def test_github_search_events_follow_contract(self):
        _, events, _ = validate.load(validate.ROOT)
        search = {n: e for n, e in events.items() if n.startswith("github.") and e.get("kind") == "search"
                  and n not in ("github.list_issues", "github.get_pr_files")}
        self.assertEqual(set(search), GITHUB_SEARCH_EVENTS)
        for name, ev in search.items():
            outs = {f["key"]: f for f in ev.get("outputFields", [])}
            for key in ("found", "total", "items", "message"):
                self.assertIn(key, outs, name)
            self.assertIs(outs["items"].get("list"), True, name)

    def test_google_sheets_search_events_follow_contract(self):
        _, events, _ = validate.load(validate.ROOT)
        new = SHEETS_SEARCH_EVENTS - {"google_sheets.lookup_row", "google_sheets.read"}
        search = {n for n, e in events.items() if n.startswith("google_sheets.") and e.get("kind") == "search"}
        self.assertEqual(search, SHEETS_SEARCH_EVENTS)
        for name in new:
            ev = events[name]
            self.assertEqual((ev["node_type"], ev["fixed"], ev["builder"]),
                             ("ACTION", {"type": "ACTION", "config": {}}, True), name)
            self.assertEqual(ev["tool_key"], "builtin:" + name.replace(".", "_"), name)
            self.assertTrue(ev.get("title", "").strip() and ev.get("description", "").strip(), name)

            def walk(fs):
                for f in fs:
                    self.assertTrue(f.get("title") and f.get("type"), (name, f.get("key")))
                    walk(f.get("children") or [])
            walk(ev["outputFields"])
            outs = {f["key"]: f for f in ev["outputFields"]}
            for key in ("found", "total", "items"):
                self.assertIn(key, outs, name)
            self.assertIs(outs["items"].get("list"), True, name)
            for key, f in ev.get("fields", {}).items():
                self.assertTrue(f.get("title") and f["title"] != key, (name, key))
        lookup_row = events["google_sheets.lookup_row"]["fields"]
        for key in ("lookup_column", "lookup_value", "lookup_column_2", "lookup_value_2", "from_bottom"):
            self.assertEqual(events["google_sheets.lookup_rows"]["fields"][key], lookup_row[key], key)
        # 출력 2MB 예산·Drive 한 페이지 초과 → truncated, find_spreadsheet 항목엔 소유 여부.
        outs = {n: [f["key"] for f in events[n]["outputFields"]] for n in new}
        for name in ("google_sheets.lookup_rows", "google_sheets.get_rows", "google_sheets.find_spreadsheet"):
            self.assertEqual(outs[name], ["found", "total", "items", "truncated"], name)
            truncated = events[name]["outputFields"][-1]
            self.assertEqual((truncated["type"], truncated["title"]), ("boolean", "잘림"), name)
        items = {f["key"]: f for f in events["google_sheets.find_spreadsheet"]["outputFields"]}["items"]
        self.assertEqual([c["key"] for c in items["children"]], ["id", "name", "url", "modified_time", "owned_by_me"])
        self.assertEqual((items["children"][-1]["type"], items["children"][-1]["title"]), ("boolean", "내 파일"))

    def test_google_sheets_row_events_follow_contract(self):
        _, events, _ = validate.load(validate.ROOT)
        base = events["google_sheets.update_row"]["fields"]
        for name, keys in SHEETS_ROW_EVENTS.items():
            ev = events[name]
            self.assertEqual((ev["node_type"], ev["kind"], ev["fixed"], ev["builder"]),
                             ("ACTION", "action", {"type": "ACTION", "config": {}}, True), name)
            self.assertEqual(ev["tool_key"], "builtin:" + name.replace(".", "_"), name)
            self.assertTrue(ev.get("title", "").strip() and ev.get("description", "").strip(), name)
            self.assertEqual(list(ev["fields"]), keys, name)
            for key in ("spreadsheet_id", "sheet_id", "overwrite_all", "value_input_option"):
                if key in ev["fields"]:
                    self.assertEqual(ev["fields"][key], base[key], (name, key))
            for key, f in ev["fields"].items():
                self.assertTrue(f.get("title") and f["title"] != key, (name, key))
            for f in ev["outputFields"]:
                self.assertTrue(f.get("title") and f.get("type"), (name, f.get("key")))
            outs = [f["key"] for f in ev["outputFields"]]
            if name == "google_sheets.append_rows":
                self.assertEqual(outs, ["updatedRange", "row_number", "row_count"])
            else:
                self.assertEqual(outs, ["row_count", "row_numbers"], name)
                self.assertEqual((ev["outputFields"][1]["type"], ev["outputFields"][1].get("list")),
                                 ("integer", True))
        for name in ("google_sheets.append_rows", "google_sheets.update_rows"):
            f = events[name]["fields"]
            self.assertEqual(f["rows"]["type"], "json")
            cm = f["column_map"]
            self.assertEqual((cm["type"], cm["ref"], cm["fieldsSource"], cm["fieldsInputs"]),
                             ("dict", False, "google.sheet_columns", ["spreadsheet_id", "sheet_id"]))
        # type·required는 agent 시그니처에서 파생(boolean·required). default가 생기면 삭제 확인이 무력해진다.
        self.assertEqual(events["google_sheets.delete_rows"]["fields"]["confirm_delete"],
                         {"title": "삭제 확인", "ref": False,
                          "description": "켜야 실행돼요. 지운 행은 되돌릴 수 없어요(버전 기록으로만 복구)"})
        fmt = events["google_sheets.format_rows"]["fields"]
        for key in ("bold", "italic", "strikethrough"):
            self.assertIs(fmt[key]["ref"], False, key)
            self.assertNotIn("choices", fmt[key])
            self.assertNotIn("default", fmt[key])
        for key in ("row_numbers", "background_color", "text_color"):
            self.assertNotIn("ref", fmt[key], key)
            self.assertNotIn("choices", fmt[key], key)

    def test_google_sheets_range_events_follow_contract(self):
        _, events, _ = validate.load(validate.ROOT)
        common = {k: events["google_sheets.update_row"]["fields"][k] for k in ("spreadsheet_id", "sheet_id")}
        column = {k: v for k, v in events["google_sheets.lookup_row"]["fields"]["lookup_column"].items()
                  if k in ("optionsSource", "optionsInputs", "ref")}
        for name, keys in SHEETS_RANGE_FIELDS.items():
            ev = events[name]
            self.assertEqual((ev["node_type"], ev["kind"], ev["fixed"], ev["builder"]),
                             ("ACTION", "action", {"type": "ACTION", "config": {}}, True), name)
            self.assertEqual(ev["tool_key"], "builtin:" + name.replace(".", "_"), name)
            self.assertTrue(ev.get("title", "").strip() and ev.get("description", "").strip(), name)
            fields = ev["fields"]
            self.assertEqual(list(fields), keys, name)
            self.assertEqual({k: fields[k] for k in common}, common, name)
            for key, f in fields.items():
                self.assertTrue(f.get("title") and f["title"] != key, (name, key))
                if "choices" in f or key in _NO_REF:
                    self.assertIs(f.get("ref"), False, (name, key))
            for key in ("before_column", "sort_column"):
                if key in fields:
                    self.assertEqual({k: fields[key][k] for k in column}, column, (name, key))
            outs = [f["key"] for f in ev["outputFields"]]
            self.assertEqual(outs, SHEETS_RANGE_OUTPUTS.get(name, ["range"]), name)
            for f in ev["outputFields"]:
                self.assertTrue(f.get("title") and f.get("type") == "string", (name, f["key"]))
        cf = [c["id"] for c in events["google_sheets.add_conditional_format"]["fields"]["condition"]["choices"]]
        dv = [c["id"] for c in events["google_sheets.set_data_validation"]["fields"]["condition"]["choices"]]
        self.assertEqual((len(cf), len(dv)), (19, 25))
        fmt = events["google_sheets.format_range"]["fields"]
        for key in ("background_color", "text_color", "bold", "italic", "strikethrough"):
            self.assertEqual(events["google_sheets.add_conditional_format"]["fields"][key], fmt[key], key)

    def test_google_sheets_sheet_events_follow_contract(self):
        _, events, _ = validate.load(validate.ROOT)
        common = events["google_sheets.update_row"]["fields"]
        for name, (fields, outs) in SHEETS_SHEET_EVENTS.items():
            ev = events[name]
            self.assertEqual((ev["node_type"], ev["kind"], ev["fixed"], ev["builder"]),
                             ("ACTION", "action", {"type": "ACTION", "config": {}}, True), name)
            self.assertEqual(ev["tool_key"], "builtin:" + name.replace(".", "_"), name)
            self.assertTrue(ev.get("title", "").strip() and ev.get("description", "").strip(), name)
            self.assertEqual(list(ev["fields"]), fields, name)
            self.assertEqual([f["key"] for f in ev["outputFields"]], outs, name)
            for f in ev["outputFields"]:
                self.assertTrue(f.get("title") and f.get("type"), (name, f["key"]))
            for key, f in ev["fields"].items():
                self.assertTrue(f.get("title") and f["title"] != key, (name, key))
                if key in ("spreadsheet_id", "sheet_id"):
                    self.assertEqual(f, common[key], (name, key))
                if key in ("destination_spreadsheet_id", "copy_from", "visibility", "confirm_delete"):
                    self.assertIs(f.get("ref"), False, (name, key))
                if key == "folder_id":
                    self.assertEqual((f["title"], f["optionsSource"], "ref" in f), ("폴더", "google.folders", False), name)
        upd = events["google_sheets.update_worksheet"]["fields"]["visibility"]
        self.assertEqual([c["id"] for c in upd["choices"]], ["hide", "show"])
        updated = next(f for f in events["google_sheets.update_worksheet"]["outputFields"] if f["key"] == "updated")
        self.assertEqual((updated["type"], updated.get("list")), ("string", True))

    def test_get_pr_reviews_outputs(self):
        _, events, _ = validate.load(validate.ROOT)
        outs = {f["key"]: f for f in events["github.get_pr_reviews"]["outputFields"]}
        self.assertEqual(set(outs), {"found", "total", "items", "message", "comments", "approved_count", "truncated",
                                     "changes_requested_count"})
        self.assertIs(outs["comments"].get("list"), True)

    def test_check_org_membership_outputs(self):
        _, events, _ = validate.load(validate.ROOT)
        outs = {f["key"]: f for f in events["github.check_org_membership"]["outputFields"]}
        self.assertEqual(set(outs), {"member", "found", "total", "items", "message"})
        self.assertEqual(outs["member"]["type"], "boolean")

    def test_delay_events_are_delay_actions(self):
        _, events, _ = validate.load(validate.ROOT)
        base = {"waitedUntil", "scheduledFor"}
        expected = {"delay.for": base, "delay.until": base, "delay.queue": base | {"queuePosition"}}
        self.assertEqual(sorted(n for n in events if n.startswith("delay.")), sorted(expected))
        for name, outs in expected.items():
            ev = events[name]
            self.assertEqual(ev["node_type"], "DELAY", name)
            self.assertEqual(ev["kind"], "action", name)
            self.assertIsNone(ev["tool_key"], name)
            self.assertEqual({f["key"] for f in ev.get("outputFields", [])}, outs, name)

    def test_approval_events_are_approval_actions(self):
        _, events, _ = validate.load(validate.ROOT)
        expected = {
            "approval.request": {"approved", "decision", "approvedBy", "approvedAt", "reviewer", "note", "content",
                                 "rejectedBy", "reason"},
            "approval.collect": {"decision", "approvedBy", "approvedAt", "reviewer", "note", "values"},
        }
        self.assertEqual(sorted(n for n in events if n.startswith("approval.")), sorted(expected))
        for name, outs in expected.items():
            ev = events[name]
            self.assertEqual(ev["node_type"], "APPROVAL", name)
            self.assertEqual(ev["kind"], "action", name)
            self.assertIsNone(ev["tool_key"], name)
            self.assertEqual({f["key"] for f in ev.get("outputFields", [])}, outs, name)
            self.assertNotIn("mode", ev["fixed"]["config"], name)
            self.assertNotIn("mode", {f["key"] for f in ev.get("inputFields", [])}, name)
        common = {"message", "webhookCredentialId", "timeoutAmount", "timeoutUnit", "onTimeout", "reminder"}
        inputs = {
            "approval.request": (common | {"items", "editable", "approveLabel", "rejectLabel", "onReject"},
                                 "items", {"key", "value"}, "content"),
            "approval.collect": (common | {"fields"},
                                 "fields", {"key", "label", "type", "required", "default", "options"}, "values"),
        }
        for name, (keys, list_key, child_keys, dyn_key) in inputs.items():
            fields = {f["key"]: f for f in events[name]["inputFields"]}
            self.assertEqual(set(fields), keys, name)
            self.assertEqual({c["key"] for c in fields[list_key]["children"]}, child_keys, name)
            outs = {f["key"]: f for f in events[name]["outputFields"]}
            self.assertIs(outs[dyn_key].get("dynamic"), True, name)

    def test_google_forms_events(self):
        apps, events, _ = validate.load(validate.ROOT)
        self.assertEqual(apps["google_forms"]["auth"], "google_oauth")
        c1, s3 = events["google_forms.set_accepting_responses"], events["google_forms.get_form"]
        self.assertEqual((c1["kind"], c1["tool_key"]), ("action", "builtin:google_forms_set_accepting_responses"))
        self.assertEqual((s3["kind"], s3["tool_key"]), ("search", "builtin:google_forms_get_form"))
        for ev in (c1, s3):
            self.assertEqual(ev["fields"]["form_id"]["optionsSource"], "google.forms")
        self.assertIs(c1["fields"]["accepting"]["ref"], False)
        self.assertEqual([f["key"] for f in c1["outputFields"]], ["isPublished", "isAcceptingResponses"])
        outs = {f["key"]: f for f in s3["outputFields"]}
        self.assertEqual(list(outs), ["found", "total", "items", "message"])
        self.assertIs(outs["items"]["list"], True)
        items = {c["key"]: c for c in outs["items"]["children"]}
        self.assertEqual(list(items), ["formId", "title", "description", "responderUrl", "isPublished",
                                       "isAcceptingResponses", "linkedSheetId", "questions"])
        self.assertIs(items["questions"]["list"], True)
        self.assertEqual([c["key"] for c in items["questions"]["children"]], ["questionId", "title", "kind", "required"])

    def test_gmail_send_family_events(self):
        _, events, _ = validate.load(validate.ROOT)
        send = events["gmail.send_email"]["fields"]
        find = events["gmail.find_email"]
        no_subject = [k for k in GMAIL_SEND_KEYS if k != "subject"]
        expected = {
            "gmail.reply": (["thread_id"] + no_subject, ["messageId", "threadId"]),
            "gmail.forward": (["message_id"] + no_subject, ["messageId", "threadId"]),
            "gmail.create_draft": (GMAIL_SEND_KEYS[:-1], ["draftId", "messageId", "threadId"]),
            "gmail.create_reply_draft": (["thread_id"] + no_subject[:-1], ["draftId", "messageId", "threadId"]),
            "gmail.find_or_send": (["query", "search_label_ids", "include_spam_trash"] + GMAIL_SEND_KEYS,
                                   ["created"] + GMAIL_MAIL_KEYS),
        }
        for name, (keys, outs) in expected.items():
            ev = events[name]
            self.assertEqual((ev["node_type"], ev["kind"], ev["fixed"], ev["builder"]),
                             ("ACTION", "action", {"type": "ACTION", "config": {}}, True), name)
            self.assertEqual(ev["tool_key"], "builtin:google_" + name.replace(".", "_"), name)
            self.assertTrue(ev["title"].strip() and ev["description"].strip(), name)
            self.assertEqual(list(ev["fields"]), keys, name)
            self.assertEqual([f["key"] for f in ev["outputFields"]], outs, name)
            for k in ("cc", "bcc", "from_email", "from_name", "reply_to", "include_signature", "label_ids"):
                if k in ev["fields"]:
                    self.assertEqual(ev["fields"][k], send[k], (name, k))
            for k in ("body_format", "subject"):
                if k in ev["fields"] and name != "gmail.forward":
                    self.assertEqual(ev["fields"][k], send[k], (name, k))
        self.assertEqual(events["gmail.reply"]["fields"]["thread_id"]["optionsSource"], "google.gmail_threads")
        self.assertEqual(events["gmail.create_reply_draft"]["fields"]["thread_id"],
                         events["gmail.reply"]["fields"]["thread_id"])
        self.assertEqual(events["gmail.forward"]["fields"]["message_id"]["optionsSource"], "google.gmail_messages")
        fos = events["gmail.find_or_send"]
        self.assertEqual(fos["fields"]["search_label_ids"], find["fields"]["label_ids"])
        for k in ("query", "include_spam_trash"):
            self.assertEqual(fos["fields"][k], find["fields"][k], k)
        for k in ("to", "body"):
            self.assertEqual(fos["fields"][k], send[k], k)
        mail = {f["key"]: f for f in fos["outputFields"]}
        items = {c["key"]: c for c in {f["key"]: f for f in find["outputFields"]}["items"]["children"]}
        for k in GMAIL_MAIL_KEYS:
            self.assertEqual(mail[k], items[k], k)
        self.assertEqual(mail["created"]["type"], "boolean")
        for name in ("gmail.create_draft", "gmail.create_reply_draft"):
            self.assertEqual(events[name]["outputFields"][0], {"key": "draftId", "title": "초안 ID", "type": "string"})

    def test_google_forms_response_events(self):
        _, events, _ = validate.load(validate.ROOT)
        answers = {"key": "answers", "title": "답", "type": "dict", "dynamic": True,
                   "fieldsSource": "google.form_questions", "fieldsInputs": ["form_id"]}

        def check_response(fields, where):
            by = {f["key"]: f for f in fields}
            self.assertEqual({k: v for k, v in by["answers"].items() if k != "description"}, answers, where)
            self.assertEqual([c["key"] for c in by["answerList"]["children"]], ["questionId", "question", "answer"], where)
            self.assertEqual((by["answerList"]["list"], by["answerList"]["children"][2]["type"]), (True, "json"), where)
            self.assertEqual((by["submittedAt"]["type"], by["createdAt"]["type"], by["totalScore"]["type"]),
                             ("datetime", "datetime", "number"), where)

        triggers = {"google_forms.new_response": ("FORMS_NEW_RESPONSE", FORMS_RESPONSE_KEYS),
                    "google_forms.new_or_updated_response": ("FORMS_ANY_RESPONSE", FORMS_RESPONSE_KEYS + ["isUpdate"])}
        for name, (ttype, outs) in triggers.items():
            ev = events[name]
            self.assertEqual((ev["node_type"], ev["kind"], ev["trigger_type"], ev["tool_key"], ev["fixed"]),
                             ("TRIGGER", "trigger", ttype, None, {"type": "TRIGGER", "config": {}}), name)
            self.assertLessEqual(len(ttype), 20, name)  # BE workflows.trigger_type VARCHAR(20)
            self.assertEqual(ev["inputFields"], [{"key": "form_id", "title": "폼", "type": "string", "required": True,
                                                  "ref": False, "description": "지켜볼 폼(편집 화면 주소의 폼 ID도 돼요)",
                                                  "optionsSource": "google.forms"}], name)
            self.assertEqual([f["key"] for f in ev["outputFields"]], outs, name)
            check_response(ev["outputFields"], name)
        self.assertEqual(events["google_forms.new_or_updated_response"]["outputFields"][-1]["type"], "boolean")

        form_id = events["google_forms.get_form"]["fields"]["form_id"]
        search = {"google_forms.list_responses": (["form_id", "period", "since", "max_results"],
                                                  ["found", "total", "items", "truncated"]),
                  "google_forms.get_response": (["form_id", "response_id"], ["found", "total", "items"])}
        for name, (keys, outs) in search.items():
            ev = events[name]
            self.assertEqual((ev["node_type"], ev["kind"], ev["fixed"], ev["builder"]),
                             ("ACTION", "search", {"type": "ACTION", "config": {}}, True), name)
            self.assertEqual(ev["tool_key"], "builtin:" + name.replace(".", "_"), name)
            self.assertEqual(list(ev["fields"]), keys, name)
            self.assertEqual(ev["fields"]["form_id"], form_id, name)
            by = {f["key"]: f for f in ev["outputFields"]}
            self.assertEqual(list(by), outs, name)
            self.assertIs(by["items"]["list"], True, name)
            self.assertEqual([c["key"] for c in by["items"]["children"]], FORMS_RESPONSE_KEYS, name)
            check_response(by["items"]["children"], name)
        s1 = events["google_forms.list_responses"]
        self.assertEqual([c["id"] for c in s1["fields"]["period"]["choices"]],
                         ["today", "last_7_days", "last_30_days", "all", "custom"])
        self.assertIs(s1["fields"]["period"]["ref"], False)
        self.assertEqual((s1["outputFields"][-1]["type"], s1["outputFields"][-1]["title"]), ("boolean", "잘림"))
        rid = events["google_forms.get_response"]["fields"]["response_id"]
        self.assertEqual((rid["optionsSource"], rid["optionsInputs"]), ("google.form_responses", ["form_id"]))
        self.assertNotIn("ref", rid)  # 참조식 허용(spec 4절 S2)


class BaseCompareTest(unittest.TestCase):
    def snap(self, events, presets=()):
        return {"gmail": APP}, {name: _event() for name in events}, [{"id": p} for p in presets]

    def test_removed_event_is_warned(self):
        warns = validate.check_against_base(self.snap(["gmail.send_email", "gmail.keep"]), self.snap(["gmail.keep"]))
        self.assertEqual(len(warns), 1, warns)
        self.assertIn("gmail.send_email", warns[0])

    def test_renamed_event_is_warned(self):
        warns = validate.check_against_base(self.snap(["gmail.send_email"]), self.snap(["gmail.send"]))
        self.assertTrue(any("gmail.send_email" in w for w in warns), warns)

    def test_added_event_and_removed_preset_are_not_warned(self):
        base = self.snap(["gmail.send_email"], presets=["ai.gmail_send"])
        self.assertEqual(validate.check_against_base(base, self.snap(["gmail.send_email", "gmail.new"])), [])

    def test_base_warning_does_not_fail(self):
        with mock.patch.object(validate, "load", return_value=self.snap(["gmail.keep"])), \
                mock.patch.object(validate, "_snapshot", return_value=self.snap(["gmail.gone", "gmail.keep"])), \
                mock.patch("builtins.print") as out:
            self.assertEqual(validate.main(["--base", "origin/main"]), 0)
        self.assertTrue(any("gmail.gone" in str(c) for c in out.call_args_list), out.call_args_list)

    def test_check_error_still_fails_with_base(self):
        head = ({"gmail": APP}, {"gmail.keep": _event(match={"type": "ACTION"})}, [])
        with mock.patch.object(validate, "load", return_value=head), \
                mock.patch.object(validate, "_snapshot", return_value=self.snap(["gmail.keep"])), \
                mock.patch("builtins.print"):
            self.assertEqual(validate.main(["--base", "origin/main"]), 1)


if __name__ == "__main__":
    unittest.main()
