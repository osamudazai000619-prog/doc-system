"""
草稿箱持久化：未完成任务的工作区快照。
上限 DRAFT_MAX 条，超出时自动淘汰最久未更新的一条。
后端不理解 payload 内部结构，只做透存透取。
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

from db.database import SessionLocal
from db.models import Draft

logger = logging.getLogger(__name__)

DRAFT_MAX = 20

# 草稿自动命名格式：草稿（n）
_DRAFT_NAME_RE = re.compile(r"^草稿（(\d+)）$")


def _next_draft_title(session) -> str:
    """生成下一个草稿名：现有「草稿（n）」中最大序号 + 1（删除后也不重复）。"""
    max_n = 0
    for d in session.query(Draft).all():
        m = _DRAFT_NAME_RE.match(d.title or "")
        if m:
            max_n = max(max_n, int(m.group(1)))
    return "草稿（%d）" % (max_n + 1)


def save_draft(
    title: str,
    step: str,
    template_name: str,
    file_count: int,
    field_count: int,
    payload: Dict[str, Any],
    draft_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    保存草稿，返回 {"id", "evicted"}；evicted 为被自动淘汰的草稿标题（无则 None）。
    传 draft_id 则覆盖更新同一条（不新增、不触发淘汰）。
    """
    evicted: Optional[str] = None
    with SessionLocal() as session:
        if draft_id:
            draft = session.get(Draft, draft_id)
            if draft is None:
                draft_id = None  # 已被删，退化为新建
        if not draft_id:
            draft = Draft()
            session.add(draft)

        # 标题为空或纯空白时自动命名「草稿（n）」；用户/前端显式给名则尊重
        if not (title or "").strip():
            title = _next_draft_title(session)
        draft.title = title.strip()
        draft.step = step or "/upload"
        draft.template_name = template_name or ""
        draft.file_count = int(file_count or 0)
        draft.field_count = int(field_count or 0)
        draft.payload_json = json.dumps(payload or {}, ensure_ascii=False)
        session.flush()

        # 超上限淘汰最久未更新的（排除刚保存的这条）
        total = session.query(Draft).count()
        if total > DRAFT_MAX:
            overflow = (
                session.query(Draft)
                .filter(Draft.id != draft.id)
                .order_by(Draft.updated_at.asc(), Draft.id.asc())
                .limit(total - DRAFT_MAX)
                .all()
            )
            for old in overflow:
                evicted = old.title
                session.delete(old)

        session.commit()
        session.refresh(draft)
        logger.info("草稿已保存: id=%s, title=%s, 淘汰=%s", draft.id, draft.title, evicted)
        return {"id": draft.id, "evicted": evicted}


def rename_draft(draft_id: int, title: str) -> bool:
    """草稿重命名；空标题拒绝（避免列表出现空白条目）。"""
    title = (title or "").strip()
    if not title:
        return False
    with SessionLocal() as session:
        d = session.get(Draft, draft_id)
        if d is None:
            return False
        d.title = title
        session.commit()
        return True


def delete_drafts(draft_ids: List[int]) -> int:
    """批量删除草稿，返回实际删除条数。"""
    if not draft_ids:
        return 0
    with SessionLocal() as session:
        n = (
            session.query(Draft)
            .filter(Draft.id.in_(draft_ids))
            .delete(synchronize_session=False)
        )
        session.commit()
        return n


def list_drafts() -> List[Dict[str, Any]]:
    """草稿列表（按更新时间倒序），只回摘要不回 payload。"""
    with SessionLocal() as session:
        drafts = (
            session.query(Draft)
            .order_by(Draft.updated_at.desc(), Draft.id.desc())
            .all()
        )
        return [
            {
                "id": d.id,
                "title": d.title,
                "step": d.step,
                "template_name": d.template_name,
                "file_count": d.file_count,
                "field_count": d.field_count,
                "updated_at": d.updated_at.strftime("%Y-%m-%d %H:%M:%S") if d.updated_at else "",
            }
            for d in drafts
        ]


def get_draft(draft_id: int) -> Optional[Dict[str, Any]]:
    """草稿详情，含完整 payload（恢复时调用）。"""
    with SessionLocal() as session:
        d = session.get(Draft, draft_id)
        if d is None:
            return None
        return {
            "id": d.id,
            "title": d.title,
            "step": d.step,
            "template_name": d.template_name,
            "payload": json.loads(d.payload_json or "{}"),
            "updated_at": d.updated_at.strftime("%Y-%m-%d %H:%M:%S") if d.updated_at else "",
        }


def delete_draft(draft_id: int) -> bool:
    with SessionLocal() as session:
        d = session.get(Draft, draft_id)
        if d is None:
            return False
        session.delete(d)
        session.commit()
        logger.info("草稿已删除: id=%s", draft_id)
        return True
