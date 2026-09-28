import os
import json
import logging

from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from models.schemas import ExtractedTable, ExtractResponseItem, RecordItem

# ================= 大模型初始化 =================
# 兼容 OpenAI 格式的 API（通义千问 / DeepSeek 等），通过环境变量配置
_llm_api_key = os.getenv("LLM_API_KEY", "")
_llm_base_url = os.getenv("LLM_BASE_URL", "")

# 配置缺失属于全局故障，必须在导入期暴露；否则每个文件都会静默降级成 PARSE_ERROR
if not _llm_api_key:
    raise RuntimeError("环境变量 LLM_API_KEY 未配置，extract 服务无法启动")
if not _llm_base_url.startswith(("http://", "https://")):
    raise RuntimeError(f"环境变量 LLM_BASE_URL 非法: {_llm_base_url!r}")

llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "qwen-plus"),
    api_key=_llm_api_key,
    base_url=_llm_base_url,
    temperature=0,  # 尽量降低随机性；注意这不等于结果可复现
)

# 绑定结构化输出，让大模型直接输出 ExtractedTable 强校验对象
# 必须显式用 function_calling：ChatOpenAI 默认 method="json_schema" 走 OpenAI 专有的
# Structured Outputs API，qwen 等兼容层不支持，会直接 400
structured_llm = llm.with_structured_output(ExtractedTable, method="function_calling")


async def extract_info_via_ai(
    prompt: str, fields: List[str], documents: List[Dict[str, Any]]
) -> List[ExtractResponseItem]:
    """
    调用大模型按指定字段从文档中提取结构化信息。
    这里将按文件循环调用大模型并处理 PARSE_ERROR。
    """
    final_results: List[ExtractResponseItem] = []

    # 核心数据隔离：按文件遍历，每次针对单个文档发起调用
    for doc in documents:
        source_file = doc.get("filename", "unknown")
        doc_content = doc.get("content", json.dumps(doc, ensure_ascii=False))

        # ---------------- 提示词组装 ----------------
        system_content = (
    "你是一个严谨的文档信息提取专家。你的任务是严格基于提供的【文档内容】进行信息提取，绝不能动用任何外部知识。\n"
    "1. 分类：根据用户的 prompt 逻辑判断文档所属的分类（table_category）。若用户的 prompt 未提供分类依据，请固定输出'默认分类'。\n"
    "2. 提取：从文档中提取用户指定的 fields 字段，直接以键值对的形式存入 records 字典中。注意：records 的键必须与用户指定的 fields 完全一致，绝不允许修改键名、遗漏字段或擅自增加字段。\n"
    "3. 铁律：如果文档原文中没有明确提及某字段的信息，该字段对应的值必须严格输出'未找到'，绝不允许推测或捏造。\n"
    "请严格按照 ExtractedTable 结构输出：table_category 为分类名称，records 为包含所有提取字段的键值对字典。"
)

        human_content = (
            f"用户提示词：{prompt}\n"
            f"需要提取的字段：{', '.join(fields)}\n"
            f"文档内容：\n{doc_content}"
        )

        # ---------------- 边界异常兜底 ----------------
        try:
            extracted_table: ExtractedTable = await structured_llm.ainvoke([
                SystemMessage(content=system_content),
                HumanMessage(content=human_content),
            ])
            
    # 【新增防御】部分大模型在完全无法按照格式输出时，会静默返回 None
            if extracted_table is None:
                raise ValueError("模型未能返回有效的结构化数据")

        except Exception as e:
    # 【修改点 1：破除致盲】必须把真实的错误原因打印在后端控制台！
            logging.exception(f"文件 {source_file} 提取异常: {str(e)}")
    
    # 超时、JSON 解析失败或其他任何异常
    # 手动构造 ExtractedTable，保证该文件不会阻塞整个任务
    
    # 【修改点 2：结构对齐】把原先复杂的 RecordItem 列表推导式，改为简单的字典推导式
            error_records = {field: "PARSE_ERROR" for field in fields}
    
            extracted_table = ExtractedTable(
                table_category="解析异常",
                records=error_records,
            )
        # ---------------- 结果聚合 ----------------
        final_results.append(ExtractResponseItem(
            source_file=source_file,
            extracted_tables=[extracted_table],
        ))

    return final_results
