"""
数据模型定义。

分层关系：assets（文件资产库，sha256 去重）
  ← schemes（方案：模板引用 + 提示词 + 字段，阶段二启用）
  ← tasks（任务历史：配置快照 + 提取结果，方案被改不污染旧记录）
  ← exports（导出产物：重复下载直接重发文件，零成本）
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class Asset(Base):
    """文件资产库：同内容文件（sha256 相同）只存一份，支撑"模板复用"。"""
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    ext: Mapped[str] = mapped_column(String(16))
    role: Mapped[str] = mapped_column(String(16))  # target / template
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    path: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Scheme(Base):
    """提取方案：模板资产 + 提示词 + 字段的一整套配置（阶段二启用）。"""
    __tablename__ = "schemes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    template_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("assets.id"), nullable=True
    )
    prompt: Mapped[str] = mapped_column(Text, default="")
    fields_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Task(Base):
    """
    任务历史：一次完整提取流程一条记录。
    配置（提示词/字段/模板）存快照而非方案引用，方案后续编辑不影响旧记录。
    """
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheme_id: Mapped[int | None] = mapped_column(
        ForeignKey("schemes.id"), nullable=True
    )
    prompt_snapshot: Mapped[str] = mapped_column(Text, default="")
    fields_json: Mapped[str] = mapped_column(Text, default="[]")
    template_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("assets.id"), nullable=True
    )
    template_name: Mapped[str] = mapped_column(String(255), default="")
    title: Mapped[str] = mapped_column(String(255), default="")  # 用户可编辑的显示名
    source_files_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(16), default="extracted")  # extracted / exported
    stats_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, index=True
    )


class ExportRecord(Base):
    """
    导出产物登记。file_id 与现有 /api/download/{file_id} 的内存登记共用同一 id，
    使下载接口在内存 miss 时可回源数据库，重启后仍可重复下载。
    """
    __tablename__ = "exports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id"), nullable=True, index=True
    )
    file_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    template_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("assets.id"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Draft(Base):
    """
    草稿箱：未完成任务的工作区快照。
    payload_json 由前端自定义（文件解析结果/提示词/字段/提取结果/所处步骤），
    后端只做透存透取，不理解内部结构；列表查询只回摘要列，不回大 payload。
    """
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), default="未命名任务")
    step: Mapped[str] = mapped_column(String(32), default="/upload")  # 恢复时跳转的路由
    template_name: Mapped[str] = mapped_column(String(255), default="")
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    field_count: Mapped[int] = mapped_column(Integer, default=0)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, index=True
    )
