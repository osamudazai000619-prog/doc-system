from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from services.export_service import EXPORT_META, generate_exported_file, preview_exported_file
from models.schemas import ExportRequest, ExportResponse, PreviewResponse

router = APIRouter(prefix="/api", tags=["export"])

@router.post("/export", response_model=ExportResponse)
async def export_document(req: ExportRequest):
    # 需要将模型转换回字典再传给 service
    confirmed_data_dicts = [item.model_dump() for item in req.confirmed_data]
    return await generate_exported_file(confirmed_data_dicts, req.template_name)

@router.get("/preview/{file_id}", response_model=PreviewResponse)
async def preview_file(file_id: str):
    """预览已生成的导出文件内容。"""
    return await run_in_threadpool(preview_exported_file, file_id)


@router.get("/download/{file_id}")
async def download_file(file_id: str):
    """下载导出生成的文件。"""
    meta = EXPORT_META.get(file_id)
    if not meta or not Path(meta["path"]).exists():
        raise HTTPException(404, "文件不存在或已过期")
    return FileResponse(
        meta["path"],
        filename=meta["filename"],
        media_type="application/octet-stream",
    )
