import os
import re
from typing import Any, Dict, List, Optional, Tuple

from neo4j import GraphDatabase
from langchain_openai import ChatOpenAI


# =========================
# 1) 基础配置
# =========================
# 建议把密钥放到环境变量里：
#   DASHSCOPE_API_KEY
#   NEO4J_URI
#   NEO4J_USER
#   NEO4J_PASSWORD
DASHSCOPE_API_KEY = "sk-648d3fd76f2e464d9b037c82d17df2dc"
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")

if not DASHSCOPE_API_KEY:
    raise ValueError("请先设置环境变量 DASHSCOPE_API_KEY")


llm = ChatOpenAI(
    model="deepseek-v4-flash",
    openai_api_key=DASHSCOPE_API_KEY,
    openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
    temperature=0.2,
)


driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD),
)


# =========================
# 2) 图谱结构说明（给模型看）
# =========================
GRAPH_SCHEMA = """
图数据库节点：
- (:Product {name, unit, boundary, tech, source})
- (:Region {name})
- (:Year {value})
- (:Stage {name})

图数据库关系：
- (p:Product)-[:LOCATED_IN]->(r:Region)
- (p:Product)-[:HAS_YEAR]->(y:Year)
- (p:Product)-[rel:HAS_STAGE {emission}]->(s:Stage)

说明：
- emission 存在 HAS_STAGE 关系属性上
- Product 节点保存产品本身的元信息
- Region / Year / Stage 是独立节点
"""


# =========================
# 3) 通用图数据库执行函数
# =========================
def run_cypher(query: str, parameters: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict[str, Any]], str]:
    """执行 Cypher，返回记录列表和错误信息。"""
    parameters = parameters or {}
    try:
        with driver.session() as session:
            result = session.run(query, parameters)
            records = [record.data() for record in result]
        return records, ""
    except Exception as e:
        return [], f"Cypher执行错误: {e}"


def format_records(records: List[Dict[str, Any]]) -> str:
    if not records:
        return "未找到数据"
    lines = []
    for row in records:
        parts = []
        for k, v in row.items():
            parts.append(f"{k}: {v}")
        lines.append(", ".join(parts))
    return "\n".join(lines)


# =========================
# 4) Text2API：常用功能函数
# =========================
def get_product_info(product_name: str) -> str:
    print(f"\n[API] get_product_info(product={product_name})")

    query = """
    MATCH (p:Product {name:$name})
    OPTIONAL MATCH (p)-[:LOCATED_IN]->(r:Region)
    OPTIONAL MATCH (p)-[:HAS_YEAR]->(y:Year)
    RETURN
        p.name AS product,
        p.unit AS unit,
        p.boundary AS boundary,
        p.tech AS tech,
        p.source AS source,
        r.name AS region,
        y.value AS year
    LIMIT 1
    """

    print("\n[Cypher Query]")
    print(query)

    print("\n[Parameters]")
    print({"name": product_name})

    records, err = run_cypher(query, {"name": product_name})

    if err:
        return err

    return format_records(records)

def get_stage_emission(product_name: str, stage_name: str) -> str:
    print(f"\n[API] get_stage_emission(product={product_name}, stage={stage_name})")

    query = """
    MATCH (p:Product {name:$product})-[rel:HAS_STAGE]->(s:Stage {name:$stage})
    RETURN p.name AS product, s.name AS stage, rel.emission AS emission
    LIMIT 1
    """

    print("\n[Cypher Query]")
    print(query)

    print("\n[Parameters]")
    print({
        "product": product_name,
        "stage": stage_name
    })

    records, err = run_cypher(
        query,
        {
            "product": product_name,
            "stage": stage_name
        }
    )

    if err:
        return err

    return format_records(records)

def get_total_emission(product_name: str) -> str:
    print(f"\n[API] get_total_emission(product={product_name})")

    query = """
    MATCH (p:Product {name:$product})-[rel:HAS_STAGE]->(:Stage)
    RETURN p.name AS product,
           sum(rel.emission) AS total_emission
    LIMIT 1
    """

    print("\n[Cypher Query]")
    print(query)

    print("\n[Parameters]")
    print({"product": product_name})

    records, err = run_cypher(
        query,
        {"product": product_name}
    )

    if err:
        return err

    return format_records(records)


def list_product_stages(product_name: str) -> str:
    print(f"\n[API] list_product_stages(product={product_name})")

    query = """
    MATCH (p:Product {name:$product})-[rel:HAS_STAGE]->(s:Stage)
    RETURN s.name AS stage,
           rel.emission AS emission
    ORDER BY rel.emission DESC
    """

    print("\n[Cypher Query]")
    print(query)

    print("\n[Parameters]")
    print({"product": product_name})

    records, err = run_cypher(
        query,
        {"product": product_name}
    )

    if err:
        return err

    return format_records(records)


def compare_two_products(product_a: str, product_b: str) -> str:
    query = """
    MATCH (p:Product)-[rel:HAS_STAGE]->(:Stage)
    WHERE p.name IN [$a, $b]
    WITH p.name AS product, sum(rel.emission) AS total_emission
    RETURN product, total_emission
    ORDER BY total_emission DESC
    """
    records, err = run_cypher(query, {"a": product_a, "b": product_b})
    if err:
        return err
    return format_records(records)


def list_all_stage_names() -> List[str]:
    query = """
    MATCH (s:Stage)
    RETURN DISTINCT s.name AS stage
    ORDER BY stage
    """
    records, err = run_cypher(query)
    if err:
        return []
    return [row["stage"] for row in records if row.get("stage")]


# =========================
# 5) 简单意图识别
# =========================
def classify_intent(question: str) -> str:
    q = question.strip()
    if any(k in q for k in ["画图", "柱状图", "折线图", "饼图", "导出", "报告", "统计图"]):
        return "api"
    if any(k in q for k in ["总排放", "某阶段", "阶段", "产品信息", "总量", "对比", "分别", "所有阶段"]):
        return "api"
    return "cypher"


# =========================
# 6) Text2API 路由
# =========================
STAGE_KEYWORDS = ["原料获取", "原料运输", "生产", "制造", "包装", "使用", "报废", "废弃物处理", "产品运输", "催熟", "产品批发仓储和销售", "消费者用塑料袋"]


def extract_entities_with_llm(question: str) -> Dict[str, Optional[str]]:
    """用大模型抽取 product / stage。"""

    # 动态读取数据库中的标准阶段
    all_stages = list_all_stage_names()

    prompt = f"""
你是一个碳排放知识图谱的实体抽取助手。

请从用户问题中抽取：

1. product（产品名称）
2. stage（生命周期阶段）

-----------------------------------
数据库中的标准阶段名称如下：

{all_stages}

-----------------------------------

要求：

1. stage 必须严格从上面的标准阶段列表中选择
2. 不允许自由生成新的 stage
3. 用户说法可能是口语化的，需要映射到最接近的标准阶段
4. 例如：
   - “运输阶段” → “产品运输”
   - “物流环节” → “产品运输”
   - “生产阶段” → “生产”
   - “使用环节” → “使用”
5. product 只保留产品本身名称
6. 不要把“阶段”“排放”“碳排放”“总排放”等词放进 product
7. 如果无法确定 stage，则返回 null
8. 如果无法确定 product，则返回 null

-----------------------------------

用户问题：
{question}

-----------------------------------

只返回 JSON：

{{
  "product": "...",
  "stage": "..."
}}
"""

    response = llm.invoke(prompt)

    text = response.content.strip()

    try:
        import json

        text = text.replace("```json", "").replace("```", "").strip()

        data = json.loads(text)

        return {
            "product": data.get("product") or None,
            "stage": data.get("stage") or None,
        }

    except Exception:
        return {
            "product": None,
            "stage": None
        }


def run_text2api(question: str) -> str:
    q = question.strip()

    print(f"\n[Question] {q}")

    # 用大模型抽取 product / stage
    entities = extract_entities_with_llm(q)
    product = entities.get("product")
    stage = entities.get("stage")

    print(f"[Extracted Product] {product}")
    print(f"[Extracted Stage] {stage}")

    # 1) 画图/导出类，后面你可以继续扩展成真正 API
    if any(k in q for k in ["画图", "柱状图", "折线图", "饼图", "统计图"]):
        if product:
            stages = list_product_stages(product)
            return f"""[TODO: draw_chart]
产品: {product}
阶段数据:
{stages}"""
        return "未识别到产品，暂时无法画图。"

    if any(k in q for k in ["导出", "报告"]):
        if product:
            info = get_product_info(product)
            stages = list_product_stages(product)
            return f"""[TODO: export_or_report]
产品信息:
{info}

阶段数据:
{stages}"""
        return "未识别到产品，暂时无法导出/生成报告。"

    # 2) 常用查询
    if product and stage:
        return get_stage_emission(product, stage)

    if product and any(k in q for k in ["总排放", "总量"]):
        return get_total_emission(product)

    if product and any(k in q for k in ["信息", "概况", "详情"]):
        return get_product_info(product)

    if product and any(k in q for k in ["有哪些阶段", "所有阶段", "阶段有哪些", "生命周期阶段"]):
        return list_product_stages(product)

    if stage and not product:
        return f"已识别到阶段：{stage}，但没有识别到产品名称。请补充产品名。"

    return "未命中常用API，准备走Text2Cypher兜底。"


# =========================
# 7) Text2Cypher：兜底查询
# =========================
def generate_cypher(question: str) -> str:
    stage_text = ", ".join(list_all_stage_names())

    prompt = f"""
你是一个Neo4j Cypher专家，请根据用户问题生成Cypher查询语句。

图数据库结构：
{GRAPH_SCHEMA}

数据库中存在的阶段：
{stage_text}

要求：
1. 只返回Cypher，不要解释
2. 优先使用 MATCH / OPTIONAL MATCH / WHERE / RETURN
3. emission 存在关系 rel.emission 上
4. 产品名称使用 p.name
5. 地区使用 r.name
6. 年份使用 y.value
7. 如果问某产品总排放，使用 sum(rel.emission)
8. 如果问阶段排放，匹配 (p)-[rel:HAS_STAGE]->(s:Stage)
9. 如果问题提到“阶段/环节/生命周期”，优先用 Stage 节点
10. 如果问题涉及“产品信息”，返回产品元信息：unit、boundary、tech、source、region、year

用户问题：
{question}
"""
    response = llm.invoke(prompt)
    cypher = response.content.strip()
    cypher = cypher.replace("```cypher", "").replace("```", "").strip()
    return cypher


def run_text2cypher(question: str) -> str:
    cypher = generate_cypher(question)
    records, err = run_cypher(cypher)
    if err:
        return err
    result_text = format_records(records)
    answer_prompt = f"""
你是一个专业的碳排放知识图谱分析助手。

你的任务是：
根据图数据库查询结果，
生成自然、准确、简洁的中文回答。

-----------------------------------
用户问题：
{question}

-----------------------------------
Cypher查询语句：
{cypher}

-----------------------------------
查询结果：
{result_text}

-----------------------------------

回答要求：

1. 用自然语言回答，不要直接照抄数据库字段
2. 回答要像专业分析助手，而不是程序输出
3. 如果存在产品、地区、年份：
   要主动说明
4. 如果涉及生命周期阶段：
   要明确指出阶段名称
5. 如果涉及排放值：
   必须保留数值
6. 如果结果为空：
   明确说明数据库中未找到相关数据
7. 如果有多个结果：
   要分点说明
8. 不要编造数据库中不存在的信息
9. 不要输出 Cypher
10. 不要解释数据库结构

-----------------------------------

请直接生成最终回答：
"""
    response = llm.invoke(answer_prompt)
    return response.content.strip()


# =========================
# 8) 对外主入口：先 API，后 Cypher
# =========================
def run_question(question: str) -> str:
    intent = classify_intent(question)

    if intent == "api":
        api_result = run_text2api(question)
        if api_result != "未命中常用API，准备走Text2Cypher兜底。":
            return api_result

    return run_text2cypher(question)


# =========================
# 9) 命令行交互
# =========================
def ask(question: str):
    print(f"\n👤 问题: {question}")
    intent = classify_intent(question)
    print(f"🧠 意图: {intent}")

    api_result = run_text2api(question) if intent == "api" else "未走API"
    print(f"\n🔧 API结果:\n{api_result}")

    if api_result == "未命中常用API，准备走Text2Cypher兜底。" or intent == "cypher":
        cypher = generate_cypher(question)
        print(f"\n🏆 生成的 Cypher:\n{cypher}")
        records, err = run_cypher(cypher)
        if err:
            print(f"\n❌ {err}")
            return err
        formatted = format_records(records)
        print(f"\n📊 查询结果:\n{formatted}")
        answer = run_text2cypher(question)
        print(f"\n🤖 AI回答:\n{answer}")
        return answer

    print(f"\n🤖 AI回答:\n{api_result}")
    return api_result


if __name__ == "__main__":
    print("🚀 Text2Cypher + Text2API 已启动（输入 exit 退出）")
    while True:
        q = input("\n请输入问题：")
        if q.lower() in ["exit", "quit"]:
            break
        ask(q)
