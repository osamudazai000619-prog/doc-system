from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from db.database import SessionLocal
from db.models import Asset
from services.upload_service import UPLOAD_META, parse_file

import uuid

router = APIRouter(prefix="/api", tags=["assets"])


@router.get("/assets")
async def assets_list(role: str = Query("template")):
    """
    文件资产库列表，默认只查模板。
    只返回磁盘文件仍存在的资产（避免列出已失效引用）。
    """
    with SessionLocal() as session:
        assets = (
            session.query(Asset)
            .filter(Asset.role == role)
            .order_by(Asset.created_at.desc(), Asset.id.desc())
            .all()
        )
        return {
            "items": [
                {
                    "id": a.id,
                    "original_name": a.original_name,
                    "ext": a.ext,
                    "size": a.size,
                    "created_at": a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else "",
                }
                for a in assets
                if Path(a.path).exists()
            ]
        }


@router.post("/assets/{asset_id}/load")
async def assets_load(asset_id: int):
    """
    把资产库中的文件加载到本次会话（UPLOAD_META），返回与上传解析一致的结构。
    用于"从文件库选择模板/目标文档"，免去重复上传与解析。
    """
    with SessionLocal() as session:
        asset = session.get(Asset, asset_id)
        if asset is None:
            raise HTTPException(404, "资产不存在")
        if not Path(asset.path).exists():
            raise HTTPException(410, "资产文件已从磁盘移除")

        file_id = uuid.uuid4().hex
        UPLOAD_META[file_id] = {
            "file_id": file_id,
            "path": asset.path,
            "original_name": asset.original_name,
            "role": asset.role,
            "ext": asset.ext,
            "size": asset.size,
            "asset_id": asset.id,
        }
        # 解析内容（与上传流程一致），供前端直接进提取流程
        status, content, error_msg = await run_in_threadpool(
            parse_file, Path(asset.path), asset.ext
        )
        return {
            "filename": asset.original_name,
            "status": status,
            "content": content if status == "success" else "",
            "role": asset.role,
            "error": error_msg or "",
            "asset_id": asset.id,
        }
