from pydantic import BaseModel, Field, model_validator
from typing import List, Dict, Any

# ================= 1. Upload 接口 =================
class UploadResponseItem(BaseModel):
    filename: str
    status: str
    content: str

# ================= 2. Extract 接口 =================
class RecordItem(BaseModel):
    field_name: str = Field(description="提取的字段名称")
    field_value: str = Field(description="提取的字段值，如果没有则必须为'未找到'")

class ExtractedTable(BaseModel):
    table_category: str
    records: Dict[str, str] 

class ExtractResponseItem(BaseModel):
    source_file: str
    extracted_tables: List[ExtractedTable]

class ExtractRequest(BaseModel):
    prompt: str
    fields: List[str] = Field(..., max_length=10)
    documents: List[Dict[str, Any]]

    @model_validator(mode='after')
    def check_prompt_or_fields(self):
        # 只要 prompt 去除空格后为空，且 fields 列表为空，就抛出错误
        if not self.prompt.strip() and len(self.fields) == 0:
            raise ValueError('提取字段和提示词必须至少有一项输入')
        return self
        # 其中一不为空的检验
# ================= 3. Export 接口 =================
class ExportRequest(BaseModel):
    confirmed_data: List[ExtractResponseItem]
    template_name: str

class ExportResponse(BaseModel):
    download_url: str
    message: str