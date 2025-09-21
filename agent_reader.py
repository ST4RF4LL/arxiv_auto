
from langchain_core.messages import HumanMessage,SystemMessage
from langgraph.checkpoint.memory import MemorySaver ## 保存记忆
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
import configparser
import pprint
import json
from log import logger as log
import os 
# mcp
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
import uuid

# 获取配置项的值
config = configparser.ConfigParser()
config.read('config.ini')  # 读取配置文件
model = config['llm']['model']
base_url = config['llm']['base_url']
api_key = config['llm']['api_key']
llm_service_type = config['general']['LLM_SERVICE_TYPE']


# 读论文 markitdown-mcp必须用结对路径  带./的相对路径似乎有解析问题
async def read(paper_filepath: str):
    log.info(f'读取论文: {paper_filepath}')

    papername = paper_filepath.split('/')[-1]
    summary_filepath = f"./summary_result/{papername}_summary.md"
    if os.path.exists(summary_filepath):
        log.info(f'论文已分析过: {papername}')
        return
    ## 创建Agent
    memory = MemorySaver()
    llm = ChatOpenAI(model=model,openai_api_base=base_url,openai_api_key=api_key)

    client =  MultiServerMCPClient(
        {
        "markitdown": {
            "url": "http://127.0.0.1:3001/mcp",
            "transport": "streamable_http",
        }
        }
    )
    tools = await client.get_tools()
    # async with client.session("markitdown") as session:
    #     tools = await load_mcp_tools(session)
    
    agent = create_react_agent(llm, tools, checkpointer=memory) ## 使用 checkpointer 建立记忆
    ## memory配置
    config = {"configurable": {"thread_id": uuid.uuid4()}} #指定 thread_id 的名称，针对性地管理 memory

    chunks = []
    ## run
    with open('prompts/read_a_paper.txt', 'r') as f:
        
        task_query = f.read().format(paper_filepath=paper_filepath,papername=papername)
    with open('prompts/system_paper_reader.txt', 'r') as f:
        system_prompt = f.read()
    async for chunk in agent.astream(
        {"messages": [SystemMessage(content=system_prompt),HumanMessage(content=task_query)]},
        config,
        stream_mode="values"
    ):
        chunks.append(chunk)
        print("------")
        pprint.pprint(chunk, depth=2)
        log.info(chunk['messages'][-1])
    
    # python不自带filesystem，不如直接用open
    # prompt:保存到summary_result目录下，并以markdwon格式将分析结果保存为`{papername}_summary.md`
    # 从chunks里提取最后一个AIMessage chunk
    last_aimessage = chunks[-1]['messages'][-1]
    with open(summary_filepath, 'w') as f:
            f.write(last_aimessage.content) # 如果不出问题，最后一个chunk应该是AIMessage


if __name__ == "__main__":
    import asyncio
    asyncio.run(read('/mnt/d/WorkSpace/arxiv_auto/pdf_downloads/2504.05259v1.pdf'))
    