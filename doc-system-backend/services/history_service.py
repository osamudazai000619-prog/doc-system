"""
任务历史与导出产物持久化。

写入时机（与既定契约一致，均为增量行为）：
- 提取完成 → record_extraction：tasks 落一条快照（status=extracted）
- 导出成功 → record_export：exports 落产物记录，tasks.status 更新为 exported
读取：
- 历史列表/详情走 tasks + exports 联查，且仅含 status=exported 的任务
  （仅提取未导出、未走完流程的任务不进历史）
- /api/download/{file_id} 内存 miss 时经 find_export_by_file_id 回源，
  保证后端重启后历史产物仍可重复下载
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from db.database import SessionLocal
from db.models import ExportRecord, Task

logger = logging.getLogger(__name__)


def record_extraction(
    prompt: str,
    fields: List[str],
    results: List[Dict[str, Any]],
    source_filenames: List[str],
    template_asset_id: Optional[int],
    template_name: str,
) -> Optional[int]:
    """
    提取完成后落一条任务记录，返回 task_id。
    result_json 即 ExtractResponseItem 列表（契约结构原样快照）。
    失败只记日志返回 None，不影响提取响应。
    """
    try:
        record_count = sum(
            len(f.get("extracted_tables") or []) for f in results or []
        )
        stats = {"file_count": len(results or []), "record_count": record_count}
        with SessionLocal() as session:
            task = Task(
                prompt_snapshot=prompt or "",
                fields_json=json.dumps(fields or [], ensure_ascii=False),
                template_asset_id=template_asset_id,
                template_name=template_name or "",
                source_files_json=json.dumps(source_filenames or [], ensure_ascii=False),
                status="extracted",
                stats_json=json.dumps(stats, ensure_ascii=False),
                result_json=json.dumps(results or [], ensure_ascii=False),
            )
            session.add(task)
            session.commit()
            session.refresh(task)
            logger.info("任务历史已记录: task_id=%s, 文件数=%s, 记录数=%s",
                        task.id, stats["file_count"], stats["record_count"])
            return task.id
    except Exception:
        logger.exception("任务历史记录失败")
        return None


def record_export(
    task_id: Optional[int],
    file_id: str,
    filename: str,
    path: str,
    template_asset_id: Optional[int],
) -> Optional[int]:
    """导出成功后登记产物并回写任务状态为 exported。失败只记日志。"""
    try:
        with SessionLocal() as session:
            rec = ExportRecord(
                task_id=task_id,
                file_id=file_id,
                template_asset_id=template_asset_id,
                filename=filename,
                path=path,
            )
            session.add(rec)
            if task_id:
                task = session.get(Task, task_id)
                if task is not None:
                    task.status = "exported"
            session.commit()
            session.refresh(rec)
            logger.info("导出产物已登记: export_id=%s, task_id=%s, file=%s",
                        rec.id, task_id, filename)
            return rec.id
    except Exception:
        logger.exception("导出产物登记失败: file_id=%s", file_id)
        return None


def find_export_by_file_id(file_id: str) -> Optional[Dict[str, str]]:
    """按 file_id 查导出产物（下载/预览的 DB 兜底）。"""
    try:
        with SessionLocal() as session:
            rec = session.query(ExportRecord).filter_by(file_id=file_id).first()
            if rec is None:
                return None
            return {"path": rec.path, "filename": rec.filename}
    except Exception:
        logger.exception("查询导出产物失败: file_id=%s", file_id)
        return None


def rename_task(task_id: int, title: str) -> bool:
    """历史任务重命名（仅改显示名，不动 template_name 等业务字段）。"""
    title = (title or "").strip()
    if not title:
        return False
    with SessionLocal() as session:
        task = session.get(Task, task_id)
        if task is None:
            return False
        task.title = title
        session.commit()
        return True


def delete_tasks(task_ids: List[int]) -> int:
    """批量删除历史任务及其导出产物登记（磁盘文件留给清理脚本回收）。"""
    if not task_ids:
        return 0
    with SessionLocal() as session:
        session.query(ExportRecord).filter(
            ExportRecord.task_id.in_(task_ids)
        ).delete(synchronize_session=False)
        n = (
            session.query(Task)
            .filter(Task.id.in_(task_ids))
            .delete(synchronize_session=False)
        )
        session.commit()
        return n


def _task_to_list_item(task: Task, export: Optional[ExportRecord]) -> Dict[str, Any]:
    stats = json.loads(task.stats_json or "{}")
    return {
        "id": task.id,
        "created_at": task.created_at.strftime("%Y-%m-%d %H:%M:%S") if task.created_at else "",
        "status": task.status,
        "template_name": task.template_name,
        "title": task.title or "",
        "fields": json.loads(task.fields_json or "[]"),
        "prompt_preview": (task.prompt_snapshot or "")[:80],
        "source_files": json.loads(task.source_files_json or "[]"),
        "file_count": stats.get("file_count", 0),
        "record_count": stats.get("record_count", 0),
        "export_file_id": export.file_id if export else "",
        "export_filename": export.filename if export else "",
    }


def list_tasks(page: int = 1, size: int = 20) -> Dict[str, Any]:
    """历史任务列表（按时间倒序，分页）。每条附带最近一次导出产物信息。

    仅返回走完流程（status=exported）的任务；仅提取未导出的任务不进历史。
    """
    page = max(page, 1)
    size = min(max(size, 1), 100)
    with SessionLocal() as session:
        base_q = session.query(Task).filter(Task.status == "exported")
        total = base_q.count()
        tasks = (
            base_q
            .order_by(Task.created_at.desc(), Task.id.desc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        task_ids = [t.id for t in tasks]
        exports: Dict[int, ExportRecord] = {}
        if task_ids:
            recs = (
                session.query(ExportRecord)
                .filter(ExportRecord.task_id.in_(task_ids))
                .order_by(ExportRecord.id.desc())
                .all()
            )
            for rec in recs:  # id 倒序遍历，首次出现即最近一次导出
                exports.setdefault(rec.task_id, rec)
        return {
            "total": total,
            "page": page,
            "size": size,
            "items": [_task_to_list_item(t, exports.get(t.id)) for t in tasks],
        }


def get_task_detail(task_id: int) -> Optional[Dict[str, Any]]:
    """任务详情：配置快照 + 结果快照 + 全部导出产物。

    仅对走完流程（status=exported）的任务可见，未导出的任务按不存在处理（404）。
    """
    with SessionLocal() as session:
        task = session.get(Task, task_id)
        if task is None or task.status != "exported":
            return None
        exports = (
            session.query(ExportRecord)
            .filter_by(task_id=task_id)
            .order_by(ExportRecord.id.desc())
            .all()
        )
        return {
            "id": task.id,
            "created_at": task.created_at.strftime("%Y-%m-%d %H:%M:%S") if task.created_at else "",
            "status": task.status,
            "prompt": task.prompt_snapshot or "",
            "fields": json.loads(task.fields_json or "[]"),
            "template_name": task.template_name,
            "title": task.title or "",
            "template_asset_id": task.template_asset_id,
            "source_files": json.loads(task.source_files_json or "[]"),
            "stats": json.loads(task.stats_json or "{}"),
            "results": json.loads(task.result_json or "[]"),
            "exports": [
                {
                    "file_id": e.file_id,
                    "filename": e.filename,
                    "created_at": e.created_at.strftime("%Y-%m-%d %H:%M:%S") if e.created_at else "",
                }
                for e in exports
            ],
        }
