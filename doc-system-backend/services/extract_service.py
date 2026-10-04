import os
import json
import re
import asyncio
import logging

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from models.schemas import ExtractedTable, ExtractResponseItem, TablePlan, TablePlanItem

# ================= 大模型初始化 =================
# 兼容 OpenAI 格式的 API（通义千问 / DeepSeek 等），通过环境变量配置
_llm_api_key = os.getenv("LLM_API_KEY", "")
_llm_base_url = os.getenv("LLM_BASE_URL", "")

# 配置缺失属于全局故障，必须在导入期暴露；否则每个文件都会静默降级成 PARSE_ERROR
if not _llm_api_key:
    raise RuntimeError("环境变量 LLM_API_KEY 未配置，extract 服务无法启动")
if not _llm_base_url.startswith(("http://", "https://")):
    raise RuntimeError(f"环境变量 LLM_BASE_URL 非法: {_llm_base_url!r}")

_model_name = os.getenv("LLM_MODEL", "qwen-plus")

# qwen3 系列默认开启"思考模式"，该模式下网关拒绝强制 function 调用
# （400: tool_choice does not support required/object in thinking mode），
# 而结构化输出必须强制 tool_choice，故 qwen3 默认关闭思考；
# 可用环境变量 LLM_ENABLE_THINKING=true/false 显式覆盖。
_extra_body: Dict[str, Any] = {}
_thinking_cfg = os.getenv("LLM_ENABLE_THINKING", "").strip().lower()
if _thinking_cfg in ("1", "true", "yes", "on"):
    _extra_body["enable_thinking"] = True
elif _thinking_cfg in ("0", "false", "no", "off"):
    _extra_body["enable_thinking"] = False
elif _model_name.lower().startswith("qwen3"):
    _extra_body["enable_thinking"] = False

llm = ChatOpenAI(
    model=_model_name,
    api_key=_llm_api_key,
    base_url=_llm_base_url,
    temperature=0,  # 尽量降低随机性；注意这不等于结果可复现
    request_timeout=90,  # 单次请求最长等待 90 秒，防止无限阻塞；
    # 最坏总耗时 = 阶段一90s + N文件×90s，需落在前端 axios 300s 超时之内
    extra_body=_extra_body or None,
)

# 绑定结构化输出。必须显式用 function_calling：ChatOpenAI 默认 method="json_schema"
# 走 OpenAI 专有的 Structured Outputs API，qwen 等兼容层不支持，会直接 400。
# 阶段一：输出"表计划"（几张表、每表分类名与行筛选条件）
_plan_llm = llm.with_structured_output(TablePlan, method="function_calling")


class _TableList(BaseModel):
    """阶段二结构化输出包装：一个文件的多张表。直接绑 List[ExtractedTable]
    在部分网关/function_calling 实现下不被接受，故包一层对象。"""
    tables: List[ExtractedTable] = Field(default_factory=list)


# 阶段二：按计划输出多张表
_extract_llm = llm.with_structured_output(_TableList, method="function_calling")


# ================= 阶段一：根据用户要求 + 模板结构，生成"填表计划" =================
# 关键约束：category 必须逐字抄录自模板描述段落——导出端靠"分类名 ⊆ 模板表上方描述文字"
# 的子串匹配来路由数据，模型自造/改写名称会导致匹配失败、三表填串。

_PLAN_SYSTEM = (
    "你是填表计划分析员。用户将提供【用户要求】和【模板结构】。\n"
    "模板中包含若干张表，每张表上方有一段描述文字。\n"
    "任务：\n"
    "1. 判断模板共有几张表、每张表应填什么数据。\n"
    "2. 每张表输出一条计划：\n"
    "   - category：从该表上方的描述文字中逐字抄录能标识该表的名称"
    "（如城市名），不得改写、缩略或自造；\n"
    "   - filters：从【用户要求】中提取该表的行筛选条件（如 城市、监测时间），"
    "值逐字抄录；用户要求未提及则输出空对象。\n"
    "3. 模板有几张表就输出几条，不得多也不得少。"
)


def _load_latest_template_text() -> Optional[str]:
    """从 UPLOAD_META 取最近上传的模板文件并解析为纯文本。无模板或解析失败返回 None。"""
    # 延迟导入避免循环依赖（upload_service 不依赖本模块，但保持单向依赖更清晰）
    from services.upload_service import UPLOAD_META, parse_file

    template_meta: Optional[Dict[str, Any]] = None
    for meta in UPLOAD_META.values():
        if meta.get("role") == "template":
            template_meta = meta  # 遍历取最后出现的，即最近上传
    if not template_meta:
        return None

    path = Path(template_meta["path"])
    if not path.exists():
        return None
    status, content, error = parse_file(path, template_meta["ext"])
    if status != "success":
        logging.warning("模板解析失败，阶段一降级: %s", error)
        return None
    return content


def _load_latest_target_headers() -> str:
    """从 UPLOAD_META 取最近上传的目标文件，解析并提取其真实表头行。
    表头行定义：首个含 " | " 且不以 "[" 开头的行（跳过 [工作表]/[表格N] 标记行）。
    无目标文件或解析失败时返回占位提示，绝不阻塞主流程。"""
    from services.upload_service import UPLOAD_META, parse_file

    target_meta: Optional[Dict[str, Any]] = None
    for meta in UPLOAD_META.values():
        if meta.get("role") == "target":
            target_meta = meta  # 遍历取最后出现的，即最近上传
    if not target_meta:
        return "未识别到表头"

    path = Path(target_meta["path"])
    if not path.exists():
        return "未识别到表头"

    status, content, error = parse_file(path, target_meta["ext"])
    if status != "success":
        logging.warning("目标文件解析失败，无法提取表头: %s", error)
        return "未识别到表头"

    for line in content.strip().split("\n"):
        if "|" in line and not line.strip().startswith("["):
            return line.strip()
    return "未识别到表头"


async def _build_table_plan(prompt: str) -> Tuple[List[TablePlanItem], str]:
    """
    阶段一：根据用户要求 + 模板结构生成填表计划，并同时提取目标文件的真实表头。
    任何失败（无模板 / 解析失败 / 模型异常）都退化为单条"默认分类"计划，
    保证阶段二行为等同旧逻辑，绝不阻塞主流程。
    返回: (填表计划, 目标文件表头行)
    """
    fallback = [TablePlanItem(category="默认分类", filters={})]

    target_headers = _load_latest_target_headers()

    template_text = _load_latest_template_text()
    if not template_text:
        logging.info("无可用模板，阶段一降级为默认分类")
        return fallback, target_headers

    try:
        plan: Optional[TablePlan] = await _plan_llm.ainvoke([
            SystemMessage(content=_PLAN_SYSTEM),
            HumanMessage(content=f"【用户要求】\n{prompt}\n\n【模板结构】\n{template_text}"),
        ])
        if plan is None or not plan.plans:
            raise ValueError("阶段一模型未返回有效计划")
        return plan.plans, target_headers
    except Exception as e:
        logging.exception("阶段一计划生成失败，降级为默认分类: %s", e)
        return fallback, target_headers


# ================= 日期范围预筛选 =================
# 在用户提示词中识别日期范围，喂给 LLM 前先按日期列筛掉范围外数据行，
# 既减少 token 消耗，也避免模型在超长表格中漏行。

# 支持格式：2020/7/1、2020-07-01、2020.7.1、2020年7月1日
_DATE_PATTERN = re.compile(r'(\d{4})\s*[年/\-.]\s*(\d{1,2})\s*[月/\-.]\s*(\d{1,2})\s*日?')


def _normalize_date(s: str) -> Optional[str]:
    """把 2020/7/1、2020-7-01、2020年7月1日 等写法归一化为 YYYY-MM-DD；无法识别返回 None。"""
    m = _DATE_PATTERN.search(s)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}"


def extract_date_range(prompt: str) -> Optional[Tuple[str, str]]:
    """从用户提示词中提取日期范围，返回 (start, end)（YYYY-MM-DD）。
    只识别到一个日期时视为单天查询；未识别到返回 None。"""
    dates = [d for d in (_normalize_date(m.group(0)) for m in _DATE_PATTERN.finditer(prompt)) if d]
    if len(dates) >= 2:
        start, end = dates[0], dates[1]
        return (start, end) if start <= end else (end, start)
    if len(dates) == 1:
        return dates[0], dates[0]
    return None


def filter_content_by_date(content: str, start_date: str, end_date: str) -> str:
    """
    按日期范围筛选数据行。
    content 可能以 "[工作表] xxx" 标记行开头，真实表头是首条含 " | " 的行。
    找不到日期列时原样返回，交给 AI 自行判断。
    start_date / end_date 格式：YYYY-MM-DD
    """
    lines = content.split("\n")
    if len(lines) < 2:
        return content

    # 1. 定位真实表头行（跳过 [工作表]/[表格N] 标记行和空行）
    header_idx = None
    for idx, line in enumerate(lines):
        if line.startswith("[") or not line.strip():
            continue
        if " | " in line:
            header_idx = idx
            break
    if header_idx is None:
        return content

    # 2. 模糊匹配日期列
    headers = [h.strip().lower() for h in lines[header_idx].split(" | ")]
    date_idx = -1
    for i, h in enumerate(headers):
        if any(k in h for k in ["日期", "date", "时间", "time"]):
            date_idx = i
            break

    # 3. 没找到日期列则原样返回，交给 AI 自行判断
    if date_idx == -1:
        return content

    # 4. 逐行比对日期（单元格日期先归一化为 YYYY-MM-DD 再做字符串比较）
    out = [lines[header_idx]]
    for line in lines[header_idx + 1:]:
        if not line.strip() or line.startswith("[") or " | " not in line:
            continue
        cells = line.split(" | ")
        if len(cells) > date_idx:
            d = _normalize_date(cells[date_idx].strip())
            if d and start_date <= d <= end_date:
                out.append(line)

    return "\n".join(out)


# ================= 分块提取配置 =================
# 旧方案"只喂前 N 行、其余丢弃"会导致 41 国数据只提取到前 4 国。
# 现方案：把大表切成多个小块分别请求、按原文顺序合并，保证全量覆盖。
#   EXTRACT_CHUNK_ROWS          每块最多行数（含表头，默认 100 → 每块 99 数据行）
#                               设小是为控制单次输出量：块越大模型要输出的分号段越多，
#                               越容易超过单次请求超时（旧值 200 时 186 行块频繁 90s 超时）。
#                               100 行恰好让每块按国家边界（每国约 62 行）成块，常量列对齐
#                               最干净，几乎不再触发劈半重取，反而更省钱。
#   EXTRACT_CHUNK_CONCURRENCY   单文件分块并发请求数（默认 8；被网关限流可调小）
#   EXTRACT_MAX_CONTENT_LENGTH  单块字符上限（默认 60000），与请求超时匹配
CHUNK_ROWS = int(os.getenv("EXTRACT_CHUNK_ROWS", os.getenv("EXTRACT_MAX_DATA_ROWS", "100")))
CHUNK_CONCURRENCY = int(os.getenv("EXTRACT_CHUNK_CONCURRENCY", "8"))
MAX_CONTENT_LENGTH = int(os.getenv("EXTRACT_MAX_CONTENT_LENGTH", "60000"))
# 块结果对位率：用源块中与字段同名的列（如"国家/地区"）逐行校验模型输出，
# 低于阈值判定模型漏行/串行，自动沿国家边界劈半重取（最多两级）。
# 0.995：186 行的块错 1 行（99.46%）即触发修复
CHUNK_MIN_SCORE = float(os.getenv("EXTRACT_CHUNK_MIN_SCORE", "0.995"))
REPAIR_MAX_DEPTH = 2
REPAIR_MIN_ROWS = 20


def prune_columns(content: str, fields: List[str]) -> str:
    """
    列裁剪：只保留表头中与用户字段精确同名的列，删掉其余列。
    源表常有十几列而用户只要几个字段，未裁剪会把大量无关列喂给模型，
    显著增加输入 token 与耗时。裁剪在分块前进行，对散文（无表格行）原样返回。
    """
    if not fields:
        return content
    lines = content.split("\n")
    out: List[str] = []
    # None=尚未遇到表头；非空 list=要保留的列下标；[]=该节表头无匹配列，整节原样保留
    keep_cols: Optional[List[int]] = None
    for line in lines:
        is_marker = line.startswith("[")
        is_tabular = bool(line.strip()) and not is_marker and " | " in line
        if is_marker:
            keep_cols = None  # 新 sheet，重新识别表头
            out.append(line)
            continue
        if not is_tabular:
            out.append(line)
            continue
        cells = line.split(" | ")
        if keep_cols is None:
            # 首个表格行视为表头：定位与字段同名的列下标
            keep_cols = [i for i, c in enumerate(cells) if c.strip() in fields]
            if not keep_cols:
                # 表头与字段无交集（可能非目标表）：整节原样保留，避免误删
                out.append(line)
                continue
            out.append(" | ".join(cells[i] for i in keep_cols))
            continue
        if not keep_cols:
            # 该节无匹配列，数据行也原样保留
            out.append(line)
            continue
        # 数据行：按已定位的列下标取值，越界补空
        out.append(" | ".join(
            cells[i] if i < len(cells) else "" for i in keep_cols
        ))
    return "\n".join(out)


def split_into_chunks(content: str) -> List[Dict[str, Any]]:
    """
    把解析后的文档切成 LLM 请求块。
    - 结构化文本（含 " | " 表格行，兼容多 sheet）：按 [工作表] 标记分节，
      每节首个表格行识别为表头，数据行按 行数+字符数 双约束贪心切批；
      每块自带节标记与表头，模型可独立定位列。块的 n_rows=数据行数（>=1）。
    - 散文文本（docx 叙述文等，全文无表格行）：整体一块，n_rows=None，
      不做段数归一化（散文提取出的条目数本就不固定）。
    """
    lines = content.split("\n")

    # 1. 按 [工作表] 标记把行组织成 (preamble, header, data_rows) 节
    sections: List[Tuple[List[str], Optional[str], List[str]]] = []
    preamble: List[str] = []
    header: Optional[str] = None
    data_rows: List[str] = []
    seen_tabular = False
    for line in lines:
        is_marker = line.startswith("[")
        is_tabular = bool(line.strip()) and not is_marker and " | " in line
        if is_marker and seen_tabular:
            # 新 sheet 标记出现：落盘上一节，开启新节
            sections.append((preamble, header, data_rows))
            preamble, header, data_rows = [line], None, []
            seen_tabular = False
        elif is_marker:
            preamble.append(line)
        elif is_tabular and not seen_tabular:
            header = line
            seen_tabular = True
        elif is_tabular:
            data_rows.append(line)
        elif not seen_tabular:
            preamble.append(line)
        # 表头之后的空行/散行直接丢弃（解析器正常不产生）
    sections.append((preamble, header, data_rows))

    has_tabular = any(
        sec_header is not None or any(" | " in r for r in sec_rows)
        for _, sec_header, sec_rows in sections
    )
    if not has_tabular:
        return [{"kind": "prose", "text": content, "n_rows": None}]

    # 2. 每节内先按"首列值连续段(run)"分组（如同一国家的连续多行不被切断），
    #    再在 行数 + 字符数 双约束下贪心装块。块沿语义边界切开能显著降低
    #    模型漏行/串行后按位置对齐时的错位风险。
    chunks: List[Dict[str, Any]] = []
    max_data_rows = max(CHUNK_ROWS - 1, 1)
    for sec_preamble, sec_header, sec_rows in sections:
        rows = [r for r in sec_rows if " | " in r]
        base = sec_preamble + ([sec_header] if sec_header else [])
        overhead = len("\n".join(base)) + 1

        runs: List[List[str]] = []
        run: List[str] = []
        run_key: Optional[str] = None
        for row in rows:
            key = row.split(" | ", 1)[0].strip()
            if run and key != run_key:
                runs.append(run)
                run = []
            run_key = key
            run.append(row)
        if run:
            runs.append(run)

        def flush(batch_rows: List[str]) -> None:
            if batch_rows:
                chunks.append({"kind": "table", "preamble": base,
                               "rows": batch_rows, "n_rows": len(batch_rows)})

        batch: List[str] = []
        used = overhead
        for grp in runs:
            # 单个 run 本身超限（如一个国家行数极多）：先把已装的块落盘，
            # 再对该 run 按容量硬切
            grp_chars = sum(len(r) + 1 for r in grp)
            if len(grp) > max_data_rows or overhead + grp_chars > MAX_CONTENT_LENGTH:
                flush(batch)
                batch, used = [], overhead
                sub: List[str] = []
                sub_used = overhead
                for row in grp:
                    add_len = len(row) + 1
                    if sub and (len(sub) >= max_data_rows or sub_used + add_len > MAX_CONTENT_LENGTH):
                        flush(sub)
                        sub, sub_used = [], overhead
                    if add_len > MAX_CONTENT_LENGTH:
                        logging.warning("单行超过字符上限(%d)，已硬截断该行", MAX_CONTENT_LENGTH)
                        row = row[:MAX_CONTENT_LENGTH]
                        add_len = len(row) + 1
                    sub.append(row)
                    sub_used += add_len
                flush(sub)
                sub = []
                continue

            add_len = sum(len(r) + 1 for r in grp)
            if batch and (len(batch) + len(grp) > max_data_rows or used + add_len > MAX_CONTENT_LENGTH):
                flush(batch)
                batch, used = [], overhead
            batch.extend(grp)
            used += add_len
        flush(batch)
    return chunks


# ================= 阶段二：按计划逐表提取 =================

_EXTRACT_SYSTEM = (
    "你是一个严谨的文档信息提取专家，严格基于【文档内容】提取，绝不动用外部知识。\n"
    "本次按“逐表提取”方式进行：用户给出【表计划】，每条含 category 与 filters。\n"
    "1. 对计划中每一条，从文档内容中筛出满足其 filters 的数据行，输出一个表。\n"
    "2. table_category 必须逐字抄录该条的 category，不得修改。\n"
    "3. records 的键必须与用户指定的 fields 完全一致，不得增删改。\n"
    "4. 铁律：文档中未明确提及的字段值输出“未找到”，不许推测捏造。\n"
    "5. 筛到多行时：每个字段把各行取值按原文行序用英文分号“;”拼接，"
    "且所有字段拼出的段数必须相等；某行该列缺失记“未找到”。\n"
    "6. 一行都没筛到：该表所有字段输出“未找到”。"
)

# 分块模式追加的硬约束
_CHUNK_EXTRACT_SYSTEM = _EXTRACT_SYSTEM + (
    "\n7.【分块提取】本次输入只是全文分块后的一块，只输出本块内的数据行，"
    "严禁补充块外数据。\n"
    "8. 每个字段分号拼接值的段数必须恰好等于告知的本块数据行数 N；"
    "即使某列在块内每行取值相同（如国家、大洲、人口），也必须逐行重复 N 次，"
    "严禁只给一个汇总值。"
)

# 散文文档（无表格行）兜底重试所用提示词，沿用旧逻辑
_PROSE_FALLBACK_SYSTEM = (
    "你是一个严谨的文档信息提取专家。请忽略【表计划】，"
    "直接将【文档内容】中的所有数据行提取出来，"
    "严格对照【目标文档的真实表头】来定位列数据。\n"
    "1. table_category 固定为“默认表”。\n"
    "2. records 的键必须与用户指定的字段完全一致，不得增删改。\n"
    "3. 文档中未明确提及的字段值输出“未找到”，不许推测捏造。"
)


def _chunk_text(chunk: Dict[str, Any]) -> str:
    return "\n".join(chunk["preamble"] + chunk["rows"])


def _normalize_tables(
    tables: List[ExtractedTable], fields: List[str], n_rows: int
) -> List[ExtractedTable]:
    """
    把单块模型输出按"该块数据行数 n_rows"做字段级归一化：
    - 统一按中英文分号切段；
    - 模型只回 1 段而块内多行时，视为常量列广播到 n_rows（如国家、人均GDP）；
    - 段数不足补"未找到"、超出截断，保证同块各字段段数一致、跨块可直接拼接。
    """
    out: List[ExtractedTable] = []
    for t in tables:
        records: Dict[str, str] = {}
        for f in fields:
            raw = str(t.records.get(f, "")).strip()
            segs = [s.strip() for s in re.split(r"[;；]", raw)] if raw else []
            segs = [s if s else "未找到" for s in segs]
            if len(segs) == 1 and n_rows > 1:
                segs = segs * n_rows  # 常量列广播
            elif len(segs) < n_rows:
                segs += ["未找到"] * (n_rows - len(segs))
            elif len(segs) > n_rows:
                logging.warning(
                    "块表「%s」字段「%s」返回%d段，超过块行数%d已截断",
                    t.table_category, f, len(segs), n_rows,
                )
                segs = segs[:n_rows]
            records[f] = ";".join(segs)
        out.append(ExtractedTable(table_category=t.table_category, records=records))
    return out


def _merge_chunk_tables(
    per_chunk: List[List[ExtractedTable]], fields: List[str]
) -> List[ExtractedTable]:
    """按块顺序、按 table_category 拼接各字段分号串，分类顺序以首次出现为准。"""
    order: List[str] = []
    buckets: Dict[str, Dict[str, List[str]]] = {}
    for tables in per_chunk:
        for t in tables:
            if t.table_category not in buckets:
                buckets[t.table_category] = {f: [] for f in fields}
                order.append(t.table_category)
            for f in fields:
                buckets[t.table_category][f].append(t.records.get(f, "未找到"))
    return [
        ExtractedTable(
            table_category=cat,
            records={f: ";".join(buckets[cat][f]) for f in fields},
        )
        for cat in order
    ]


def _placeholder_tables(n_rows: int, fields: List[str], category: str) -> List[ExtractedTable]:
    """整块/半块彻底失败时的占位：每个字段补 n_rows 个"未找到"，保证段数对齐。"""
    return [ExtractedTable(
        table_category=category,
        records={f: ";".join(["未找到"] * n_rows) for f in fields},
    )]


def _chunk_constant_columns(chunk: Dict[str, Any]) -> Dict[str, str]:
    """找出块内取值全相同的表头列（如按国家切块后的国家/大洲/人均GDP）。
    返回 {列名: 唯一值}。这些列无需模型输出，由代码直接从源数据填充：
    零 token、零耗时、100% 准确，同时大幅缩短单次请求时间、降低超时概率。"""
    rows = chunk.get("rows") or []
    header_line: Optional[str] = None
    for line in reversed(chunk.get("preamble", [])):
        if " | " in line:
            header_line = line
            break
    if header_line is None or not rows:
        return {}
    headers = [h.strip() for h in header_line.split(" | ")]
    const: Dict[str, str] = {}
    for i, name in enumerate(headers):
        vals = set()
        for r in rows:
            cells = r.split(" | ")
            vals.add(cells[i].strip() if i < len(cells) else "")
        if len(vals) == 1:
            const[name] = next(iter(vals))
    return const


def _prune_chunk_to_columns(chunk: Dict[str, Any], keep_names: List[str]) -> Dict[str, Any]:
    """只保留指定表头列生成新块（喂给模型的内容只含动态列，进一步压缩输入）。"""
    header_line = next(
        (l for l in reversed(chunk.get("preamble", [])) if " | " in l), None
    )
    if header_line is None or not keep_names:
        return chunk
    headers = [h.strip() for h in header_line.split(" | ")]
    keep_idx = [i for i, h in enumerate(headers) if h in keep_names]
    if not keep_idx:
        return chunk
    def pick(line: str) -> str:
        cells = line.split(" | ")
        return " | ".join(cells[i] if i < len(cells) else "" for i in keep_idx)
    preamble = [pick(l) if " | " in l and not l.startswith("[") else l
                for l in chunk.get("preamble", [])]
    return {**chunk, "preamble": preamble,
            "rows": [pick(r) for r in chunk.get("rows", [])]}


def _constant_records(const: Dict[str, str], fields: List[str], n_rows: int) -> Dict[str, str]:
    """常量列记录：唯一值广播为 n_rows 段（空值记"未找到"）。"""
    rec: Dict[str, str] = {}
    for f in fields:
        if f in const:
            v = const[f] if const[f] else "未找到"
            rec[f] = ";".join([v] * n_rows)
    return rec


async def _invoke_chunk(
    sem: asyncio.Semaphore, idx: int, total: int, chunk: Dict[str, Any],
    base_human: str, source_file: str, out_fields: Optional[List[str]] = None
) -> Tuple[bool, Any]:
    """发起单个结构化块请求。成功返回 (True, List[ExtractedTable]_raw)，失败 (False, 异常)。
    out_fields 指定模型需要输出的字段（常量列已被代码直填，不必输出）。
    超时类错误先原块重试一次：小块超时的根因多为网关抖动而非块过大，
    原块重试比直接劈半更省（劈半会把同一份数据请求两次）。"""
    n_rows = chunk["n_rows"]
    of = out_fields if out_fields else None
    extra = (
        f"本次只需输出以下字段：{', '.join(of)}；其余字段无需输出。\n" if of else ""
    )
    human = (
        f"{base_human}"
        f"【本块信息】第 {idx}/{total} 块。文档内容中表头行（列名行）不计入数据行，"
        f"禁止把列名作为值输出；表头之后共有 N={n_rows} 个数据行，"
        f"每个字段输出的分号段数必须恰好等于 {n_rows}，且与数据行一一对应、顺序不得变动。\n"
        f"{extra}"
        f"文档内容：\n{_chunk_text(chunk)}"
    )
    async with sem:
        for attempt in (1, 2):
            try:
                result: Optional[_TableList] = await _extract_llm.ainvoke([
                    SystemMessage(content=_CHUNK_EXTRACT_SYSTEM),
                    HumanMessage(content=human),
                ])
                if result is None or not result.tables:
                    raise ValueError("模型未返回有效的结构化数据")
                return True, result.tables
            except Exception as e:
                is_timeout = "Timeout" in type(e).__name__
                if is_timeout and attempt == 1:
                    logging.warning(
                        "文件 %s 块 %d/%d (n=%d) 首次请求超时，原块重试一次",
                        source_file, idx, total, n_rows,
                    )
                    continue
                logging.warning(
                    "文件 %s 块 %d/%d (n=%d) 提取失败[%s]: %s",
                    source_file, idx, total, n_rows, type(e).__name__, e,
                )
                return False, e
    return False, RuntimeError("unreachable")


def _chunk_check_columns(
    chunk: Dict[str, Any], fields: List[str]
) -> List[Tuple[str, int, bool]]:
    """找出块表头中与用户字段精确同名的源列，作为逐行对位校验列。
    返回 [(字段名, 源列下标, 是否数值列)]；数值列按数值比对（容差千分位），
    其余按规范化文本（去空白、忽略大小写）比对。只精确同名，避免近义列误判。"""
    header_line: Optional[str] = None
    for line in reversed(chunk["preamble"]):
        if " | " in line:
            header_line = line
            break
    if header_line is None:
        return []
    headers = [h.strip() for h in header_line.split(" | ")]
    checks: List[Tuple[str, int, bool]] = []
    for f in fields:
        if f not in headers:
            continue
        col = headers.index(f)
        col_vals = []
        for r in chunk["rows"]:
            cells = r.split(" | ")
            if col < len(cells) and cells[col].strip():
                col_vals.append(cells[col].strip())
        numeric_hits = sum(1 for v in col_vals if re.match(r"^-?\d+(\.\d+)?$", v.replace(",", "")))
        is_numeric = bool(col_vals) and numeric_hits / len(col_vals) >= 0.8
        checks.append((f, col, is_numeric))
    return checks


def _cells_match(src: str, got: str, is_numeric: bool) -> bool:
    s, g = src.strip(), got.strip()
    if is_numeric:
        ms = re.match(r"^-?\d+(?:\.\d+)?", s.replace(",", ""))
        mg = re.match(r"^-?\d+(?:\.\d+)?", g.replace(",", ""))
        if ms and mg:
            return abs(float(ms.group(0)) - float(mg.group(0))) < 1e-6
        if not s:
            return g in ("未找到", "", "-", "—")
        return s.replace(",", "") == g.replace(",", "")
    return s.lower() == g.lower()


def _validate_chunk(
    chunk: Dict[str, Any], tables: List[ExtractedTable],
    checks: List[Tuple[str, int, bool]]
) -> float:
    """对位率 [0,1]：各校验列逐行命中率的最小值（最弱列决定是否修复）。
    某字段段数与块行数不一致直接判 0；无校验列时返回 1.0（无法机器校验）。"""
    if not checks or not tables:
        return 1.0 if not checks else 0.0
    if not chunk["rows"]:
        return 1.0
    scores: List[float] = []
    for field, col, is_numeric in checks:
        expected = []
        for r in chunk["rows"]:
            cells = r.split(" | ")
            expected.append(cells[col].strip() if col < len(cells) else "")
        # 找到含该字段的首条模型表记录
        raw = next((t.records.get(field) for t in tables if field in t.records), None)
        if raw is None:
            return 0.0
        got = [x.strip() for x in re.split(r"[;；]", str(raw))]
        if len(got) != len(expected):
            return 0.0
        hit = sum(1 for a, b in zip(expected, got) if _cells_match(a, b, is_numeric))
        scores.append(hit / len(expected))
    return min(scores)


def _split_chunk_at_run(chunk: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """把块劈成两半，切点尽量落在首列值变化处（国家边界），避免切开同一序列。"""
    rows = chunk["rows"]
    n = len(rows)
    keys = [r.split(" | ", 1)[0].strip() for r in rows]
    cut = n // 2
    for d in range(n // 2):
        found: Optional[int] = None
        for cand in (n // 2 - d, n // 2 + d):
            if 0 < cand < n and keys[cand] != keys[cand - 1]:
                found = cand
                break
        if found is not None:
            cut = found
            break
    left = {**chunk, "rows": rows[:cut], "n_rows": cut}
    right = {**chunk, "rows": rows[cut:], "n_rows": n - cut}
    return left, right


async def _run_table_chunk(
    sem: asyncio.Semaphore, idx: int, total: int, chunk: Dict[str, Any],
    base_human: str, source_file: str, fields: List[str], default_cat: str,
    depth: int = 0,
) -> Optional[List[ExtractedTable]]:
    """
    执行一个结构化块并保证结果可信：
    1) 请求失败（超时等）：劈半各重试一次，两半均失败返回 None（系统级故障信号）；
    2) 请求成功但对位率低于 CHUNK_MIN_SCORE（模型漏行/串行导致按位置错位）：
       沿国家边界劈半重取，递归深度最多 REPAIR_MAX_DEPTH；小块/达深度后保留最佳努力结果；
    3) 半块请求失败时该半块按行数补"未找到"占位，不影响其余行。
    """
    n_rows = chunk["n_rows"]

    # 常量列（块内取值全相同，如按国家切块后的国家/大洲/人均GDP）直接取自源数据：
    # 零 token、零耗时、100% 准确；模型只需输出取值逐行变化的动态列，
    # 单次输出量大减，既省钱又显著降低超时概率。
    const = _chunk_constant_columns(chunk)
    const_fields = [f for f in fields if f in const]
    dyn_fields = [f for f in fields if f not in const]
    const_records = _constant_records(const, fields, n_rows)

    if not dyn_fields:
        # 块内所有目标字段都是常量：无需调用模型
        return [ExtractedTable(table_category=default_cat, records=const_records)]

    model_chunk = _prune_chunk_to_columns(chunk, dyn_fields)
    ok, payload = await _invoke_chunk(
        sem, idx, total, model_chunk, base_human, source_file, dyn_fields
    )

    need_repair = False
    if ok:
        tables = _normalize_tables(payload, dyn_fields, n_rows)
        checks = _chunk_check_columns(model_chunk, dyn_fields)
        if checks and n_rows >= REPAIR_MIN_ROWS and depth < REPAIR_MAX_DEPTH:
            score = _validate_chunk(model_chunk, tables, checks)
            if score < CHUNK_MIN_SCORE:
                logging.warning(
                    "文件 %s 块 %d/%d 对位率 %.1f%%（约%d行不匹配，校验列:%s），劈半重取修复(depth=%d)",
                    source_file, idx, total, score * 100,
                    round((1 - score) * n_rows), [c[0] for c in checks], depth,
                )
                need_repair = True
        if not need_repair:
            # 常量列直填值并入模型输出，还原为完整字段集
            for t in tables:
                t.records.update(const_records)
            return tables
    else:
        if n_rows <= 1 or depth >= REPAIR_MAX_DEPTH:
            return None
        need_repair = True  # 请求失败且仍可下钻：劈半重试

    left, right = _split_chunk_at_run(chunk)
    left_res, right_res = await asyncio.gather(
        _run_table_chunk(sem, idx, total, left, base_human, source_file,
                         fields, default_cat, depth + 1),
        _run_table_chunk(sem, idx, total, right, base_human, source_file,
                         fields, default_cat, depth + 1),
    )
    if left_res is None and right_res is None:
        return None

    merged: List[ExtractedTable] = []
    failed_rows = 0
    for half, res in ((left, left_res), (right, right_res)):
        if res is None:
            merged.extend(_placeholder_tables(half["n_rows"], fields, default_cat))
            failed_rows += half["n_rows"]
        else:
            merged.extend(res)
    if failed_rows:
        logging.warning(
            "文件 %s 块 %d/%d 修复后仍有 %d 行请求失败，已占位",
            source_file, idx, total, failed_rows,
        )
    return merged


async def _run_prose_chunk(
    chunk: Dict[str, Any], base_human: str, source_file: str, fields: List[str]
) -> List[ExtractedTable]:
    """散文文档：单块请求，沿用旧的"忽略计划再试一次"兜底；最终失败给 PARSE_ERROR。"""
    text = chunk["text"]
    if len(text) > MAX_CONTENT_LENGTH:
        logging.warning("文件 %s 散文内容过长(%d字符)，截断至%d字符",
                        source_file, len(text), MAX_CONTENT_LENGTH)
        text = text[:MAX_CONTENT_LENGTH]
    human = f"{base_human}文档内容：\n{text}"

    try:
        result: Optional[_TableList] = await _extract_llm.ainvoke([
            SystemMessage(content=_EXTRACT_SYSTEM),
            HumanMessage(content=human),
        ])
        if result is None or not result.tables:
            raise ValueError("模型未能返回有效的结构化数据")
        return result.tables
    except Exception as e:
        logging.exception(f"文件 {source_file} 散文提取异常: {str(e)}")
        try:
            fallback: Optional[_TableList] = await _extract_llm.ainvoke([
                SystemMessage(content=_PROSE_FALLBACK_SYSTEM),
                HumanMessage(content=human),
            ])
            if fallback is None or not fallback.tables:
                raise ValueError("兜底提取依然失败")
            logging.info("文件 %s 兜底提取成功，共 %d 张表", source_file, len(fallback.tables))
            return fallback.tables
        except Exception as fallback_e:
            logging.exception(f"文件 {source_file} 兜底提取失败: {fallback_e}")
            return [ExtractedTable(
                table_category="解析异常",
                records={field: "PARSE_ERROR" for field in fields},
            )]


async def extract_info_via_ai(
    prompt: str, fields: List[str], documents: List[Dict[str, Any]]
) -> List[ExtractResponseItem]:
    """
    调用大模型按指定字段从文档中提取结构化信息。
    两阶段：先按用户要求+模板生成填表计划；
    再把每个文档切分为多个数据块并发提取（超时块劈半重试一次），
    最后按块顺序合并为整文件结果，保证大表全量覆盖、不丢数据。
    """
    final_results: List[ExtractResponseItem] = []

    # 阶段一：整批请求共享一份计划（模板与用户要求在一次请求内不变）
    plan_items, target_headers = await _build_table_plan(prompt)
    logging.info("填表计划: %s", [(p.category, p.filters) for p in plan_items])
    plan_text = json.dumps(
        [{"category": p.category, "filters": p.filters} for p in plan_items],
        ensure_ascii=False,
    )
    default_cat = plan_items[0].category if plan_items else "默认分类"

    # 从提示词中提取日期范围，用于在分块前预筛选数据行
    date_range = extract_date_range(prompt)
    if date_range:
        logging.info("检测到日期范围筛选: %s ~ %s", date_range[0], date_range[1])

    # 各块共享的提示词前缀（文档内容随块追加）
    base_human = (
        f"用户提示词：{prompt}\n"
        f"需要提取的字段：{', '.join(fields)}\n"
        f"【目标文档的真实表头（定位列的依据）】\n{target_headers}\n"
        f"【表计划】\n{plan_text}\n"
    )

    for doc in documents:
        source_file = doc.get("filename", "unknown")
        doc_content = doc.get("content", json.dumps(doc, ensure_ascii=False))

        # 提示词中含日期范围时，先按日期列预筛选，减少分块数量与 token 消耗
        if date_range:
            doc_content = filter_content_by_date(doc_content, date_range[0], date_range[1])
            logging.info("文件 %s 日期筛选后内容长度: %d 字符", source_file, len(doc_content))

        # 只保留用户要填的字段同名列，删掉无关列，大幅减少输入 token
        # （必须在日期筛选之后：筛选依赖日期列，而日期列通常不在 fields 中）
        before = len(doc_content)
        doc_content = prune_columns(doc_content, fields)
        if len(doc_content) < before:
            logging.info(
                "文件 %s 列裁剪: %d -> %d 字符（节省 %.0f%%）",
                source_file, before, len(doc_content), (1 - len(doc_content) / before) * 100,
            )

        chunks = split_into_chunks(doc_content)

        if len(chunks) == 1 and chunks[0]["kind"] == "prose":
            # 散文文档：条目数不固定，单块提取不做段数约束
            extracted_tables = await _run_prose_chunk(chunks[0], base_human, source_file, fields)
        else:
            total = len(chunks)
            total_rows = sum(c["n_rows"] for c in chunks)
            logging.info(
                "文件 %s 切分为 %d 个数据块（共%d行），并发=%d",
                source_file, total, total_rows, CHUNK_CONCURRENCY,
            )
            sem = asyncio.Semaphore(CHUNK_CONCURRENCY)
            chunk_results = await asyncio.gather(*[
                _run_table_chunk(
                    sem, i + 1, total, chunk, base_human, source_file, fields, default_cat
                )
                for i, chunk in enumerate(chunks)
            ])

            failed = [c for c, r in zip(chunks, chunk_results) if r is None]
            if len(failed) == total:
                # 全部块失败属于系统性故障（鉴权/额度/网关宕机），不得伪装成"未找到"
                logging.error("文件 %s 全部 %d 个块提取失败，返回 PARSE_ERROR", source_file, total)
                extracted_tables = [ExtractedTable(
                    table_category="解析异常",
                    records={field: "PARSE_ERROR" for field in fields},
                )]
            else:
                per_chunk: List[List[ExtractedTable]] = []
                for chunk, result in zip(chunks, chunk_results):
                    if result is None:
                        per_chunk.append(
                            _placeholder_tables(chunk["n_rows"], fields, default_cat)
                        )
                    else:
                        per_chunk.append(result)
                extracted_tables = _merge_chunk_tables(per_chunk, fields)
                if failed:
                    failed_rows = sum(c["n_rows"] for c in failed)
                    logging.warning(
                        "文件 %s 有 %d/%d 块（%d行）彻底失败，已以未找到占位合并",
                        source_file, len(failed), total, failed_rows,
                    )
                logging.info(
                    "文件 %s 分块合并完成，共 %d 张表: %s",
                    source_file, len(extracted_tables),
                    [t.table_category for t in extracted_tables],
                )

        final_results.append(ExtractResponseItem(
            source_file=source_file,
            extracted_tables=extracted_tables,
        ))

    return final_results
