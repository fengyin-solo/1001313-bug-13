"""污泥脱水业务规则：状态流转、字段校验、在办唯一性与历史记录保护。

规则要点：
- 同一台机组同一时期只允许存在一条在办（未停机）记录，重复登记直接拦下；
- 所有字段一律按中文名读写，禁止按列位置映射，避免机组编号与运行功率错位；
- 进泥量、絮凝剂用量等计量字段整条记录一次性登记，不做拆分均摊；
- 「加药登记」是在办记录的收尾动作：登记絮凝剂用量（可同时补出泥含水率）后
  机组状态变为「已停机」，絮凝剂用量随记录保留；
- 已停机的历史记录可查不可改，任何动作都拒绝；出泥含水率一旦写入不得覆盖。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "sludge"

# 所有字段一律以中文名为准，列表、详情、写库都用同一份，杜绝按位置错位。
DISPLAY_FIELDS = [
    "机组编号", "所属厂站", "机组类型", "进泥量", "出泥含水率",
    "絮凝剂用量", "运行功率", "机组状态", "开始时间", "结束时间",
]
REQUIRED_FIELDS = ["机组编号", "所属厂站", "机组类型", "运行功率"]
TEXT_FIELDS = ["机组编号", "所属厂站", "机组类型"]
NUMERIC_FIELDS = ["进泥量", "出泥含水率", "絮凝剂用量", "运行功率"]

STATUS_PENDING_FEED = "待进料"
STATUS_RUNNING = "运行中"
STATUS_FLUSHING = "冲洗中"
STATUS_STOPPED = "已停机"
ACTIVE_STATUSES = [STATUS_PENDING_FEED, STATUS_RUNNING, STATUS_FLUSHING]
STATUS_ORDER = ACTIVE_STATUSES + [STATUS_STOPPED]

ACTION_FEED = "启动进料"
ACTION_FLUSH = "开始冲洗"
ACTION_DOSE = "加药登记"
ACTION_RULES = {
    ACTION_FEED: STATUS_RUNNING,
    ACTION_FLUSH: STATUS_FLUSHING,
    ACTION_DOSE: STATUS_STOPPED,
}


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _as_number(value: Any) -> tuple[float | None, bool]:
    """把前端提交值转成数值；返回 (数值, 是否非法)。空值视为未填，不算非法。"""
    if value is None or str(value).strip() == "":
        return None, False
    try:
        return float(str(value).strip()), False
    except (TypeError, ValueError):
        return None, True


def _normalize(value: float) -> float | int:
    return int(value) if value.is_integer() else round(value, 2)


class SludgeService:
    # ---------------------------------------------------------------- 读取
    def _present(self, row: dict[str, Any]) -> dict[str, Any]:
        """统一序列化：详情与列表走同一份口径，保证两处判断一致。"""
        item: dict[str, Any] = {"id": row.get("id")}
        for field in DISPLAY_FIELDS:
            item[field] = row.get(field)
        # 机组状态以内部状态机字段为准，不信任任何按位置写入的旧值。
        item["机组状态"] = row.get("status")
        item["status"] = row.get("status")
        item["pending"] = row.get("status") != STATUS_STOPPED
        item["abnormal"] = bool(row.get("abnormal"))
        item["readonly"] = row.get("status") == STATUS_STOPPED
        return item

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("机组编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        # 在办记录在前（开始时间新→旧），已停机历史记录排末尾，方便台账核对。
        # 先按开始时间倒序，再借稳定排序把在办记录整体提到停机记录之前。
        rows = sorted(rows, key=lambda row: str(row.get("开始时间", "")), reverse=True)
        rows = sorted(rows, key=lambda row: row.get("status") == STATUS_STOPPED)
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._present(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return self._present(row) if row is not None else None

    def stats(self) -> dict[str, int]:
        rows = store.rows(MODULE)
        return {
            "运行中机组": sum(1 for row in rows if row.get("status") == STATUS_RUNNING),
            "在办记录": sum(1 for row in rows if row.get("status") in ACTIVE_STATUSES),
            "已停机记录": sum(1 for row in rows if row.get("status") == STATUS_STOPPED),
        }

    def _find_active_by_code(self, unit_code: str) -> dict[str, Any] | None:
        for row in store.rows(MODULE):
            if row.get("status") != STATUS_STOPPED and str(row.get("机组编号", "")).strip() == unit_code:
                return row
        return None

    # ---------------------------------------------------------------- 登记
    def create_entry(
        self, values: dict[str, Any]
    ) -> tuple[bool, dict[str, Any] | None, str]:
        """登记一条在办运行记录。

        返回 (是否成功, 记录或冲突的在办记录, 说明)。
        """
        missing = [
            field for field in REQUIRED_FIELDS
            if not str(values.get(field) or "").strip()
        ]
        if missing:
            return False, None, f"缺少必填字段：{'、'.join(missing)}"

        unit_code = str(values.get("机组编号")).strip()
        existing = self._find_active_by_code(unit_code)
        if existing is not None:
            # 同一台机组同期只留一条在办，重复提交（含连点两次）一律拦在这里。
            return (
                False,
                self._present(existing),
                f"机组 {unit_code} 已存在一条在办运行记录（{existing.get('status')}），"
                "请在该记录上继续操作，不能重复登记",
            )

        entry: dict[str, Any] = {
            "id": max((int(row.get("id", 0)) for row in store.rows(MODULE)), default=0) + 1,
            "status": STATUS_PENDING_FEED,
            "pending": True,
            "abnormal": False,
        }
        for field in TEXT_FIELDS:
            entry[field] = str(values.get(field)).strip()
        for field in NUMERIC_FIELDS:
            number, invalid = _as_number(values.get(field))
            if invalid:
                return False, None, f"字段「{field}」必须填数值，收到：{values.get(field)!r}"
            if number is not None:
                if number < 0:
                    return False, None, f"字段「{field}」不能为负数"
                entry[field] = _normalize(number)
            else:
                entry[field] = None
        entry["开始时间"] = _now_text()
        entry["结束时间"] = None
        store.rows(MODULE).append(entry)
        return True, self._present(entry), "脱水机组运行记录已登记"

    # ---------------------------------------------------------------- 动作
    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        values = values or {}
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"脱水机组记录 {entry_id} 不存在或已归档"

        current = str(entry.get("status"))
        # 历史记录只读：已结束的运行记录能查到，但任何动作都拒绝。
        # 这条判断放在动作合法性之前，保证无论提交什么动作，结论一致。
        if current == STATUS_STOPPED:
            return None, "该运行记录已停机归档，仅供查询，不能再操作"

        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于污泥脱水可执行范围"

        target = ACTION_RULES[action]

        if action == ACTION_FEED:
            if current == STATUS_RUNNING:
                return self._present(entry), "机组已在运行进料中，无需重复启动"
            if current == STATUS_FLUSHING:
                return None, "机组正在冲洗，需先完成加药停机后才能重新进料"
            # 先校验、后改状态，避免校验失败时留下半截状态。
            feed_amount, invalid = _as_number(values.get("进泥量"))
            if invalid:
                return None, f"字段「进泥量」必须填数值，收到：{values.get('进泥量')!r}"
            if feed_amount is not None and feed_amount < 0:
                return None, "进泥量不能为负数"
            entry["status"] = target
            if feed_amount is not None:
                # 本次运行的进泥量整额记入同一条台账，不拆分、不均摊。
                entry["进泥量"] = _normalize(feed_amount)
            entry["pending"] = True
            return self._present(entry), "已启动进料"

        if action == ACTION_FLUSH:
            if current != STATUS_RUNNING:
                return None, f"当前状态为「{current}」，只有运行中的机组才能开始冲洗"
            entry["status"] = target
            entry["pending"] = True
            return self._present(entry), "机组开始冲洗"

        # 加药登记：收尾在办记录，状态转已停机，并保留絮凝剂用量。
        dose_amount, invalid = _as_number(values.get("絮凝剂用量"))
        if invalid:
            return None, f"字段「絮凝剂用量」必须填数值，收到：{values.get('絮凝剂用量')!r}"
        if dose_amount is None:
            return None, "加药登记必须填写絮凝剂用量"
        if dose_amount < 0:
            return None, "絮凝剂用量不能为负数"

        moisture, invalid = _as_number(values.get("出泥含水率"))
        if invalid:
            return None, f"字段「出泥含水率」必须填数值，收到：{values.get('出泥含水率')!r}"
        if moisture is not None and not 0 <= moisture <= 100:
            return None, "出泥含水率应在 0~100 之间"
        if moisture is not None and entry.get("出泥含水率") is not None:
            # 历史含水率受保护：已填过就不允许用新提交覆盖。
            return None, (
                f"出泥含水率已记录为 {entry.get('出泥含水率')}%，"
                "历史含水率不能被覆盖"
            )

        entry["絮凝剂用量"] = _normalize(dose_amount)
        if moisture is not None:
            entry["出泥含水率"] = _normalize(moisture)
        entry["status"] = STATUS_STOPPED
        entry["pending"] = False
        entry["abnormal"] = False
        entry["结束时间"] = _now_text()
        return self._present(entry), "加药登记完成，机组已停机"
