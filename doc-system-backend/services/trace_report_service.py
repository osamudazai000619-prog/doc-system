# ============================================================
# trace_report_service.py —— 生成「文档提取溯源报告」PDF
# 依赖：reportlab。中文字体优先使用 WenQuanYi Zen Hei
# （/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc，Linux 部署环境），
# 缺失时回退到 reportlab 内置简体中文字体 STSong-Light，保证跨平台可用。
# ============================================================
import os
import io
from datetime import datetime
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)

# ------------------------------------------------------------
# 中文字体注册（模块加载时执行一次）
# ------------------------------------------------------------
_FONT_NAME = "Helvetica"
try:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    _WQY_PATH = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
    if os.path.exists(_WQY_PATH):
        # .ttc 为字体集合，需指定 subfontIndex
        pdfmetrics.registerFont(TTFont("WQY", _WQY_PATH, subfontIndex=0))
        _FONT_NAME = "WQY"
    else:
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        _FONT_NAME = "STSong-Light"
except Exception:  # pragma: no cover - 极端环境兜底
    _FONT_NAME = "Helvetica"


# 风险标记 → （显示文案, 颜色）
_RISK_META = {
    "not_found": ("未找到", colors.HexColor("#f56c6c")),
    "low_confidence": ("低置信度", colors.HexColor("#e6a23c")),
    "conflict": ("冲突", colors.HexColor("#c9a227")),
    "no_source": ("无来源", colors.HexColor("#409eff")),
}


def _cell_value(cell: Any) -> str:
    """兼容单元格为 dict（{value,source,...}）或纯字符串两种形态。"""
    if isinstance(cell, dict):
        return str(cell.get("value") or "")
    return str(cell or "")


def _cell_meta(cell: Any) -> Dict[str, Any]:
    """取出单元格的溯源元信息；纯字符串时返回空结构。"""
    if isinstance(cell, dict):
        return {
            "source": cell.get("source"),
            "context": cell.get("context"),
            "confidence": cell.get("confidence"),
            "risk": cell.get("risk") or [],
        }
    return {"source": None, "context": None, "confidence": None, "risk": []}


def _fmt_source(source: Any) -> str:
    if not isinstance(source, dict):
        return "—"
    pid = source.get("para_id")
    page = source.get("page")
    start = source.get("start")
    end = source.get("end")
    parts = []
    if pid is not None:
        parts.append(f"段落 #{pid}")
    if page is not None:
        parts.append(f"第 {page} 页")
    if start is not None and end is not None:
        parts.append(f"偏移 {start}-{end}")
    return "，".join(parts) if parts else "—"


def _fmt_confidence(conf: Any) -> str:
    if conf is None or conf == "":
        return "—"
    try:
        return f"{float(conf) * 100:.0f}%"
    except (TypeError, ValueError):
        return str(conf)


def _risk_labels(risks: Any) -> str:
    if not risks:
        return "—"
    labels = [_RISK_META.get(r, (r, None))[0] for r in risks]
    return "、".join(labels) if labels else "—"


def _truncate(text: str, limit: int = 100) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit] + "…"


def _para(text: str, style: ParagraphStyle) -> Paragraph:
    # XML 转义，避免 < > & 破坏 Paragraph
    safe = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, style)


def generate_trace_report_pdf(results: List[Dict[str, Any]]) -> bytes:
    """根据提取结果生成溯源报告 PDF，返回二进制内容。"""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title="文档提取溯源报告",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleCN", parent=styles["Title"], fontName=_FONT_NAME, fontSize=20,
        leading=26, textColor=colors.HexColor("#303133"), spaceAfter=10,
    )
    h2 = ParagraphStyle(
        "H2CN", parent=styles["Heading2"], fontName=_FONT_NAME, fontSize=14,
        leading=20, textColor=colors.HexColor("#303133"), spaceBefore=10, spaceAfter=6,
    )
    normal = ParagraphStyle(
        "NormalCN", parent=styles["Normal"], fontName=_FONT_NAME, fontSize=10,
        leading=15, textColor=colors.HexColor("#303133"),
    )
    small = ParagraphStyle(
        "SmallCN", parent=normal, fontSize=9, leading=13,
        textColor=colors.HexColor("#606266"),
    )

    story = []
    story.append(Paragraph("文档提取溯源报告", title_style))
    story.append(Spacer(1, 4 * mm))

    # ---------- 基本信息区 ----------
    file_names = [r.get("source_file", "unknown") for r in (results or [])]
    field_set = set()
    total_rows = 0
    risk_counter: Dict[str, int] = {k: 0 for k in _RISK_META}

    for f in (results or []):
        for t in f.get("extracted_tables", []) or []:
            recs = t.get("records", {})
            rec_list = [recs] if isinstance(recs, dict) else (recs or [])
            for rec in rec_list:
                if not isinstance(rec, dict):
                    continue
                total_rows += 1
                for k in rec.keys():
                    if not str(k).startswith("_"):
                        field_set.add(k)

    basic = [
        ["文件名", "、".join(file_names) if file_names else "—"],
        ["提取时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["文件数量", str(len(file_names))],
        ["字段数量", str(len(field_set))],
        ["记录行数", str(total_rows)],
    ]
    basic_tbl = Table(
        [[_para(r[0], normal), _para(r[1], normal)] for r in basic],
        colWidths=[28 * mm, 140 * mm],
    )
    basic_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), _FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f7fa")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#606266")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dcdfe6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(Paragraph("一、基本信息", h2))
    story.append(basic_tbl)
    story.append(Spacer(1, 5 * mm))

    # ---------- 溯源详情表格 ----------
    story.append(Paragraph("二、溯源详情", h2))
    header = ["字段名", "提取值", "置信度", "来源段落", "原文上下文", "风险标记"]
    table_rows: List[List[Paragraph]] = [[_para(h, normal) for h in header]]

    for f in (results or []):
        sfile = f.get("source_file", "")
        for t in f.get("extracted_tables", []) or []:
            cat = t.get("table_category", "")
            recs = t.get("records", {})
            rec_list = [recs] if isinstance(recs, dict) else (recs or [])
            for rec in rec_list:
                if not isinstance(rec, dict):
                    continue
                for field, cell in rec.items():
                    if str(field).startswith("_"):
                        continue
                    meta = _cell_meta(cell)
                    for r in (meta["risk"] or []):
                        if r in risk_counter:
                            risk_counter[r] += 1
                    label_prefix = f"[{sfile}/{cat}] " if (sfile or cat) else ""
                    table_rows.append([
                        _para(label_prefix + str(field), small),
                        _para(_truncate(_cell_value(cell), 120), small),
                        _para(_fmt_confidence(meta["confidence"]), small),
                        _para(_fmt_source(meta["source"]), small),
                        _para(_truncate(meta["context"] or "", 100), small),
                        _para(_risk_labels(meta["risk"]), small),
                    ])

    if len(table_rows) == 1:
        table_rows.append([_para("（暂无提取结果）", small)] + [_para("", small)] * 5)

    detail_tbl = Table(
        table_rows,
        colWidths=[34 * mm, 40 * mm, 18 * mm, 30 * mm, 34 * mm, 20 * mm],
        repeatRows=1,
    )
    detail_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), _FONT_NAME),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f5f7fa")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#303133")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dcdfe6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(detail_tbl)
    story.append(Spacer(1, 5 * mm))

    # ---------- 风险汇总区 ----------
    story.append(Paragraph("三、风险汇总", h2))
    has_alert = risk_counter.get("not_found", 0) > 0 or risk_counter.get("conflict", 0) > 0
    summary_header = ["风险类型", "数量", "说明"]
    summary_rows = [[_para(h, normal) for h in summary_header]]
    explain = {
        "not_found": "模型未从文档中提取到该字段值",
        "low_confidence": "提取置信度较低，建议人工复核",
        "conflict": "多源结果存在冲突，需人工判定",
        "no_source": "未能定位到来源段落",
    }
    for key, (label, _clr) in _RISK_META.items():
        summary_rows.append([
            _para(label, normal),
            _para(str(risk_counter.get(key, 0)), normal),
            _para(explain.get(key, ""), small),
        ])
    summary_tbl = Table(summary_rows, colWidths=[30 * mm, 25 * mm, 113 * mm])
    style_cmds = [
        ("FONTNAME", (0, 0), (-1, -1), _FONT_NAME),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f5f7fa")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dcdfe6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    # not_found / conflict 高亮（行背景浅红）
    for idx, key in enumerate(_RISK_META.keys(), start=1):
        if risk_counter.get(key, 0) > 0 and key in ("not_found", "conflict"):
            style_cmds.append(("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#fef0f0")))
            style_cmds.append(("TEXTCOLOR", (0, idx), (-1, idx), colors.HexColor("#f56c6c")))
    summary_tbl.setStyle(TableStyle(style_cmds))
    story.append(summary_tbl)

    if has_alert:
        story.append(Spacer(1, 3 * mm))
        warn = ParagraphStyle(
            "WarnCN", parent=normal, fontSize=10, leading=15,
            textColor=colors.HexColor("#f56c6c"),
        )
        story.append(Paragraph(
            "⚠ 提醒：本报告存在「未找到」或「冲突」风险项，请重点人工复核对应记录。", warn
        ))

    doc.build(story)
    return buf.getvalue()
