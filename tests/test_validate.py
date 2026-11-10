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
