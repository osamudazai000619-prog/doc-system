from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
import logging
import re
from pathlib import Path

from services.extract_service import extract_info_via_ai
from services.history_service import record_extraction
from services.scheme_service import touch_scheme
from services.upload_service import UPLOAD_META, parse_file
from models.schemas import ExtractRequest, ExtractResponseItem

router = APIRouter(prefix="/api", tags=["extract"])

logger = logging.getLogger(__name__)


@router.post("/extract", response_model=List[ExtractResponseItem])
async def extract_info(req: ExtractRequest):
    results = await extract_info_via_ai(req.prompt, req.fields, req.documents)

    # 提取完成即落一条任务历史（配置与结果存快照）；失败只记日志，不影响响应
    template_meta: Optional[Dict[str, Any]] = None
    for meta in UPLOAD_META.values():
        if meta.get("role") == "template":
            template_meta = meta  # 遍历取最后出现的模板记录
    task_id = record_extraction(
        prompt=req.prompt,
        fields=req.fields,
        results=[item.model_dump() for item in results],
        source_filenames=[str(d.get("filename", "")) for d in req.documents],
        template_asset_id=(template_meta or {}).get("asset_id"),
        template_name=(template_meta or {}).get("original_name", ""),
    )
    if task_id is not None:
        for item in results:
            item.task_id = str(task_id)

    # 回写方案使用时间（用于推荐接口的"最近使用"排序）；失败只记日志
    if req.scheme_id and str(req.scheme_id).isdigit():
        touch_scheme(int(req.scheme_id))
    return results


# ========== 智能提取模板表头接口 ==========
@router.get("/extract/template-headers")
async def get_template_headers():
    """
    获取最新上传的模板文件的表头信息。
    支持带标题/说明文字的复杂 Excel，自动定位真实表头行。
    如果未找到模板或解析失败，返回空列表。
    """
    # 1. 找到最新的模板文件（遍历取最后出现的 role=template 记录）
    latest_template_meta: Optional[Dict[str, Any]] = None
    for meta in UPLOAD_META.values():
        if meta.get("role") == "template":
            latest_template_meta = meta

    if not latest_template_meta:
        logger.warning("未找到 role=template 的上传记录")
        return {"headers": []}

    logger.info("选中的模板记录: %s", latest_template_meta)

    # 2. 解析模板文件内容
    try:
        path = Path(latest_template_meta["path"])
        if not path.exists():
            logger.warning("模板文件不存在: %s", path)
            return {"headers": []}

        # 统一处理扩展名：兼容 "xlsx" / ".xlsx" / "XLSX" 等写法
        file_ext = str(latest_template_meta.get("ext", "")).lower().strip()
        if not file_ext.startswith('.'):
            file_ext = '.' + file_ext

        headers: List[str] = []

        if file_ext in ('.xlsx', '.xlsm'):
            headers = _extract_xlsx_headers(path)
        elif file_ext == '.docx':
            headers = _extract_docx_headers(path)
        else:
            # 非 Excel / Word（CSV / 文本等）走通用文本解析
            status, content, error = parse_file(path, file_ext)
            if status != "success":
                logger.warning("模板解析失败: %s", error)
                return {"headers": []}

            lines = content.strip().split('\n')
            if not lines:
                logger.info("内容为空，无法提取表头")
                return {"headers": []}

            headers = re.split(r'[,\t|;]+', lines[0].strip())
            headers = [h.strip() for h in headers if h.strip()]

        if not headers:
            logger.info("已读取文件，但未解析出任何有效表头")
            return {"headers": []}

        logger.info("成功提取到模板表头: %s", headers)
        return {"headers": headers}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取模板表头时发生未知错误: %s", e)
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


def _extract_xlsx_headers(path: Path) -> List[str]:
    """
    Excel 表头提取：自动定位真实表头行（非空单元格最多且达到阈值的一行），
    并用左侧值填充合并单元格造成的空值。
    说明：刻意使用项目已有依赖 openpyxl，避免为单个接口引入 pandas。
    """
    # 延迟导入：可选格式依赖禁止模块顶层 import
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=False, data_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        # 先把合并单元格的值回填到每个被合并位置：
        # 否则表头行因合并出现空洞，"非空最多"启发式会错选下方的满列数据行
        grid = [list(row) for row in ws.iter_rows(values_only=True)]
        for rng in ws.merged_cells.ranges:
            top_left = grid[rng.min_row - 1][rng.min_col - 1]
            for r in range(rng.min_row - 1, rng.max_row):
                for c in range(rng.min_col - 1, rng.max_col):
                    grid[r][c] = top_left
        rows = [tuple(row) for row in grid]
    finally:
        wb.close()

    if not rows:
        return []

    logger.info("Excel 读取成功，共 %d 行", len(rows))

    # 智能定位真实表头行：非空单元格数量最多且达到阈值的一行
    min_threshold = 3
    best_idx = -1
    max_cols_count = 0
    for i, row in enumerate(rows):
        non_empty = sum(1 for cell in row if cell is not None and str(cell).strip())
        if non_empty > max_cols_count and non_empty >= min_threshold:
            max_cols_count = non_empty
            best_idx = i

    if best_idx == -1:
        logger.info("未找到满足阈值(%d列)的表头行", min_threshold)
        return []

    logger.info("定位到表头行索引: %d，非空列数: %d", best_idx, max_cols_count)

    # 用左侧值填充合并单元格造成的空值（ffill），并清理换行/首尾空格
    headers: List[str] = []
    last_val = ""
    for cell in rows[best_idx]:
        if cell is not None and str(cell).strip():
            last_val = str(cell).replace('\n', '').replace('\r', '').strip()
        if last_val:
            headers.append(last_val)
    return headers


def _extract_docx_headers(path: Path) -> List[str]:
    """Word 表头提取：遍历所有表格，取列数最多的主表首行作为表头。"""
    # 延迟导入：可选格式依赖禁止模块顶层 import
    from docx import Document

    doc = Document(str(path))
    if not doc.tables:
        logger.info("Word 文档中未发现任何表格")
        return []

    best_table = None
    max_cols = 0
    for table in doc.tables:
        if not table.rows:
            continue
        cols = len(table.rows[0].cells)
        if cols > max_cols:
            max_cols = cols
            best_table = table

    if not best_table:
        logger.info("Word 文档中没有有效的表格结构")
        return []

    headers: List[str] = []
    for cell in best_table.rows[0].cells:
        text = cell.text.replace('\n', '').replace('\r', '').strip()
        if text:
            headers.append(text)

    if not headers:
        logger.info("Word 表格第一行未解析到任何文字")
        return []

    logger.info("从 Word 表格成功提取表头: %s", headers)
    return headers
