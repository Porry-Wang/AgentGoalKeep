"""地基①的验收：数据模型的形状对不对。

跑法：python3 -m unittest tests.test_types -v
"""
import unittest
from dataclasses import FrozenInstanceError

from agent_state.types import (
    Event, Intent, IntentKind, IntentStatus, WorkingState,
)


class EventShape(unittest.TestCase):
    def test_event_is_immutable(self):
        """账本流水写进就不许改——这是账本可信的前提。"""
        e = Event(seq=1, actor="user", type="IntentSet", payload={"goal": "A"})
        with self.assertRaises(FrozenInstanceError):
            e.seq = 2  # type: ignore[misc]

    def test_event_payload_defaults_to_empty(self):
        e = Event(seq=1, actor="user", type="IntentSet")
        self.assertEqual(e.payload, {})


class IntentShape(unittest.TestCase):
    def test_default_status_is_active(self):
        i = Intent(id="i-1", goal="做个订单服务")
        self.assertEqual(i.status, IntentStatus.ACTIVE)
        self.assertEqual(i.kind, IntentKind.OBJECTIVE)


class WorkingStateShape(unittest.TestCase):
    def test_empty_has_no_active(self):
        s = WorkingState.empty()
        self.assertEqual(s.intents, {})
        self.assertIsNone(s.active_intent())

    def test_active_intent_picks_deepest_level(self):
        """活跃指针取最深一层：子任务 > 阶段目标 > 总目标。"""
        s = WorkingState.empty()
        s.intents["i-obj"] = Intent(id="i-obj", goal="总目标", kind=IntentKind.OBJECTIVE)
        s.intents["i-goal"] = Intent(id="i-goal", goal="阶段目标", kind=IntentKind.GOAL)
        s.active_by_level["objective"] = "i-obj"
        s.active_by_level["goal"] = "i-goal"
        self.assertEqual(s.active_intent().id, "i-goal")

    def test_active_intent_falls_back_to_objective(self):
        s = WorkingState.empty()
        s.intents["i-obj"] = Intent(id="i-obj", goal="总目标")
        s.active_by_level["objective"] = "i-obj"
        self.assertEqual(s.active_intent().id, "i-obj")


if __name__ == "__main__":
    unittest.main(verbosity=2)