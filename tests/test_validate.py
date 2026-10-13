import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import validate  # noqa: E402

APP = {"provider": "google", "title": "Gmail", "brand": "gmail", "serviceType": "GOOGLE", "auth": "google_oauth"}


def _event(**over):
    ev = {"node_type": "ACTION", "kind": "action", "tool_key": "gmail",
          "fixed": {"type": "ACTION", "config": {"tools": [{"name": "gmail"}]}}}
    ev.update(over)
    return ev


def _trigger(**over):
    ev = {"node_type": "TRIGGER", "kind": "trigger", "trigger_type": "GMAIL_NEW_EMAIL", "tool_key": None,
          "fixed": {"type": "TRIGGER", "config": {}}}
    ev.update(over)
    return ev


class CheckTest(unittest.TestCase):
    def ok(self, apps=None, events=None, presets=None, aliases=None):
        return validate.check(apps if apps is not None else {"gmail": APP},
                              events if events is not None else {"gmail.send_email": _event()},
                              presets or [], aliases or {})

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

    def test_loader_injected_values_must_not_be_written(self):
        for cfg in ({"triggerType": "GMAIL_NEW_EMAIL"}, {"serviceType": "GOOGLE"}):
            errs = self.ok(events={"gmail.new_email": _trigger(fixed={"type": "TRIGGER", "config": cfg})})
            self.assertTrue(errs, cfg)
        errs = self.ok(events={"gmail.new_email": _trigger(fixed={"type": "TRIGGER", "event": "x", "config": {}})})
        self.assertTrue(any("event" in e for e in errs), errs)

    def test_options_source_format(self):
        bad = _event(inputFields=[{"key": "a", "optionsSource": "Google Calendars"}])
        self.assertTrue(self.ok(events={"gmail.send_email": bad}))
        nested = _event(fields={"a": {"children": [{"key": "b", "optionsSource": "nope"}]}})
        self.assertTrue(self.ok(events={"gmail.send_email": nested}))
        good = _event(inputFields=[{"key": "a", "optionsSource": "google.calendars"}])
        self.assertEqual(self.ok(events={"gmail.send_email": good}), [])

    def test_preset_rules(self):
        self.assertEqual(self.ok(presets=[{"id": "ai.gmail_send", "app": "gmail"}]), [])
        self.assertTrue(self.ok(presets=[{"id": "gmail.send_email"}]))           # 이벤트와 이름 충돌
        self.assertTrue(self.ok(presets=[{"id": "p"}, {"id": "p"}]))             # 중복
        self.assertTrue(self.ok(presets=[{"id": "p", "builder": True}]))         # 로더가 정하는 키
        self.assertEqual(self.ok(presets=[{"id": "p", "match": {"type": "AI"}}]), [])  # 매칭용 match는 허용
        self.assertTrue(self.ok(presets=[{"id": "p", "app": "nope"}]))           # 없는 앱

    def test_alias_target_must_be_event(self):
        self.assertEqual(self.ok(aliases={"action.gmail_send": "gmail.send_email"}), [])
        self.assertTrue(self.ok(aliases={"action.gmail_send": "gmail.nope"}))

    def test_alias_chain_reaching_event_passes(self):
        # 이벤트 이름을 다시 바꾸면 옛 별칭은 그대로 두고 새 별칭을 잇는다.
        events = {"gmail.send": _event()}
        self.assertEqual(self.ok(events=events, aliases={"old": "gmail.send_email", "gmail.send_email": "gmail.send"}), [])
        self.assertTrue(self.ok(events=events, aliases={"a": "b", "b": "a"}))   # 순환

    def test_app_shape(self):
        self.assertTrue(self.ok(apps={"gmail": {**APP, "brand": ""}}))
        self.assertTrue(self.ok(apps={"gmail": {k: v for k, v in APP.items() if k != "auth"}}))
        self.assertEqual(self.ok(apps={"gmail": {**APP, "serviceType": None, "auth": None}}), [])


class BaseCompareTest(unittest.TestCase):
    def snap(self, events, presets=(), aliases=None):
        return ({"gmail": APP}, {name: _event() for name in events}, [{"id": p} for p in presets], aliases or {})

    def test_removing_event_without_alias_fails(self):
        errs = validate.check_against_base(self.snap(["gmail.send_email"]), self.snap([]))
        self.assertTrue(any("gmail.send_email" in e for e in errs), errs)

    def test_rename_with_alias_passes(self):
        head = self.snap(["gmail.send"], aliases={"gmail.send_email": "gmail.send"})
        self.assertEqual(validate.check_against_base(self.snap(["gmail.send_email"]), head), [])

    def test_removing_preset_without_alias_fails(self):
        errs = validate.check_against_base(self.snap([], presets=["ai.gmail_send"]), self.snap([]))
        self.assertTrue(errs)

    def test_second_rename_keeps_old_alias(self):
        base = self.snap(["gmail.send_email"], aliases={"old": "gmail.send_email"})
        head = self.snap(["gmail.send"], aliases={"old": "gmail.send_email", "gmail.send_email": "gmail.send"})
        self.assertEqual(validate.check(*head), [])
        self.assertEqual(validate.check_against_base(base, head), [])

    def test_self_alias_can_follow_rename(self):
        apps = {"ai": APP}
        base = (apps, {"ai.reasoning": _event()}, [], {"ai.reasoning": "ai.reasoning"})
        head = (apps, {"ai.think": _event()}, [], {"ai.reasoning": "ai.think"})
        self.assertEqual(validate.check(*head), [])
        self.assertEqual(validate.check_against_base(base, head), [])

    def test_alias_cannot_be_removed_or_changed(self):
        base = self.snap(["gmail.send"], aliases={"old": "gmail.send"})
        self.assertTrue(validate.check_against_base(base, self.snap(["gmail.send"])))
        changed = self.snap(["gmail.send", "gmail.other"], aliases={"old": "gmail.other"})
        self.assertTrue(validate.check_against_base(base, changed))


if __name__ == "__main__":
    unittest.main()
