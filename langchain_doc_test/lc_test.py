from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from supabase import create_client
import json
from typing import Dict, Any
from api_keys import SUPABASE_URL, SUPABASE_PUBLIC_KEY, DEEPSEEK_API_KEY

# 自定义工具：获取BTC价格
@tool("get_crypto_price")
def get_crypto_price() -> list:
    """获取最新的BTC日线价格数据，包括开盘价、最高价、最低价、收盘价等信息"""
    try:
        client = create_client(SUPABASE_URL, SUPABASE_PUBLIC_KEY)
        response = client.table("daily_crypto_klines")\
                        .select("*")\
                        .order("datetime", desc=True)\
                        .limit(1)\
                        .execute()
        data = response.data if response.data else []
        return data  
    except Exception as e:
        return ["Error"]
    
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", """
        你是一个加密货币专家，必须按以下步骤工作：
        1. 使用工具获取实时数据
        2. 分析价格趋势
        3. 给出明确建议（买入/持有/卖出）
        4. 用中文输出
        """),
        ("placeholder", "{messages}"),
    ]
)

model = ChatOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1",
    model="deepseek-chat",
    temperature=0.5,  
)

tools = [get_crypto_price]
    
agent = create_react_agent(model, tools,prompt=prompt)

query = "基于当前价格，现在投资BTC合适吗？"

# response = agent.invoke(
#     {"messages": [("human", query)]}
# )
# print(response["messages"][-1].content)

def parse_stream_output(step: Dict[str, Any]) -> None:
    # 阶段1: Agent决定调用工具
    if "agent" in step and "tool_calls" in step["agent"]["messages"][0].additional_kwargs:
        msg = step["agent"]["messages"][0]
        print("\n🔧 [阶段1] Agent正在调用工具:")
        print(f"工具名称: {msg.tool_calls[0]['name']}")
        print(f"调用ID: {msg.tool_calls[0]['id']}")
        print(f"消耗token数: {msg.usage_metadata['input_tokens']} (输入) / {msg.usage_metadata['output_tokens']} (输出)")

    # 阶段2: 工具返回数据
    elif "tools" in step:
        tool_msg = step["tools"]["messages"][0]
        print("\n📊 [阶段2] 工具返回原始数据:")
        print(f"工具名称: {tool_msg.name}")
        
        # 解析JSON数据
        try:
            data = json.loads(tool_msg.content)[0]
            print(f"最新K线时间: {data['datetime']}")
            print(f"收盘价: {data['close']} | RSI: {data['rsi']}")
            print(f"30/60日均线: {data['sma_30']}/{data['sma_60']}")
        except (json.JSONDecodeError, KeyError) as e:
            print(f"数据解析失败: {e}")

    # 阶段3: Agent生成最终分析
    elif "agent" in step and step["agent"]["messages"][0].content:
        msg = step["agent"]["messages"][0]
        print("\n💡 [阶段3] Agent分析建议:")
        print(msg.content)  # 直接输出格式化建议
        print(f"总消耗token: {msg.usage_metadata['total_tokens']}")

for step in agent.stream(
    {"messages": [("human", query)]}, stream_mode="updates"
):
    parse_stream_output(step)