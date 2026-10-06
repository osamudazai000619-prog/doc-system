from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.scheme_service import (
    delete_scheme,
    find_recommendation,
    get_scheme,
    list_schemes,
    save_scheme,
)

router = APIRouter(prefix="/api", tags=["schemes"])


class SchemeSaveRequest(BaseModel):
    name: str
    prompt: str = ""
    fields: List[str] = []
    template_asset_id: Optional[int] = None
    scheme_id: Optional[int] = None  # 传入则更新，否则新建


@router.get("/schemes")
async def schemes_list():
    """方案列表（按最后使用时间倒序）。"""
    return {"items": list_schemes()}


@router.get("/schemes/{scheme_id}")
async def schemes_detail(scheme_id: int):
    detail = get_scheme(scheme_id)
    if detail is None:
        raise HTTPException(404, "方案不存在")
    return detail


@router.post("/schemes")
async def schemes_save(req: SchemeSaveRequest):
    try:
        return save_scheme(
            name=req.name,
            prompt=req.prompt,
            fields=req.fields,
            template_asset_id=req.template_asset_id,
            scheme_id=req.scheme_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/recommend")
async def recommend(template_asset_id: Optional[int] = Query(None)):
    """
    推荐：同一模板文件最近使用过的配置。
    返回 null 表示无历史记录。
    """
    return find_recommendation(template_asset_id)


@router.delete("/schemes/{scheme_id}")
async def schemes_delete(scheme_id: int):
    if not delete_scheme(scheme_id):
        raise HTTPException(404, "方案不存在")
    return {"ok": True}
