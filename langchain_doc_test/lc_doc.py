from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from api_keys import SUPABASE_URL, SUPABASE_PUBLIC_KEY, DEEPSEEK_API_KEY

model = ChatOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1",
    model="deepseek-chat",
    temperature=0.5,  
)

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a helpful assistant. Respond only in Spanish."),
        ("placeholder", "{messages}"),
        ("user", "Also say 'Pandamonium!' after the answer."),
    ]
)

@tool
def magic_function(input: int) -> int:
    """Applies a magic function to an input."""
    return input + 2

tools = [magic_function]

query = "what is the value of magic_function(3)?"

langgraph_agent_executor = create_react_agent(model, tools, prompt=prompt)

# messages = langgraph_agent_executor.invoke({"messages": [("human", query)]})
# print(messages["messages"][-1].content)

for step in langgraph_agent_executor.stream(
    {"messages": [("human", query)]}, stream_mode="updates"
):
    print(step)