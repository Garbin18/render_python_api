from openai import AsyncOpenAI
from typing import AsyncGenerator

# 配置 OpenAI 官方API URL
OPENAI_API_URL = "https://api.openai.com/v1"

async def openai_stream_generator(messages: list, api_key: str) -> AsyncGenerator[str, None]:
    # 创建异步客户端实例
    client = AsyncOpenAI(
        base_url=OPENAI_API_URL,
        api_key=api_key
    )

    try:
        # 调用Chat Completions接口
        stream = await client.chat.completions.create(
            model="gpt-4o-mini",  # 或 "gpt-4"
            messages=messages,
            temperature=0.7,
            stream=True
        )

        # 处理流式响应
        async for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                content = chunk.choices[0].delta.content
                if content:
                    yield content

    except Exception as e:
        print(f"OpenAI API请求异常: {str(e)}")
        yield "[ERROR] OpenAI服务异常，请检查API密钥或稍后重试"
        raise

    finally:
        await client.close()