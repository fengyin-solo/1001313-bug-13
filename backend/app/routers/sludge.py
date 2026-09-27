"""污泥脱水接口：维护脱水机组运行台账，覆盖登记、进料、冲洗、加药停机等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.sludge import STATUS_ORDER, SludgeService

router = APIRouter(prefix="/api/sludge", tags=["污泥脱水"])

service = SludgeService()

LIST_FIELDS = [
    "机组编号", "所属厂站", "机组类型", "进泥量", "出泥含水率",
    "絮凝剂用量", "运行功率", "机组状态", "开始时间", "结束时间",
]
STATUSES = STATUS_ORDER


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按机组编号检索"),
    status: str | None = Query(default=None, description="运行中、待进料、冲洗中、已停机"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按机组编号与状态过滤污泥脱水列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/stats", response_model=dict)
def stats() -> dict[str, int]:
    """台账统计：运行中机组数、在办记录数、已停机历史记录数。"""
    return service.stats()


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出污泥脱水清单：返回当前全部数据（含已停机历史记录）。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "sludge", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条脱水机组明细；不存在时给出可读的错误说明。已停机记录同样可查。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"脱水机组记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条在办运行记录；同一机组已有在办记录或缺少必填字段时说明原因。"""
    ok, entry, message = service.create_entry(payload.values)
    return ActionResult(ok=ok, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条在办记录执行启动进料、开始冲洗、加药登记。

    加药登记完成后机组转为已停机；已停机记录只读，任何动作都会被拦下。
    """
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
