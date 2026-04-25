import sqlite3
import os
from langchain_openai import ChatOpenAI

DASHSCOPE_API_KEY = "sk-648d3fd76f2e464d9b037c82d17df2dc" 

# ===== 2. 初始化 LLM（统一用这个）=====
llm = ChatOpenAI(
    model="qwen-plus",
    openai_api_key=DASHSCOPE_API_KEY,
    openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
    temperature=0
)

# ===== 3. 数据库结构（给模型看的）=====
SCHEMA = """
表 products:
- id (产品ID)
- name (产品名称)
- unit (单位)
- boundary (系统边界)
- tech (技术)
- region (地区)
- source (数据来源)
- date (年份)

表 emissions:
- id
- product_id (关联 products.id)
- stage (阶段)
- emission (碳排放)

关系:
products.id = emissions.product_id
"""
# ===== 6.5 AI生成最终答案 =====
def generate_answer(question, sql, result):
    prompt = f"""
你是一个碳排放分析助手，请根据数据库查询结果回答用户问题。

用户问题：
{question}

SQL查询语句：
{sql}

查询结果：
{result}

请给出最终回答，要求：
1. 用自然语言回答（像人说话）
2. 说明清楚产品、时间、地区（如果有）
3. 数值要写清楚
4. 如果有多个结果，请分别说明
5. 如果结果为空，请说明未找到数据
"""

    response = llm.invoke(prompt)
    return response.content.strip()


# ===== 6.5 AI生成最终答案 =====
def generate_answer(question, sql, result):
    prompt = f"""
你是一个碳排放分析助手，请根据数据库查询结果回答用户问题。

用户问题：
{question}

SQL查询语句：
{sql}

查询结果：
{result}

请给出最终回答，要求：
1. 用自然语言回答（像人说话）
2. 说明清楚产品、时间、地区（如果有）
3. 数值要写清楚
4. 如果有多个结果，请分别说明
5. 如果结果为空，请说明未找到数据
"""

    response = llm.invoke(prompt)
    return response.content.strip()


# ===== 4. 生成 SQL =====
def generate_sql(question):
    prompt = f"""
你是一个SQLite专家，请根据用户问题生成SQL查询语句。

数据库结构：
{SCHEMA}

要求：
1. 只能写 SELECT 查询
2. 必须使用 JOIN：
   FROM products p
   JOIN emissions e ON p.id = e.product_id

3. 条件解析规则（非常重要）：
- 如果问题中提到“年份”，使用 p.date
- 如果提到“地区/国家/地方”，必须使用 p.region
- 如果提到“产品名称”，使用 p.name

4. 聚合规则：
- “总排放” → SUM(e.emission)
- 如果查询涉及多个地区 → 必须 GROUP BY p.region
- 如果已经明确指定地区 → 不需要 GROUP BY

5. 所有字符串必须加引号，例如：
   p.date = '2023'
   p.region = '中国云南'

6. 只返回SQL，不要解释

用户问题：
{question}
"""

    response = llm.invoke(prompt)

    sql = response.content.strip()

    # 🔥 清理模型输出（非常重要）
    sql = sql.replace("```sql", "").replace("```", "").strip()

    return sql

# ===== 5. 执行 SQL =====
def run_sql(sql):
    conn = sqlite3.connect("text2sql/carbon.db")
    cursor = conn.cursor()

    try:
        cursor.execute(sql)
        result = cursor.fetchall()
    except Exception as e:
        result = f"SQL执行错误: {e}"

    conn.close()
    return result

# ===== 6. 主流程 =====
def ask(question):
    print(f"\n👤 问题: {question}")

    # 1. 生成SQL
    sql = generate_sql(question)
    print(f"\n🧠 生成SQL:\n{sql}")

    # 2. 执行SQL
    result = run_sql(sql)
    print(f"\n📊 查询结果:\n{result}")

    # 3. AI生成最终答案
    answer = generate_answer(question, sql, result)

    print(f"\n🤖 AI回答:\n{answer}")

    return answer

# ===== 7. 启动 =====
if __name__ == "__main__":
    print("🚀 text2sql 已启动（输入 exit 退出）")

    while True:
        q = input("\n请输入问题：")

        if q.lower() in ["exit", "quit"]:
            break

        ask(q)