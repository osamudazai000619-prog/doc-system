from fastapi import APIRouter
from typing import List

from services.extract_service import extract_info_via_ai
from models.schemas import ExtractRequest, ExtractResponseItem

router = APIRouter(prefix="/api", tags=["extract"])

@router.post("/extract", response_model=List[ExtractResponseItem])
async def extract_info(req: ExtractRequest):
    return await extract_info_via_ai(req.prompt, req.fields, req.documents)