r"""
uploads 清理脚本：
- exports/：默认只删"未被 exports 表引用且超期"的孤儿文件；
  历史导出文件在 exports 表有登记，历史任务弹窗依赖它重复下载，默认不删。
  加 --purge-exports-days N 才级联清理超期导出记录（删 DB 行 + 磁盘文件），
  清理后历史弹窗对应下载条目随之消失。
- targets/ 与 templates/：仅删除"未被 assets 表任何行引用 且 超过 N 天"的孤儿文件；
  被资产表引用的文件是资产库的真实存储，永不删除。

默认 dry-run（只列出将删除的文件，不实际删除），加 --apply 才真正执行。

用法（在后端根目录下运行）：
    .venv\Scripts\python.exe cleanup_uploads.py                          # dry-run
    .venv\Scripts\python.exe cleanup_uploads.py --apply                  # 实际删除
    .venv\Scripts\python.exe cleanup_uploads.py --days 3 --apply
    .venv\Scripts\python.exe cleanup_uploads.py --purge-exports-days 30 --apply
"""
import argparse
import time
from datetime import datetime
from pathlib import Path

from db.database import SessionLocal
from db.models import Asset, ExportRecord

BASE = Path(__file__).resolve().parent / "uploads"


def _resolve_set(rows) -> set:
    return {str(Path(p).resolve()) for (p,) in rows if p}


def main() -> None:
    ap = argparse.ArgumentParser(description="uploads 清理脚本（默认 dry-run）")
    ap.add_argument("--days", type=int, default=7, help="孤儿文件年龄阈值（天），默认 7")
    ap.add_argument(
        "--purge-exports-days",
        type=int,
        default=None,
        help="级联清理超期导出记录（删 DB 行 + 文件），默认不清理历史导出",
    )
    ap.add_argument("--apply", action="store_true", help="真正删除文件（默认只列不删）")
    args = ap.parse_args()

    cutoff = time.time() - args.days * 86400

    with SessionLocal() as session:
        asset_paths = _resolve_set(session.query(Asset.path).all())
        export_paths = _resolve_set(session.query(ExportRecord.path).all())

    to_delete = []  # (path, reason, export_record_id)

    exports = BASE / "exports"
    if exports.is_dir():
        for f in exports.iterdir():
            if not f.is_file():
                continue
            if str(f.resolve()) in export_paths:
                continue  # 历史任务可重复下载，默认不删
            if f.stat().st_mtime < cutoff:
                to_delete.append((f, "超期导出孤儿文件（无 DB 引用）", None))

    for sub in ("targets", "templates"):
        d = BASE / sub
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if not f.is_file() or f.stat().st_mtime >= cutoff:
                continue
            if str(f.resolve()) in asset_paths:
                continue  # 资产库引用中，绝不删除
            to_delete.append((f, "未被资产引用的孤儿文件", None))

    if args.purge_exports_days is not None:
        cutoff2 = datetime.fromtimestamp(
            time.time() - args.purge_exports_days * 86400
        )
        with SessionLocal() as session:
            recs = (
                session.query(ExportRecord)
                .filter(ExportRecord.created_at < cutoff2)
                .all()
            )
            for rec in recs:
                to_delete.append(
                    (Path(rec.path), "超期导出记录（级联删 DB 行）", rec.id)
                )

    if not to_delete:
        print("无可清理文件。")
        return

    freed = 0
    deleted_ids = []
    for f, reason, rec_id in to_delete:
        size = f.stat().st_size if f.exists() else 0
        freed += size
        tag = "[删除]" if args.apply else "[将删除]"
        print(f"{tag} {reason}: {f} ({size} 字节)")
        if args.apply:
            f.unlink(missing_ok=True)
            if rec_id is not None:
                deleted_ids.append(rec_id)

    if args.apply and deleted_ids:
        with SessionLocal() as session:
            session.query(ExportRecord).filter(
                ExportRecord.id.in_(deleted_ids)
            ).delete(synchronize_session=False)
            session.commit()

    verb = "已释放" if args.apply else "预计释放"
    print(f"共 {len(to_delete)} 个文件，{verb} {freed / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
