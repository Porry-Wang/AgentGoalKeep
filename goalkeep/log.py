"""地基②：事件日志（线性、只追加）。

把第 1 节的 Event 真正存起来：只追加、统一发号、单写者、乐观锁。
一个 SQLite 文件就是一个事件日志 —— 天生持久化（崩溃还在）+ 单写者事务。
对应《设计说明》第 2 节。
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List

from .types import Event


class StaleSeqError(Exception):
    """乐观锁失败：调用方以为的号(expected)和事件日志实际号(actual)对不上。

    这意味着别人抢先写了。拒绝这条，让调用方拿最新事件日志重试——
    而不是悄悄盖掉先写者（那就是 F4 丢失更新）。
    """
    def __init__(self, expected: int, actual: int):
        self.expected = expected
        self.actual = actual
        super().__init__(
            "事件日志已到第 %d 号，而你以为是第 %d 号；请取最新状态重试" % (actual, expected))


class EventLog:
    """一个只追加的事件日志。只提供"追加"和"读"，没有"改/删"。"""

    def __init__(self, path: str):
        self.path = path
        # isolation_level=None ⇒ autocommit，事务由我们手动 BEGIN/COMMIT 控制，
        # 这样才能用 BEGIN IMMEDIATE 抢单写者锁。
        self._conn = sqlite3.connect(path, isolation_level=None)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS events ("
            "seq INTEGER PRIMARY KEY, actor TEXT NOT NULL, "
            "type TEXT NOT NULL, payload TEXT NOT NULL)"
        )

    def head_seq(self) -> int:
        """当前最大号；空日志为 0。"""
        row = self._conn.execute("SELECT MAX(seq) FROM events").fetchone()
        return int(row[0]) if row[0] is not None else 0

    def append(self, actor: str, type: str, payload: Dict[str, Any],
               expected_seq: int) -> Event:
        """追加一条事件：核对乐观锁 → 发号 → 落盘。

        expected_seq：调用方"以为事件日志现在到第几号"。对不上就拒绝（StaleSeqError）。
        号由事件日志统一发（当前最大 +1），调用方不能自己报号。
        """
        self._conn.execute("BEGIN IMMEDIATE")  # 单写者锁：同一时刻只我一个能写
        try:
            cur = self.head_seq()
            if cur != expected_seq:
                raise StaleSeqError(expected_seq, cur)
            new_seq = cur + 1
            self._conn.execute(
                "INSERT INTO events (seq, actor, type, payload) VALUES (?, ?, ?, ?)",
                (new_seq, actor, type, json.dumps(payload, ensure_ascii=False)),
            )
            self._conn.execute("COMMIT")
        except BaseException:
            if self._conn.in_transaction:
                self._conn.execute("ROLLBACK")
            raise
        return Event(seq=new_seq, actor=actor, type=type, payload=dict(payload))

    def chain(self) -> List[Event]:
        """按 seq 顺序读回全部事件（下一小步算当前状态时就喂这个）。"""
        rows = self._conn.execute(
            "SELECT seq, actor, type, payload FROM events ORDER BY seq"
        ).fetchall()
        return [Event(seq=r[0], actor=r[1], type=r[2], payload=json.loads(r[3]))
                for r in rows]

    def close(self) -> None:
        self._conn.close()