import logging
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from docx import Document
from openpyxl import load_workbook

BASE_DIR = Path("uploads")
TARGET_DIR = BASE_DIR / "targets"
TEMPLATE_DIR = BASE_DIR / "templates"
for _d in (TARGET_DIR, TEMPLATE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = {".docx", ".txt", ".md", ".xlsx"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

# 已上传文件的元数据（file_id -> meta）。export 服务依赖它按模板名查找文件路径。
# 单进程内存态即可满足当前 demo；生产环境建议替换为 Redis / 数据库
UPLOAD_META: Dict[str, Dict[str, Any]] = {}


def safe_filename(name: str) -> str:
    """清理文件名，防止路径穿越和奇怪字符。"""
    name = Path(name or "unnamed").name
    return re.sub(r"[^\w\u4e00-\u9fa5.\-]+", "_", name)


def save_upload_file(upload: UploadFile, role: str) -> Tuple[str, Path, str, str]:
    """
    保存上传文件到对应目录。
    role: target / template
    返回: file_id, save_path, original_name, ext
    """
    original = safe_filename(upload.filename or "unnamed")
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ValueError(f"不支持的文件格式：{ext or '未知'}，仅支持 DOCX/TXT/MD/XLSX")

    file_id = uuid.uuid4().hex
    save_dir = TARGET_DIR if role == "target" else TEMPLATE_DIR
    save_path = save_dir / f"{file_id}{ext}"

    size = 0
    with save_path.open("wb") as f:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                f.close()
                save_path.unlink(missing_ok=True)
                raise ValueError(f"文件超过大小限制（>{MAX_FILE_SIZE // 1024 // 1024}MB）")
            f.write(chunk)

    UPLOAD_META[file_id] = {
        "file_id": file_id,
        "path": str(save_path),
        "original_name": original,
        "role": role,
        "ext": ext,
        "size": size,
    }
    return file_id, save_path, original, ext


def read_text_file(path: Path) -> str:
    """读取 txt/md，尝试多种编码。"""
    raw = path.read_bytes()
    for enc in ("utf-8", "utf-8-sig", "gb18030", "gbk", "big5", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_docx(path: Path) -> str:
    """解析 DOCX：段落 + 普通表格。"""
    doc = Document(str(path))
    parts = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if text:
            parts.append(text)
    for idx, table in enumerate(doc.tables, 1):
        parts.append(f"[表格{idx}]")
        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n".join(parts).strip()


def parse_xlsx(path: Path) -> str:
    """解析 XLSX：每个 sheet 的单元格文本。"""
    wb = load_workbook(filename=str(path), read_only=True, data_only=True)
    parts = []
    try:
        for ws in wb.worksheets:
            parts.append(f"[工作表] {ws.title}")
            for row in ws.iter_rows(values_only=True):
                vals = ["" if v is None else str(v) for v in row]
                if any(v.strip() for v in vals):
                    parts.append(" | ".join(vals).rstrip())
            parts.append("")
    finally:
        wb.close()
    return "\n".join(parts).strip()


def parse_file(path: Path, ext: str) -> Tuple[str, str, Optional[str]]:
    """
    统一解析入口。
    返回: status, content, error
    status: success / unsupported / empty / error
    """
    try:
        if ext == ".docx":
            content = parse_docx(path)
        elif ext == ".xlsx":
            content = parse_xlsx(path)
        elif ext in (".txt", ".md"):
            content = read_text_file(path)
        else:
            return "unsupported", "", f"不支持的文件格式：{ext}"
        if not content or not content.strip():
            return "empty", "", "文件解析后内容为空"
        return "success", content, None
    except Exception as e:
        logging.exception("解析文件异常: %s", path)
        return "error", "", f"解析失败：{type(e).__name__}: {e}"


async def process_upload_files(
    target_files: List[UploadFile],
    template_files: List[UploadFile],
) -> List[Dict[str, Any]]:
    """
    保存并解析 target / template 两类文件，返回每个文件的解析状态与文本内容。
    模板文件同样保存到 TEMPLATE_DIR 并登记进 UPLOAD_META，供导出时按模板名取用。
    返回结构遵守 UploadResponseItem 契约：filename / status / content。
    """
    results: List[Dict[str, Any]] = []
    for role, files in (("target", target_files), ("template", template_files)):
        for uf in files or []:
            original = safe_filename(uf.filename or "unnamed")
            ext = Path(original).suffix.lower()

            # 格式不支持，不保存
            if ext not in ALLOWED_EXT:
                results.append({
                    "filename": original,
                    "status": "unsupported",
                    "content": "",
                })
                continue

            try:
                # 阻塞的磁盘 IO / 解析放入线程池，避免卡住事件循环
                _, save_path, original, ext = await run_in_threadpool(
                    save_upload_file, uf, role
                )
                status, content, _ = await run_in_threadpool(parse_file, save_path, ext)
            except Exception as e:
                logging.exception("文件上传保存失败: %s", original)
                status, content = "error", ""

            results.append({
                "filename": original,
                "status": status,
                "content": content if status == "success" else "",
            })
    return results
