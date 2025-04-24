from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from apis.deepseek_api import deepseek_stream_generator
from apis.openai_api import openai_stream_generator
from apis.langchain_test_api import agent_stream_generator
# from apis.langchain_okx_api import agent_stream_generator
# from api_keys import OPENAI_API_KEY, DEEPSEEK_API_KEY

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")


# render_env\Scripts\activate
# uvicorn main:app --reload --log-level debug
# pip freeze | ForEach-Object { pip uninstall -y ($_.Split('==')[0]) }
# pip freeze > requirements.lock
# pip install -r requirements.txt --pre
# python -m coincap.get_history

app = FastAPI()

# CORS 配置（根据你的前端地址调整）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议指定具体域名
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/langchain")
async def agent_analysis(request: Request):
    try:
        data = await request.json()
        query = data.get("query", "")
        
        async def event_stream():
            async for chunk in agent_stream_generator(query):
                if chunk["type"] == "done":
                    yield "data: [DONE]\n\n"
                else:
                    # 添加SSE格式包装
                    yield f"data: {json.dumps(chunk)}\n\n"
        
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/openai")
async def chat_completion(request: Request):
    try:
        data = await request.json()
        messages = data.get("messages", [])

        async def event_stream():
            async for chunk in openai_stream_generator(messages, OPENAI_API_KEY):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/deepseek")
async def chat_completion(request: Request):
    try:
        data = await request.json()
        messages = data.get("messages", [])

        async def event_stream():
            async for chunk in deepseek_stream_generator(messages, DEEPSEEK_API_KEY):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/data")
def get_data():
    return {"data": [1, 2, 3]}

@app.get("/health")
@app.head("/health")
def health_check():
    return {"status": "ok"}