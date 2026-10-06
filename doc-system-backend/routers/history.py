from typing import List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.history_service import (
    delete_tasks,
    get_task_detail,
    list_tasks,
    rename_task,
)

router = APIRouter(prefix="/api", tags=["history"])


@router.get("/history")
async def history_list(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    """历史任务列表（时间倒序，分页），每条附最近一次导出产物信息。"""
    return list_tasks(page=page, size=size)


class HistoryRenameRequest(BaseModel):
    title: str


class HistoryBatchDeleteRequest(BaseModel):
    ids: List[int]


@router.put("/history/{task_id}")
async def history_rename(task_id: int, req: HistoryRenameRequest):
    """历史任务重命名（仅显示名）。"""
    if not rename_task(task_id, req.title):
        raise HTTPException(404, "任务记录不存在或标题为空")
    return {"ok": True}


@router.post("/history/batch-delete")
async def history_batch_delete(req: HistoryBatchDeleteRequest):
    """批量删除历史任务（连同其导出产物登记）。"""
    return {"deleted": delete_tasks(req.ids)}


@router.get("/history/{task_id}")
async def history_detail(task_id: int):
    """任务详情：配置快照 + 提取结果快照 + 全部导出产物。"""
    detail = get_task_detail(task_id)
    if detail is None:
        raise HTTPException(404, "任务记录不存在")
    return detail
