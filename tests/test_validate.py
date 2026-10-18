import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import validate  # noqa: E402

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

    def test_golden_snippet_event_is_own_name(self):
        snip = {"id": "node-2", "event": "gmail.send_email", "type": "ACTION", "config": {"to": "a@b.c"}}
        self.assertEqual(self.ok(events={"gmail.send_email": _event(golden_snippet=snip)}), [])
        for bad in ({k: v for k, v in snip.items() if k != "event"}, {**snip, "event": "gmail.other"}):
            errs = self.ok(events={"gmail.send_email": _event(golden_snippet=bad)})
            self.assertTrue(any("golden_snippet.event" in e for e in errs), (bad, errs))

    def test_preset_golden_snippet_event_is_ai_agent(self):
        snip = {"id": "node-2", "event": "ai.agent", "type": "AI", "config": {"tools": [{"name": "gmail"}]}}
        self.assertEqual(self.ok(presets=[{"id": "ai.gmail_send", "app": "gmail", "golden_snippet": snip}]), [])
        bad = {**snip, "event": "ai.gmail_send"}
        errs = self.ok(presets=[{"id": "ai.gmail_send", "app": "gmail", "golden_snippet": bad}])
        self.assertTrue(any("golden_snippet.event" in e for e in errs), errs)

    def test_golden_snippet_must_not_carry_old_fields(self):
        trig = {"id": "node-1", "event": "gmail.new_email", "type": "TRIGGER",
                "config": {"triggerType": "GMAIL_NEW_EMAIL"}}
        errs = self.ok(events={"gmail.new_email": _trigger(golden_snippet=trig)})
        self.assertTrue(any("triggerType" in e for e in errs), errs)
        act = {"id": "node-2", "event": "gmail.send_email", "type": "ACTION",
               "config": {"tools": [{"name": "gmail", "config": {"to": "a@b.c"}}]}}
        errs = self.ok(events={"gmail.send_email": _event(golden_snippet=act)})
        self.assertTrue(any("config.tools" in e for e in errs), errs)

    def test_golden_snippet_config_must_be_object(self):
        snip = {"id": "node-2", "event": "gmail.send_email", "type": "ACTION"}
        self.assertEqual(self.ok(events={"gmail.send_email": _event(golden_snippet=snip)}), [])  # config 없음은 허용
        for cfg in (None, "x", []):
            errs = self.ok(events={"gmail.send_email": _event(golden_snippet={**snip, "config": cfg})})
            self.assertTrue(any("golden_snippet.config" in e for e in errs), (cfg, errs))

    def test_golden_snippet_type_is_node_type(self):
        snip = {"id": "node-2", "event": "gmail.send_email", "type": "ACTION", "config": {}}
        for bad in ({**snip, "type": "AI"}, {k: v for k, v in snip.items() if k != "type"}):
            errs = self.ok(events={"gmail.send_email": _event(golden_snippet=bad)})
            self.assertTrue(any("golden_snippet.type" in e for e in errs), (bad, errs))
        psnip = {"id": "node-2", "event": "ai.agent", "type": "ACTION", "config": {}}
        errs = self.ok(presets=[{"id": "ai.gmail_send", "golden_snippet": psnip}])
        self.assertTrue(any("golden_snippet.type" in e for e in errs), errs)

    def test_action_fixed_must_be_exact(self):
        for fixed in ({"type": "ACTION", "config": {"credentialId": ""}}, {"type": "ACTION", "config": {}, "tool": "x"},
                      {"type": "ACTION"}):
            errs = self.ok(events={"gmail.send_email": _event(fixed=fixed)})
            self.assertTrue(any("ACTION fixed" in e for e in errs), (fixed, errs))

    def test_golden_snippet_service_type_forbidden(self):
        snip = {"id": "node-2", "event": "gmail.send_email", "type": "ACTION", "config": {"serviceType": "GOOGLE"}}
        errs = self.ok(events={"gmail.send_email": _event(golden_snippet=snip)})
        self.assertTrue(any("serviceType" in e for e in errs), errs)

    def test_preset_golden_snippet_old_fields_forbidden(self):
        snip = {"id": "node-2", "event": "ai.agent", "type": "AI", "config": {"triggerType": "MANUAL"}}
        errs = self.ok(presets=[{"id": "ai.gmail_send", "golden_snippet": snip}])
        self.assertTrue(any("triggerType" in e for e in errs), errs)

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

    def test_preset_rules(self):
        self.assertEqual(self.ok(presets=[{"id": "ai.gmail_send", "app": "gmail"}]), [])
        self.assertTrue(self.ok(presets=[{"id": "gmail.send_email"}]))           # 이벤트와 이름 충돌
        self.assertTrue(self.ok(presets=[{"id": "p"}, {"id": "p"}]))             # 중복
        self.assertTrue(self.ok(presets=[{"id": "p", "builder": True}]))         # 로더가 정하는 키
        self.assertEqual(self.ok(presets=[{"id": "p", "match": {"type": "AI"}}]), [])  # AI 칸 규칙용 match는 허용
        self.assertTrue(self.ok(presets=[{"id": "p", "app": "nope"}]))           # 없는 앱

    def test_app_shape(self):
        self.assertTrue(self.ok(apps={"gmail": {**APP, "brand": ""}}))
        self.assertTrue(self.ok(apps={"gmail": {k: v for k, v in APP.items() if k != "auth"}}))
        self.assertEqual(self.ok(apps={"gmail": {**APP, "serviceType": None, "auth": None}}), [])


class RepoCatalogTest(unittest.TestCase):
    def test_repo_catalog_passes(self):
        self.assertEqual(validate.check(*validate.load(validate.ROOT)), [])


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
