"""
方案模板持久化：模板 + 提示词 + 字段的一整套配置。
- 同名方案视为重复，禁止重名
- 模板存 asset_id 引用，文件内容不落库
- last_used_at 由提取/导出流程回写，供推荐接口用
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from db.database import SessionLocal
from db.models import Asset, Scheme

logger = logging.getLogger(__name__)


def _scheme_to_dict(s: Scheme, template: Optional[Asset] = None) -> Dict[str, Any]:
    return {
        "id": s.id,
        "name": s.name,
        "template_asset_id": s.template_asset_id,
        "template_name": (template.original_name if template else ""),
        "prompt": s.prompt or "",
        "fields": json.loads(s.fields_json or "[]"),
        "created_at": s.created_at.strftime("%Y-%m-%d %H:%M:%S") if s.created_at else "",
        "updated_at": s.updated_at.strftime("%Y-%m-%d %H:%M:%S") if s.updated_at else "",
        "last_used_at": s.last_used_at.strftime("%Y-%m-%d %H:%M:%S") if s.last_used_at else "",
    }


def list_schemes() -> List[Dict[str, Any]]:
    """方案列表（按最后使用时间倒序，其次按更新时间）。"""
    with SessionLocal() as session:
        schemes = (
            session.query(Scheme)
            .order_by(
                Scheme.last_used_at.desc().nullslast(),
                Scheme.updated_at.desc(),
            )
            .all()
        )
        asset_ids = {s.template_asset_id for s in schemes if s.template_asset_id}
        assets = {}
        if asset_ids:
            for a in session.query(Asset).filter(Asset.id.in_(asset_ids)).all():
                assets[a.id] = a
        return [_scheme_to_dict(s, assets.get(s.template_asset_id)) for s in schemes]


def get_scheme(scheme_id: int) -> Optional[Dict[str, Any]]:
    with SessionLocal() as session:
        s = session.get(Scheme, scheme_id)
        if s is None:
            return None
        template = session.get(Asset, s.template_asset_id) if s.template_asset_id else None
        return _scheme_to_dict(s, template)


def save_scheme(
    name: str,
    prompt: str,
    fields: List[str],
    template_asset_id: Optional[int] = None,
    scheme_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    保存方案。传 scheme_id 则更新，否则新建。
    同名冲突抛 ValueError，由路由层转 400。
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("方案名称不能为空")

    with SessionLocal() as session:
        # 同名检查（排除自身）
        q = session.query(Scheme).filter(Scheme.name == name)
        if scheme_id:
            q = q.filter(Scheme.id != scheme_id)
        if q.first() is not None:
            raise ValueError("方案名称已存在")

        if scheme_id:
            scheme = session.get(Scheme, scheme_id)
            if scheme is None:
                raise ValueError("方案不存在")
        else:
            scheme = Scheme()
            session.add(scheme)

        scheme.name = name
        scheme.prompt = prompt or ""
        scheme.fields_json = json.dumps(fields or [], ensure_ascii=False)
        scheme.template_asset_id = template_asset_id
        session.commit()
        session.refresh(scheme)
        logger.info("方案已保存: id=%s, name=%s", scheme.id, scheme.name)
        return get_scheme(scheme.id)


def delete_scheme(scheme_id: int) -> bool:
    with SessionLocal() as session:
        s = session.get(Scheme, scheme_id)
        if s is None:
            return False
        session.delete(s)
        session.commit()
        logger.info("方案已删除: id=%s", scheme_id)
        return True


def touch_scheme(scheme_id: Optional[int]) -> None:
    """回写最后使用时间（提取/导出完成时调用）。"""
    if not scheme_id:
        return
    try:
        with SessionLocal() as session:
            s = session.get(Scheme, scheme_id)
            if s is not None:
                s.last_used_at = datetime.now()
                session.commit()
    except Exception:
        logger.exception("回写方案使用时间失败: id=%s", scheme_id)


def find_recommendation(template_asset_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """
    推荐逻辑：同一模板文件最近使用过的方案。
    优先用 tasks 快照反查最近一次提取配置；没有则找 schemes 里同模板最近使用的。
    """
    if not template_asset_id:
        return None
    try:
        with SessionLocal() as session:
            # 1. 从 tasks 快照反查最近一次同模板提取的配置
            from db.models import Task
            task = (
                session.query(Task)
                .filter(Task.template_asset_id == template_asset_id)
                .order_by(Task.created_at.desc(), Task.id.desc())
                .first()
            )
            if task is not None:
                return {
                    "source": "last_task",
                    "task_id": task.id,
                    "prompt": task.prompt_snapshot or "",
                    "fields": json.loads(task.fields_json or "[]"),
                    "used_at": task.created_at.strftime("%Y-%m-%d %H:%M:%S") if task.created_at else "",
                }

            # 2. 无历史任务则查 schemes 里同模板最近使用的
            scheme = (
                session.query(Scheme)
                .filter(Scheme.template_asset_id == template_asset_id)
                .order_by(Scheme.last_used_at.desc().nullslast(), Scheme.updated_at.desc())
                .first()
            )
            if scheme is not None:
                return {
                    "source": "scheme",
                    "scheme_id": scheme.id,
                    "scheme_name": scheme.name,
                    "prompt": scheme.prompt or "",
                    "fields": json.loads(scheme.fields_json or "[]"),
                    "used_at": scheme.last_used_at.strftime("%Y-%m-%d %H:%M:%S") if scheme.last_used_at else "",
                }
            return None
    except Exception:
        logger.exception("推荐查询失败: template_asset_id=%s", template_asset_id)
        return None
