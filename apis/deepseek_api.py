from openai import AsyncOpenAI
from typing import AsyncGenerator

# 配置 DeepSeek 的 API URL
DEEPSEEK_API_URL = "https://api.deepseek.com/v1"

async def deepseek_stream_generator(messages: list, api_key: str) -> AsyncGenerator[str, None]:
    # 创建异步客户端实例
    client = AsyncOpenAI(
        base_url=DEEPSEEK_API_URL,
        api_key=api_key
    )

    try:
        # 调用Chat Completions接口
        stream = await client.chat.completions.create(
            model="deepseek-chat",
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
        print(f"API请求异常: {str(e)}")
        yield "[ERROR] 服务暂时不可用，请稍后重试"
        raise

    finally:
        await client.close()  # 确保关闭客户端连接