"""地基①：最小数据模型。

只定义"形状"，不含任何业务逻辑（逻辑后面放在 log / reducer）。
三样东西：
  Event        —— 事件日志里的一条事件，写进就不许改。
  Intent       —— 一个意图：id + 目标 + 层级 + 状态。
  WorkingState —— 当前状态：一袋意图 + 每层一个活跃指针。
                  它由事件日志算出来，不单独存盘（状态/历史分离）。
对应《设计说明》第 1 节。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class IntentStatus(str, Enum):
    """意图的三种状态。"""
    ACTIVE = "active"          # 当前算数
    SUPERSEDED = "superseded"  # 被一条新意图取代（推翻）
    ARCHIVED = "archived"      # 同层旧意图让位，归档留底


class IntentKind(str, Enum):
    """意图的三层。每层最多一个活跃意图——这是 F1（状态陈旧）的命门。"""
    OBJECTIVE = "objective"    # 总目标
    GOAL = "goal"              # 阶段目标
    SUBTASK = "subtask"        # 子任务


@dataclass(frozen=True)
class Event:
    """事件日志里的一条事件。

    frozen=True ⇒ 写进就不许改。这是事件日志可信的前提：
    历史一旦能被涂改，"重算/审计/崩溃重放"就全都靠不住了。
    """
    seq: int                                   # 第几号，线性递增
    actor: str                                 # 谁干的
    type: str                                  # 做了什么（事件类型名）
    payload: Dict[str, Any] = field(default_factory=dict)  # 改了哪块


@dataclass
class Intent:
    """一个意图。最小版只有 id / 目标 / 层级 / 状态，外加两个关系指针。"""
    id: str
    goal: str
    kind: IntentKind = IntentKind.OBJECTIVE
    status: IntentStatus = IntentStatus.ACTIVE
    parent_id: Optional[str] = None            # 挂在哪个父意图下
    superseded_by: Optional[str] = None        # 被谁取代（指向新意图 id）


@dataclass
class WorkingState:
    """当前状态 = 一袋意图 + 每层一个活跃指针。

    关键：这份东西不往磁盘单独存，每次都由事件日志（事件序列）算出来。
    磁盘上只有事件日志。这就是"状态/历史分离"，是 F1 的根。
    """
    intents: Dict[str, Intent] = field(default_factory=dict)
    active_by_level: Dict[str, str] = field(default_factory=dict)  # 层 -> 活跃意图 id
    last_seq: int = 0                          # 已经应用到第几号事件

    @classmethod
    def empty(cls) -> "WorkingState":
        return cls()

    def active_intent(self) -> Optional[Intent]:
        """取最深的活跃意图：子任务 > 阶段目标 > 总目标。"""
        for kind in (IntentKind.SUBTASK, IntentKind.GOAL, IntentKind.OBJECTIVE):
            iid = self.active_by_level.get(kind.value)
            if iid and iid in self.intents:
                return self.intents[iid]
        return None