import logging
import re
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from docx import Document
from openpyxl import load_workbook

from services.history_service import find_export_by_file_id, record_export
from services.upload_service import UPLOAD_META, parse_file
from db.database import SessionLocal
from db.models import Asset

logger = logging.getLogger(__name__)

EXPORT_DIR = Path("uploads") / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# 导出结果登记（file_id -> path/filename），供 /api/download/{file_id} 使用
EXPORT_META: Dict[str, Dict[str, str]] = {}

# 这些取值视为"无数据"，不写入模板
SKIP_VALUES = {"未找到", "PARSE_ERROR", "", None}


def _normalize_field(s: str) -> str:
    """字段名归一化：去空白/标点，转小写。"""
    s = (s or "").strip()
    s = re.sub(r"[\s:：,，、；;\-_/\\|。.()（）\[\]【】]+", "", s)
    return s.lower()


def _is_blank(s: Any) -> bool:
    """单元格内容是否为空白（含只有占位下划线的情况）。"""
    if s is None:
        return True
    text = str(s).strip()
    if not text:
        return True
    return set(text) <= set("_-— .\u3000")


# ============ 同义词表 ============
SYNONYM_GROUPS = [
    {"联系电话", "手机号码", "联系方式", "电话号码", "手机号", "电话", "联系人电话"},
    {"项目名称", "课题名称", "项目名", "课题名", "申报项目名称"},
    {"负责人", "项目负责人", "主持人", "申请人", "项目主持人", "负责人姓名"},
    {"金额", "申报金额", "经费", "预算", "项目金额", "资金", "申报经费"},
    {"日期", "申报日期", "提交日期", "填报日期", "申请日期", "签订日期"},
    {"单位", "所属单位", "工作单位", "申报单位", "承担单位", "所在单位"},
    {"地址", "联系地址", "通信地址", "通讯地址", "详细地址", "住址"},
    {"邮箱", "电子邮箱", "email", "邮箱地址", "电子邮件"},
    {"身份证号", "身份证号码", "证件号", "证件号码"},
    {"编号", "项目编号", "课题编号", "申报编号"},
]

_SYN_INDEX: Dict[str, int] = {}


def _build_synonym_index() -> None:
    _SYN_INDEX.clear()
    for gi, group in enumerate(SYNONYM_GROUPS):
        for word in group:
            _SYN_INDEX[_normalize_field(word)] = gi


_build_synonym_index()


def _resolve_field(
    template_field: str,
    available_fields: List[str],
    user_mapping: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """
    将模板中的字段标签解析为数据里的实际字段名。
    优先级：用户显式映射 > 精确匹配 > 同义词组匹配。
    """
    if not template_field:
        return None
    raw = str(template_field).strip().rstrip(":：")
    norm_t = _normalize_field(raw)
    if not norm_t:
        return None

    if user_mapping:
        if template_field in user_mapping:
            return user_mapping[template_field]
        for k, v in user_mapping.items():
            if _normalize_field(k) == norm_t:
                return v

    for f in available_fields:
        if _normalize_field(f) == norm_t:
            return f

    gi = _SYN_INDEX.get(norm_t)
    if gi is not None:
        group_norms = {_normalize_field(w) for w in SYNONYM_GROUPS[gi]}
        for f in available_fields:
            if _normalize_field(f) in group_norms:
                return f
    return None


# ============ 数据展平 ============
def _collect_rows(confirmed_data: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    展平确认数据为行记录，并附上 _source_file / _table_category 元信息。
    契约中 records 为 Dict[str, str]（键=字段名，值=提取值）；
    兼容容错：若上游传成 list[dict] 结构也能处理。
    """
    rows: List[Dict[str, str]] = []
    for file_data in confirmed_data or []:
        source = file_data.get("source_file", "")
        for table in file_data.get("extracted_tables", []):
            category = table.get("table_category", "")
            records = table.get("records", {})
            if isinstance(records, dict):
                records_iter: List[Dict[str, Any]] = [records]
            elif isinstance(records, list):
                records_iter = [r for r in records if isinstance(r, dict)]
            else:
                records_iter = []
            for rec in records_iter:
                row = {k: v for k, v in rec.items() if not str(k).startswith("_")}
                row["_source_file"] = source
                row["_table_category"] = category
                rows.append(row)
    return rows


def _collect_available_fields(rows: List[Dict[str, str]]) -> List[str]:
    fields: List[str] = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k.startswith("_"):
                continue
            if k not in seen:
                seen.add(k)
                fields.append(k)
    return fields


def _merge_rows(rows: List[Dict[str, str]]) -> Dict[str, str]:
    """多行合并为一条记录：跳过无数据值，后面的行不覆盖前面的非空值。"""
    merged: Dict[str, str] = {}
    for r in rows:
        for k, v in r.items():
            if k.startswith("_"):
                continue
            if v in SKIP_VALUES:
                continue
            merged[k] = str(v)
    return merged


def _replace_placeholders_in_str(
    text: str,
    record: Dict[str, str],
    available_fields: List[str],
    user_mapping: Optional[Dict[str, str]] = None,
) -> Tuple[str, set]:
    """替换 {字段名} / {{字段名}} 占位符，返回 (新文本, 已填充字段集合)。"""
    filled: set = set()
    if not text or "{" not in text:
        return text, filled

    def _repl(m: re.Match) -> str:
        raw = m.group(1).strip()
        field = _resolve_field(raw, available_fields, user_mapping)
        if field is None:
            return m.group(0)
        value = record.get(field)
        if value in SKIP_VALUES:
            return ""
        filled.add(field)
        return str(value)

    text = re.sub(r"\{\{\s*([^{}]+?)\s*\}\}", _repl, text)
    text = re.sub(r"\{\s*([^{}]+?)\s*\}", _repl, text)
    return text, filled


def _rows_by_category(rows: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    """按 _table_category 分组。"""
    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for r in rows:
        cat = r.get("_table_category", "").strip()
        if cat:
            grouped[cat].append(r)
    return grouped


# ============ Excel 填充 ============
def _find_excel_header_row(
    ws, available_fields: List[str], user_mapping: Optional[Dict[str, str]]
) -> Tuple[Optional[int], Dict[int, str]]:
    """找到表头行，并建立 列号 -> 字段名 映射。"""
    for row in ws.iter_rows():
        if not row:
            continue
        mapping: Dict[int, str] = {}
        for cell in row:
            if cell.value is None:
                continue
            raw = str(cell.value).strip()
            if not raw:
                continue
            field = _resolve_field(raw, available_fields, user_mapping)
            if field:
                mapping[cell.column] = field
        if len(mapping) >= 2:
            return row[0].row, mapping
    return None, {}


def _fill_excel_kv_mode(
    ws,
    record: Dict[str, str],
    available_fields: List[str],
    filled: set,
    user_mapping: Optional[Dict[str, str]] = None,
) -> None:
    """键值对模式：标签在左/上，值填在右/下单元格。"""
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            cell_str = str(cell.value).strip()

            if "{" in cell_str:
                new_text, f = _replace_placeholders_in_str(
                    cell_str, record, available_fields, user_mapping
                )
                if new_text != cell_str:
                    cell.value = new_text
                    filled.update(f)
                    continue

            field = _resolve_field(cell_str, available_fields, user_mapping)
            if field is None or field in filled:
                continue
            value = record.get(field)
            if value in SKIP_VALUES:
                continue

            right = ws.cell(row=cell.row, column=cell.column + 1)
            if _is_blank(right.value):
                right.value = str(value)
                filled.add(field)
                continue
            down = ws.cell(row=cell.row + 1, column=cell.column)
            if _is_blank(down.value):
                down.value = str(value)
                filled.add(field)


def fill_excel_template(
    template_path: Path,
    rows: List[Dict[str, str]],
    output_path: Path,
    user_mapping: Optional[Dict[str, str]] = None,
) -> set:
    wb = load_workbook(filename=str(template_path))
    filled: set = set()
    available_fields = _collect_available_fields(rows)
    rows_by_cat = _rows_by_category(rows)

    for ws in wb.worksheets:
        matched_rows = rows
        matched_cat = None
        ws_title = ws.title.strip()

        # 1. 优先匹配 Sheet 名称（包含匹配，例如 "德州市数据" 可匹配 "德州市"）
        for cat in list(rows_by_cat.keys()):
            if cat and cat in ws_title:
                matched_cat = cat
                break

        # 2. Sheet 名没匹配到，再检查前 3 行文本（包含匹配）
        if not matched_cat:
            for row in ws.iter_rows(min_row=1, max_row=3, values_only=True):
                for val in row:
                    if val:
                        val_str = str(val).strip()
                        for cat in list(rows_by_cat.keys()):
                            if cat and cat in val_str:
                                matched_cat = cat
                                break
                    if matched_cat:
                        break
                if matched_cat:
                    break

        if matched_cat:
            matched_rows = rows_by_cat[matched_cat]

        merged = _merge_rows(matched_rows)

        header_row, col_map = _find_excel_header_row(ws, available_fields, user_mapping)
        if header_row is not None and col_map:
            data_start = header_row + 1
            for i, row_data in enumerate(matched_rows):
                target_row = data_start + i
                for col_idx, field in col_map.items():
                    value = row_data.get(field)
                    if value in SKIP_VALUES:
                        continue
                    ws.cell(row=target_row, column=col_idx, value=str(value))
                    filled.add(field)
        else:
            _fill_excel_kv_mode(ws, merged, available_fields, filled, user_mapping)

    wb.save(str(output_path))
    return filled


# ============ Word 填充 ============
def _find_word_header_row(
    table, available_fields: List[str], user_mapping: Optional[Dict[str, str]]
) -> Tuple[Optional[int], Dict[int, str]]:
    """找到表头行，并建立 列号 -> 字段名 映射。"""
    for r_idx, row in enumerate(table.rows):
        mapping: Dict[int, str] = {}
        for c_idx, cell in enumerate(row.cells):
            raw = cell.text.strip()
            if not raw:
                continue
            field = _resolve_field(raw, available_fields, user_mapping)
            if field:
                mapping[c_idx] = field
        if len(mapping) >= 2:
            return r_idx, mapping
    return None, {}


def _fill_word_kv_mode(
    table,
    record: Dict[str, str],
    available_fields: List[str],
    filled: set,
    user_mapping: Optional[Dict[str, str]] = None,
) -> None:
    """键值对模式：标签在左/上，值填在右/下单元格。"""
    rows = table.rows
    for r_idx, row in enumerate(rows):
        for c_idx, cell in enumerate(row.cells):
            for para in cell.paragraphs:
                for run in para.runs:
                    if "{" in run.text:
                        new_text, f = _replace_placeholders_in_str(
                            run.text, record, available_fields, user_mapping
                        )
                        if new_text != run.text:
                            run.text = new_text
                            filled.update(f)

            cell_text = cell.text.strip()
            if not cell_text:
                continue
            field = _resolve_field(cell_text, available_fields, user_mapping)
            if field is None or field in filled:
                continue
            value = record.get(field)
            if value in SKIP_VALUES:
                continue
            if c_idx + 1 < len(row.cells):
                right_cell = row.cells[c_idx + 1]
                if _is_blank(right_cell.text):
                    right_cell.text = str(value)
                    filled.add(field)
                    continue
            if r_idx + 1 < len(rows) and c_idx < len(rows[r_idx + 1].cells):
                down_cell = rows[r_idx + 1].cells[c_idx]
                if _is_blank(down_cell.text):
                    down_cell.text = str(value)
                    filled.add(field)


def fill_word_template(
    template_path: Path,
    rows: List[Dict[str, str]],
    output_path: Path,
    user_mapping: Optional[Dict[str, str]] = None,
) -> set:
    doc = Document(str(template_path))
    filled: set = set()
    available_fields = _collect_available_fields(rows)
    rows_by_cat = _rows_by_category(rows)

    # 段落中的占位符统一使用全量数据（不区分表格分类）
    merged_all = _merge_rows(rows)
    for para in doc.paragraphs:
        for run in para.runs:
            if "{" in run.text:
                new_text, f = _replace_placeholders_in_str(
                    run.text, merged_all, available_fields, user_mapping
                )
                if new_text != run.text:
                    run.text = new_text
                    filled.update(f)

    for table in doc.tables:
        matched_rows = rows
        matched_cat = None

        # 尝试通过表格【前一段说明段落】及【表格前两行】的文本匹配分类
        table_text = ""

        # 1. 抓取表格紧挨着的上一段说明文字（非常关键）。
        #    例如"本表记录...德州市市..."写在表格上方的段落里，表头本身只写了
        #    "城市 | 站点名称"，仅扫表格内部会匹配失败导致数据填不进去。
        #    注：lxml 的 .text 只取节点直接文本，docx 里文字嵌在 w:r/w:t 内，
        #    因此用 itertext() 才能取到完整段落文字。
        prev_node = table._element.getprevious()
        if prev_node is not None and prev_node.tag.endswith("}p"):
            table_text += "".join(prev_node.itertext()) + " "

        # 2. 抓取表格内部前两行文字
        for r_idx in range(min(2, len(table.rows))):
            table_text += " ".join(c.text for c in table.rows[r_idx].cells)

        for cat in list(rows_by_cat.keys()):
            if cat and cat in table_text:
                matched_cat = cat
                break

        if matched_cat:
            matched_rows = rows_by_cat[matched_cat]

        merged = _merge_rows(matched_rows)

        header_idx, col_map = _find_word_header_row(table, available_fields, user_mapping)
        if header_idx is not None and col_map:
            data_start = header_idx + 1
            for i, row_data in enumerate(matched_rows):
                target = data_start + i
                if target >= len(table.rows):
                    break
                for c_idx, field in col_map.items():
                    if c_idx >= len(table.rows[target].cells):
                        continue
                    value = row_data.get(field)
                    if value in SKIP_VALUES:
                        continue
                    table.rows[target].cells[c_idx].text = str(value)
                    filled.add(field)
        else:
            _fill_word_kv_mode(table, merged, available_fields, filled, user_mapping)

    doc.save(str(output_path))
    return filled


def _asset_template_by_name(template_name: str) -> Optional[Dict[str, Any]]:
    """UPLOAD_META 重启即丢；回退资产库按原始文件名查模板磁盘路径。"""
    if not template_name:
        return None
    try:
        with SessionLocal() as session:
            asset = (
                session.query(Asset)
                .filter(
                    Asset.role == "template",
                    Asset.original_name == template_name,
                )
                .order_by(Asset.id.desc())
                .first()
            )
            if asset and Path(asset.path).exists():
                return {
                    "path": asset.path,
                    "original_name": asset.original_name,
                    "ext": Path(asset.path).suffix.lower(),
                }
    except Exception as exc:
        logger.warning("资产库回退查询模板 %s 失败: %s", template_name, exc)
    return None


# ============ 导出入口 ============
async def generate_exported_file(
    confirmed_data: List[Dict[str, Any]], template_name: str, task_id: str = ""
) -> Dict[str, Any]:
    """
    将确认后的提取数据套入指定模板，生成可下载文件。
    模板按 template_name 从已上传的模板文件（UPLOAD_META）中查找，同
    名时取最近上传的那份。
    返回遵守 ExportResponse 契约：download_url / message。
    """
    # 1. 查找模板
    template_meta: Optional[Dict[str, Any]] = None
    for meta in UPLOAD_META.values():
        if meta["role"] == "template" and meta["original_name"] == template_name:
            template_meta = meta  # 后写覆盖前写 -> 同名取最近上传

    # UPLOAD_META 为内存登记，后端重启即丢失；草稿恢复的导出请求需回退
    # 资产库按模板名查磁盘路径（role=template，取最新一条且文件仍存在）
    if not template_meta:
        template_meta = _asset_template_by_name(template_name)

    if not template_meta:
        raise HTTPException(404, f"未找到模板文件「{template_name}」，请先上传模板")

    template_path = Path(template_meta["path"])
    if not template_path.exists():
        raise HTTPException(404, "模板文件已丢失，请重新上传")
    template_ext = template_meta.get("ext") or template_path.suffix.lower()
    if template_ext not in (".docx", ".xlsx"):
        raise HTTPException(400, f"模板仅支持 docx/xlsx，当前：{template_ext}")

    # 2. 展平数据
    rows = _collect_rows(confirmed_data or [])
    if not rows:
        raise HTTPException(400, "confirmed_data 为空，无数据可填充")

    available_fields = _collect_available_fields(rows)
    if not available_fields:
        raise HTTPException(400, "没有可填充的字段")

    # 3. 填充并生成文件（填充函数从模板读取、另存为输出文件）
    out_id = uuid.uuid4().hex
    stem = Path(template_meta["original_name"]).stem
    out_name = f"{stem}_filled_{out_id[:8]}{template_ext}"
    out_path = EXPORT_DIR / out_name

    try:
        if template_ext == ".xlsx":
            filled = await run_in_threadpool(
                fill_excel_template, template_path, rows, out_path
            )
        else:
            filled = await run_in_threadpool(
                fill_word_template, template_path, rows, out_path
            )
    except Exception as e:
        out_path.unlink(missing_ok=True)
        logging.exception("模板填充失败: %s", out_name)
        raise HTTPException(500, f"填充失败：{type(e).__name__}: {e}")

    # 4. 登记导出文件并返回（内存 + 数据库双登记，重启后仍可重复下载）
    EXPORT_META[out_id] = {"path": str(out_path), "filename": out_name}
    record_export(
        task_id=int(task_id) if str(task_id).isdigit() else None,
        file_id=out_id,
        filename=out_name,
        path=str(out_path),
        template_asset_id=template_meta.get("asset_id"),
    )

    unfilled = [f for f in available_fields if f not in filled]
    message = f"生成成功：{out_name}（填充 {len(filled)}/{len(available_fields)} 个字段）"
    if unfilled:
        message += f"，未填充：{'、'.join(unfilled)}"
    return {
        "download_url": f"/api/download/{out_id}",
        "message": message,
    }


def preview_exported_file(file_id: str) -> Dict[str, str]:
    """解析已生成的导出文件，返回文件名与文本内容，供前端预览。"""
    meta = EXPORT_META.get(file_id)
    if not meta:
        meta = find_export_by_file_id(file_id)  # 内存 miss 回源数据库
        if meta:
            EXPORT_META[file_id] = meta
    if not meta or not Path(meta["path"]).exists():
        raise HTTPException(404, "文件不存在或已过期")
    path = Path(meta["path"])
    status, content, error = parse_file(path, path.suffix.lower())
    if status != "success":
        raise HTTPException(400, f"预览失败：{error or '无法解析文件内容'}")
    return {"filename": meta["filename"], "content": content}
