"""
文件资产登记：按 sha256 去重写入 assets 表。
同内容文件重复上传时复用已有资产记录，为"模板复用/方案引用"提供稳定 id。
"""
import hashlib
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from db.database import SessionLocal
from db.models import Asset

logger = logging.getLogger(__name__)


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def register_asset(
    path: Path, original_name: str, ext: str, role: str, size: int
) -> Tuple[Optional[int], Path]:
    """
    登记文件资产，返回 (asset_id, 有效路径)。
    - 同 sha256 已存在且磁盘文件仍在：删除本次重复落盘的文件，复用原路径；
    - 同 sha256 但原文件已丢失：改指向新路径；
    失败只记日志返回 (None, 原路径)，不阻断上传主流程。
    """
    try:
        digest = _sha256_of(path)
        with SessionLocal() as session:
            asset = session.query(Asset).filter_by(sha256=digest).first()
            if asset is None:
                asset = Asset(
                    sha256=digest,
                    original_name=original_name,
                    ext=ext,
                    role=role,
                    size=size,
                    path=str(path),
                )
                session.add(asset)
                session.commit()
                session.refresh(asset)
                return asset.id, path

            if Path(asset.path).exists():
                # 内容相同，本次落盘的是冗余副本，删除并复用原文件
                if Path(asset.path) != path:
                    path.unlink(missing_ok=True)
                return asset.id, Path(asset.path)

            asset.path = str(path)
            asset.original_name = original_name
            asset.role = role
            asset.size = size
            session.commit()
            return asset.id, path
    except Exception:
        logger.exception("文件资产登记失败: %s", path)
        return None, path


def get_asset_path(asset_id: Optional[int]) -> Optional[str]:
    if not asset_id:
        return None
    try:
        with SessionLocal() as session:
            asset = session.get(Asset, asset_id)
            return asset.path if asset else None
    except Exception:
        logger.exception("读取资产失败: id=%s", asset_id)
        return None


def load_asset_as_upload(asset_id: int, upload_service_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    把已存在的资产文件加载到 UPLOAD_META（不重复落盘），
    使导出服务能按模板名找到它。返回兼容 UploadResponseItem 的元数据。
    失败只记日志返回 None。
    """
    try:
        with SessionLocal() as session:
            asset = session.get(Asset, asset_id)
            if asset is None:
                logger.warning("资产不存在: id=%s", asset_id)
                return None
            if not Path(asset.path).exists():
                logger.warning("资产文件已丢失: id=%s, path=%s", asset_id, asset.path)
                return None

            file_id = uuid.uuid4().hex
            upload_service_meta[file_id] = {
                "file_id": file_id,
                "path": asset.path,
                "original_name": asset.original_name,
                "role": asset.role,
                "ext": asset.ext,
                "size": asset.size,
                "asset_id": asset.id,
            }
            return {
                "filename": asset.original_name,
                "status": "success",
                "content": "",
                "role": asset.role,
                "error": "",
                "file_id": file_id,
            }
    except Exception:
        logger.exception("加载资产到上传元数据失败: id=%s", asset_id)
        return None
