from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from supabase import create_client
import json
import os
import asyncio
from typing import Dict, Any
from fastapi.concurrency import run_in_threadpool
# from api_keys import DEEPSEEK_API_KEY,SUPABASE_PUBLIC_KEY


SUPABASE_URL = 'https://zcmrdzzgbnsrslsglrjg.supabase.co'
SUPABASE_PUBLIC_KEY = os.getenv("SUPABASE_PUBLIC_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# 自定义工具：获取BTC价格
@tool("get_crypto_price")
def get_crypto_price() -> list:
    """获取最新的BTC日线价格数据，包括开盘价、最高价、最低价、收盘价等信息"""
    try:
        client = create_client(SUPABASE_URL, SUPABASE_PUBLIC_KEY)
        response = client.table("daily_crypto_klines")\
                        .select("*")\
                        .order("datetime", desc=True)\
                        .limit(20)\
                        .execute()
        data = response.data if response.data else []
        sorted_data = sorted(data, key=lambda x: x["datetime"])
        print(sorted_data)
        return sorted_data  
    except Exception as e:
        return ["Error"]
    
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", """
        你是一个加密货币专家，必须按以下步骤工作：
        1. 使用工具获取实时数据
        2. 分析价格趋势
        3. 给出明确建议（买入/持有/卖出）
        4. 用中文输出，并确保日期注明 **UTC 时间**，例如：
           - 最新价格数据（UTC时间 2025-04-14 16:00:00）
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

def parse_stream_output(step: Dict[str, Any]) -> dict:
    """解析步骤数据为结构化字典"""
    # 阶段1: 工具调用
    if "agent" in step and "tool_calls" in step["agent"]["messages"][0].additional_kwargs:
        msg = step["agent"]["messages"][0]
        return {
            "type": "tool_call",
            "tool_name": msg.tool_calls[0]['name'],
            "input_tokens": msg.usage_metadata.get('input_tokens', 0),
            "output_tokens": msg.usage_metadata.get('output_tokens', 0)
        }
    
    # 阶段2: 工具响应
    elif "tools" in step:
        tool_msg = step["tools"]["messages"][0]
        return {
            "type": "tool_response",
            "tool_name": tool_msg.name,
            "content": tool_msg.content  # 原始数据或可解析为具体字段
        }
    
    # 阶段3: 最终回答
    elif "agent" in step and step["agent"]["messages"][0].content:
        msg = step["agent"]["messages"][0]
        return {
            "type": "final_answer",
            "content": msg.content
        }

    # elif "agent" in step and step["agent"]["messages"][0].content:
    #     msg = step["agent"]["messages"][0]
    #     content = msg.content
    #     for char in content:  # 可以按 char，也可以按 word/sentence
    #         yield {
    #             "type": "final_answer",
    #             "content": char
    #         }
    #     return
    
    # elif "agent" in step and step["agent"]["messages"][0].content:
    #     msg = step["agent"]["messages"][0]
    #     return {
    #         "type": "final_answer",
    #         "content": msg.content,
    #         "total_tokens": msg.usage_metadata.get('total_tokens', 0)
    #     }
    
    return {"type": "unknown"}

async def agent_stream_generator(query: str):
    def sync_stream():
        for step in agent.stream({"messages": [("human", query)]}, stream_mode="updates"):
            parsed = parse_stream_output(step)
            yield parsed
        yield {"type": "done"}

    gen = sync_stream()
    while True:
        try:
            chunk = await run_in_threadpool(next, gen)

            # ⬇️ 如果是最终回答，就逐字 yield
            if chunk.get("type") == "final_answer":
                for char in chunk["content"]:
                    yield {"type": "final_answer", "content": char}
            else:
                yield chunk

            if chunk.get("type") == "done":
                break
        except StopIteration:
            break


    # """将同步流转换为异步生成器，并实现逐字输出"""
    # def sync_stream():
    #     for step in agent.stream({"messages": [("human", query)]}, stream_mode="updates"):
    #         if "agent" in step and step["agent"]["messages"][0].content:
    #             content = step["agent"]["messages"][0].content
    #             for char in content:
    #                 yield {"type": "final_answer", "content": char}
    #         else:
    #             parsed = parse_stream_output(step)
    #             if isinstance(parsed, dict):
    #                 yield parsed
    #     yield {"type": "done"}

    # gen = sync_stream()
    # while True:
    #     try:
    #         chunk = await run_in_threadpool(next, gen)
    #         yield chunk
    #         if chunk.get("type") == "done":
    #             break
    #     except StopIteration:
    #         break

    
    # """将同步流转换为异步生成器"""
    # def sync_stream():
    #     for step in agent.stream(
    #         {"messages": [("human", query)]}, 
    #         stream_mode="updates"
    #     ):
    #         yield parse_stream_output(step)
    #     yield {"type": "done"}
    
    # gen = sync_stream()
    # while True:
    #     try:
    #         # 使用线程池处理同步迭代
    #         chunk = await run_in_threadpool(next, gen)
    #         yield chunk
    #         if chunk.get("type") == "done":
    #             break
    #     except StopIteration:
    #         break