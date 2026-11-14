"""地基②的验收：账本只追加、统一发号、乐观锁、持久化。

跑法：python3 -m unittest tests.test_log -v
"""
import os
import tempfile
import unittest

from goalkeep.log import EventLog, StaleSeqError


class LogCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "ledger.db")
        self.log = EventLog(self.path)

    def tearDown(self):
        self.log.close()
        for f in os.listdir(self.dir):
            os.remove(os.path.join(self.dir, f))
        os.rmdir(self.dir)

    def test_empty_head_is_zero(self):
        self.assertEqual(self.log.head_seq(), 0)
        self.assertEqual(self.log.chain(), [])

    def test_append_allocates_sequential_seq(self):
        e1 = self.log.append("user", "IntentSet", {"goal": "A"}, expected_seq=0)
        e2 = self.log.append("user", "IntentSet", {"goal": "B"}, expected_seq=1)
        e3 = self.log.append("user", "IntentSet", {"goal": "C"}, expected_seq=2)
        self.assertEqual([e1.seq, e2.seq, e3.seq], [1, 2, 3])
        self.assertEqual(self.log.head_seq(), 3)

    def test_optimistic_lock_rejects_stale(self):
        self.log.append("user", "IntentSet", {"goal": "A"}, expected_seq=0)
        # 现在 head=1，却声称以为是 0 ⇒ 拒绝
        with self.assertRaises(StaleSeqError):
            self.log.append("user", "IntentSet", {"goal": "B"}, expected_seq=0)
        # 拒绝不留半笔：head 仍是 1，链里仍只有 1 笔
        self.assertEqual(self.log.head_seq(), 1)
        self.assertEqual(len(self.log.chain()), 1)

    def test_after_rejection_correct_append_works(self):
        self.log.append("user", "IntentSet", {"goal": "A"}, expected_seq=0)
        with self.assertRaises(StaleSeqError):
            self.log.append("user", "IntentSet", {"goal": "B"}, expected_seq=0)
        e = self.log.append("user", "IntentSet", {"goal": "B"}, expected_seq=1)
        self.assertEqual(e.seq, 2)

    def test_chain_order_and_payload(self):
        self.log.append("user", "IntentSet", {"goal": "甲"}, expected_seq=0)
        self.log.append("agent:main", "IntentRefined", {"goal": "乙"}, expected_seq=1)
        chain = self.log.chain()
        self.assertEqual([e.seq for e in chain], [1, 2])
        self.assertEqual(chain[0].payload, {"goal": "甲"})
        self.assertEqual(chain[1].actor, "agent:main")
        self.assertEqual(chain[1].type, "IntentRefined")

    def test_two_writers_only_one_wins(self):
        """F4 的机器演示：两人都以为 head=0，只有一个写得进，另一个被拒。"""
        other = EventLog(self.path)
        try:
            self.assertEqual(self.log.head_seq(), 0)
            self.assertEqual(other.head_seq(), 0)
            self.log.append("user", "IntentSet", {"goal": "A"}, expected_seq=0)
            with self.assertRaises(StaleSeqError):
                other.append("user", "IntentSet", {"goal": "B"}, expected_seq=0)
            self.assertEqual(self.log.head_seq(), 1)
            self.assertEqual(len(self.log.chain()), 1)
        finally:
            other.close()

    def test_persistence_across_reopen(self):
        self.log.append("user", "IntentSet", {"goal": "A"}, expected_seq=0)
        self.log.close()
        reopened = EventLog(self.path)
        try:
            self.assertEqual(reopened.head_seq(), 1)
            self.assertEqual(reopened.chain()[0].payload, {"goal": "A"})
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)