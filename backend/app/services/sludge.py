"""污泥脱水业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "sludge"
REQUIRED_FIELDS = ["机组编号", "所属厂站", "机组类型"]
BUSINESS_FIELDS = ["机组编号", "所属厂站", "机组类型", "进泥量", "出泥含水率", "絮凝剂用量", "运行功率"]
NUMERIC_FIELDS = ["进泥量", "絮凝剂用量", "运行功率"]
STATUS_ORDER = ["待进料", "运行中", "冲洗中", "已停机"]
TERMINAL_STATUS = STATUS_ORDER[-1]

# 状态机：每个动作限定来源状态与目标状态；已停机不在任何来源里，归档记录天然只读。
ACTION_FLOW: dict[str, dict[str, Any]] = {
    "启动进料": {"from": ["待进料"], "target": "运行中"},
    "开始冲洗": {"from": ["运行中"], "target": "冲洗中"},
    "加药": {"from": ["运行中", "冲洗中"], "target": "已停机"},
    "停机": {"from": ["待进料", "运行中", "冲洗中"], "target": "已停机"},
}


def _parse_number(raw: Any) -> float | None:
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _is_blank(raw: Any) -> bool:
    return raw is None or str(raw).strip() == ""


class SludgeService:
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
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self.serialize(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return self.serialize(entry)

    def serialize(self, entry: dict[str, Any]) -> dict[str, Any]:
        """输出副本：带上真实状态、只读标记与可执行动作，列表页和详情页用同一份判断。"""
        data = dict(entry)
        data["机组状态"] = entry.get("status")
        data["readonly"] = entry.get("status") == TERMINAL_STATUS
        data["available_actions"] = self.available_actions(entry)
        return data

    def available_actions(self, entry: dict[str, Any]) -> list[str]:
        status = str(entry.get("status", ""))
        return [name for name, rule in ACTION_FLOW.items() if status in rule["from"]]

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in REQUIRED_FIELDS if _is_blank(values.get(field))]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        code = str(values["机组编号"]).strip()
        for row in store.rows(MODULE):
            if str(row.get("机组编号", "")).strip() == code and row.get("status") != TERMINAL_STATUS:
                return None, (
                    f"机组 {code} 已有一条在办记录（台账 #{row.get('id')}，状态：{row.get('status')}），"
                    "同期只保留一条，请先办结后再登记"
                )
        invalid = self._validate_measurements(values)
        if invalid:
            return None, invalid
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        # 按字段名逐个落账，机组编号与运行功率不会错位；留空的选填项不写入。
        for field in BUSINESS_FIELDS:
            raw = values.get(field)
            if _is_blank(raw):
                continue
            entry[field] = self._normalize(field, raw)
        entry["机组编号"] = code
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, "脱水机组已登记"

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"脱水机组 {entry_id} 不存在"
        if action not in ACTION_FLOW:
            return None, f"动作「{action}」不属于污泥脱水可执行范围"
        status = str(entry.get("status", ""))
        if status == TERMINAL_STATUS:
            return None, f"机组 {entry.get('机组编号')} 已停机归档，记录仅供查询，不能再改动"
        rule = ACTION_FLOW[action]
        if status not in rule["from"]:
            return None, f"当前状态「{status}」不允许执行「{action}」"
        if action == "加药":
            invalid = self._apply_dosing(entry, values)
            if invalid:
                return None, invalid
        entry["status"] = rule["target"]
        entry["pending"] = rule["target"] != TERMINAL_STATUS
        entry["abnormal"] = False
        if action == "加药":
            return entry, "加药完成，机组已停机，絮凝剂用量已留存"
        return entry, f"脱水机组已{action}"

    def _apply_dosing(self, entry: dict[str, Any], values: dict[str, Any]) -> str | None:
        """加药登记：絮凝剂用量必填且大于 0，出泥含水率选填；先校验后落账。"""
        dose = _parse_number(values.get("絮凝剂用量"))
        if dose is None or dose <= 0:
            return "加药登记需要填写大于 0 的絮凝剂用量"
        moisture: float | None = None
        if not _is_blank(values.get("出泥含水率")):
            moisture = _parse_number(values.get("出泥含水率"))
            if moisture is None or not 0 < moisture < 100:
                return "出泥含水率需为 0–100 之间的数字"
        entry["絮凝剂用量"] = dose
        if moisture is not None:
            entry["出泥含水率"] = moisture
        return None

    def _validate_measurements(self, values: dict[str, Any]) -> str | None:
        for field in NUMERIC_FIELDS:
            raw = values.get(field)
            if _is_blank(raw):
                continue
            number = _parse_number(raw)
            if number is None or number <= 0:
                return f"{field}需为大于 0 的数字"
        if not _is_blank(values.get("出泥含水率")):
            moisture = _parse_number(values.get("出泥含水率"))
            if moisture is None or not 0 < moisture < 100:
                return "出泥含水率需为 0–100 之间的数字"
        return None

    def _normalize(self, field: str, raw: Any) -> Any:
        if field in NUMERIC_FIELDS or field == "出泥含水率":
            number = _parse_number(raw)
            if number is not None:
                return number
        return str(raw).strip()
