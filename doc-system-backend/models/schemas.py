from pydantic import BaseModel, Field, model_validator
from typing import List, Dict, Any

# ================= 1. Upload 接口 =================
class UploadResponseItem(BaseModel):
    filename: str
    status: str
    content: str
    role: str = ""        # 文件角色：target（目标文档）/ template（模板文件）
    error: str = ""       # 解析失败时的报错信息，成功时为空字符串

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

# ---------- 后端内部模型：阶段一"表计划"，不进对外契约 ----------
class TablePlanItem(BaseModel):
    category: str = Field(description="分类名，必须逐字抄录自模板表上方的描述文字")
    filters: Dict[str, str] = Field(
        default_factory=dict,
        description="该表的行筛选条件，键为列名，值逐字抄录自用户要求；无条件则为空字典",
    )

class TablePlan(BaseModel):
    plans: List[TablePlanItem] = Field(default_factory=list)

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

class PreviewResponse(BaseModel):
    filename: str
    content: str