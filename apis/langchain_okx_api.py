from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from supabase import create_client
import os
import pandas as pd
from typing import Dict, Any
from fastapi.concurrency import run_in_threadpool
import okx.MarketData as MarketData
# from api_keys import DEEPSEEK_API_KEY,SUPABASE_PUBLIC_KEY


SUPABASE_URL = 'https://zcmrdzzgbnsrslsglrjg.supabase.co'
SUPABASE_PUBLIC_KEY = os.getenv("SUPABASE_PUBLIC_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# 自定义工具：获取BTC价格
@tool("get_crypto_price")
def get_crypto_price(instId:str,bar:str,limit:int) -> pd.DataFrame:
  """从okx的api获得K线数据，获取最新的BTC日线价格数据，包括开盘价、最高价、最低价、收盘价等信息"""
  flag = "0"  # 实盘:0 , 模拟盘：1
  marketDataAPI =  MarketData.MarketAPI(flag=flag)
  # 获取交易产品K线数据
  result = marketDataAPI.get_candlesticks(
      instId=instId,
      bar=bar,
      limit=max(limit, 100)
  )
  # 转换为DataFrame并处理列名
  data = result['data']
  df = pd.DataFrame(data, columns=[
      'timestamp', 'open', 'high', 'low', 'close',
      'volume', 'vol_ccy', 'vol_ccy_quote', 'confirm'
  ])
  # 强制转换所有数值列为 float
  numeric_cols = ['open', 'high', 'low', 'close', 'volume']
  df[numeric_cols] = df[numeric_cols].astype(float)
  # 反转数据顺序（OKX默认返回的是倒序，最新数据在前）
  df = df.iloc[::-1].reset_index(drop=True)
  # 添加时间戳转换（东八区）并格式化为字符串
  df['datetime'] = pd.to_datetime(df['timestamp'].astype(int)//1000, unit='s') + pd.Timedelta(hours=8)
  df.set_index('datetime', inplace=True)
  df.ta.macd(append=True)  # 结果会自动添加 MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9 三列
  df.ta.rsi(length=14, append=True)  # 添加 RSI_14 列
  df.ta.bbands(length=20, append=True)  # 添加 BBU_20_2.0, BBL_20_2.0, BBB_20_2.0 等列
  df.ta.sma(length=30, append=True)   # 添加 SMA_30 列
  df.ta.sma(length=60, append=True)  # 添加 SMA_60 列
  df.ta.vwap(anchor='D', append=True)  # 添加 VWAP_D 列
  df = df.reset_index()
  df['instId'] = instId
  # 精简列（保留关键字段）
  cols = ['instId', 'datetime', 'open', 'high', 'low', 'close',  'volume', 'SMA_30', 'SMA_60', 'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9', 'RSI_14']
  df_subset = df[cols].copy()
  # 精度压缩（减少小数位数）
  df_subset = df_subset.round(2)
  result = df_subset.tail(20)
  print(result)
  return result
    
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

# query = "基于当前价格，现在投资BTC合适吗？"

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

