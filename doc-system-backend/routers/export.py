import urllib.parse
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from services.export_service import EXPORT_META, generate_exported_file, preview_exported_file
from services.trace_report_service import generate_trace_report_pdf
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


@router.post("/export/trace-report")
async def export_trace_report(data: List[Dict[str, Any]]):
    """导出当前提取结果的溯源报告 PDF。
    入参为提取结果列表（结构与 /extract 返回一致：records 的值可为
    {value,source,context,confidence,risk} 字典或纯字符串）。
    生成在独立线程池，避免阻塞事件循环。"""
    if not data:
        raise HTTPException(400, "提取结果为空，无法生成溯源报告")
    pdf_bytes = await run_in_threadpool(generate_trace_report_pdf, data)
    filename = f"溯源报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    # RFC5987 兼容中文文件名
    quoted = urllib.parse.quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quoted}",
    }
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers=headers,
    )
