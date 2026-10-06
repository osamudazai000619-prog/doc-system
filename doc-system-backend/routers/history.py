from fastapi import APIRouter, HTTPException, Query

from services.history_service import get_task_detail, list_tasks

router = APIRouter(prefix="/api", tags=["history"])


@router.get("/history")
async def history_list(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    """历史任务列表（时间倒序，分页），每条附最近一次导出产物信息。"""
    return list_tasks(page=page, size=size)


@router.get("/history/{task_id}")
async def history_detail(task_id: int):
    """任务详情：配置快照 + 提取结果快照 + 全部导出产物。"""
    detail = get_task_detail(task_id)
    if detail is None:
        raise HTTPException(404, "任务记录不存在")
    return detail
