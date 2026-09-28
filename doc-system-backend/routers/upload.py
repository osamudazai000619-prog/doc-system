from fastapi import APIRouter, UploadFile, File
from typing import List, Optional

# 1. 新增：从刚才创建的 schemas 文件中导入返回模型
from models.schemas import UploadResponseItem 
from services.upload_service import process_upload_files

router = APIRouter(prefix="/api", tags=["upload"])

# 2. 修改：在原有的路由装饰器里加上 response_model
@router.post("/upload", response_model=List[UploadResponseItem])
async def upload_files(
    target_files: List[UploadFile] = File(...),
    template_files: Optional[List[UploadFile]] = File(default=[])
):
    """
    接收目标处理文件和模板文件
    使用 Optional 和 default=[] 防止前端未传模板文件时报错
    """
    return await process_upload_files(target_files, template_files)