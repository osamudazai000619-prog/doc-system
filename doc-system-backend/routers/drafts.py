from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.draft_service import delete_draft, get_draft, list_drafts, save_draft

router = APIRouter(prefix="/api", tags=["drafts"])


class DraftSaveRequest(BaseModel):
    title: str = ""
    step: str = "/upload"
    template_name: str = ""
    file_count: int = 0
    field_count: int = 0
    payload: Dict[str, Any] = {}
    draft_id: Optional[int] = None  # 传入则覆盖更新同一条


@router.get("/drafts")
async def drafts_list():
    """草稿列表（摘要，按更新时间倒序）。"""
    return {"items": list_drafts()}


@router.post("/drafts")
async def drafts_save(req: DraftSaveRequest):
    """保存草稿；超过上限时自动淘汰最久未更新的一条。"""
    return save_draft(
        title=req.title,
        step=req.step,
        template_name=req.template_name,
        file_count=req.file_count,
        field_count=req.field_count,
        payload=req.payload,
        draft_id=req.draft_id,
    )


@router.get("/drafts/{draft_id}")
async def drafts_detail(draft_id: int):
    """草稿详情（含完整 payload，恢复时调用）。"""
    detail = get_draft(draft_id)
    if detail is None:
        raise HTTPException(404, "草稿不存在")
    return detail


@router.delete("/drafts/{draft_id}")
async def drafts_delete(draft_id: int):
    if not delete_draft(draft_id):
        raise HTTPException(404, "草稿不存在")
    return {"ok": True}
