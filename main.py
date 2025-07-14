import os
import requests
import configparser
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
import xml.etree.ElementTree as ET
from datetime import datetime,timedelta


config = configparser.ConfigParser()
config.read('config.ini')  # 读取配置文件

# 获取配置项的值
model = config['llm']['model']
base_url = config['llm']['base_url']
api_key = config['llm']['api_key']

def get_arxiv():
    # 定义 API URL
    max_results = 1  # 每页最多返回的结果数
    arxiv_base_url = 'http://export.arxiv.org/api/query'
    today = datetime.today().strftime('%Y%m%d')  # 获取今天的日期，格式为 YYYYMMDD
    last_week = (datetime.today() - timedelta(days=7)).strftime('%Y%m%d')  # 获取一周前的日期，格式为 YYYYMMDD
    search_query = f'submittedDate:[{last_week} TO {today}] AND ti:llm AND all:security'
    arxiv_url = f'{arxiv_base_url}?search_query={search_query}&max_results={max_results}'
    print(arxiv_url)
    try:
        # 发送 GET 请求
        response = requests.get(arxiv_url)
        # 检查响应状态码
        response.raise_for_status()
        # 打印响应内容
        # print(response.text)
        return response.text
    except requests.exceptions.RequestException as e:
        print(f'请求出错: {e}')
        return ''

def get_citation_count(arxiv_id):
        # 使用 Semantic Scholar API 获取引用量
    semantic_scholar_url = f'https://api.semanticscholar.org/graph/v1/paper/arXiv:{arxiv_id}?fields=citationCount'
    try:
        semantic_response = requests.get(semantic_scholar_url)
        semantic_response.raise_for_status()
        citation_count = semantic_response.json().get('citationCount', 0)
    except requests.exceptions.RequestException:  
        citation_count = None
    return citation_count

# 初始化 ChatOpenAI 模型
llm=ChatOpenAI(model=model,openai_api_base=base_url,openai_api_key=api_key)

# 获取 Arxiv 上的论文信息
arxiv_data = get_arxiv()

# 解析 Arxiv 数据
if arxiv_data:
    # 解析 XML 数据
    root = ET.fromstring(arxiv_data)
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    entries = root.findall('.//atom:entry', ns)
    
    for entry in entries:
        # 提取标题和简述
        title = entry.find('atom:title', ns).text.strip() # 标题
        summary = entry.find('atom:summary', ns).text.strip() # 简述
        url = entry.find('atom:id', ns).text.strip() # 链接
        arxiv_id = entry.find('atom:id', ns).text.strip().split('/')[-1].split('v')[0] # arxiv_id

        # 使用 LLM 对简述进行翻译总结
        prompt = f'这有一篇论文的标题叫{title}，请根据它的summary给出一个中文简述：\n{summary}'
        translated_summary = llm.invoke([HumanMessage(content=prompt)])
        citation_count = get_citation_count(arxiv_id) 
        
        # 使用 LLM 根据简述生成标签
        tags_prompt = f'你是一个计算机科学学术论文分析专家，请根据以下论文的标题和简述生成中文标签，用逗号分隔，如果这篇论文你判断是一个网络安全相关的论文，标签列表中必须包含至少两个标签之一：\'LLM for Security\'--指使用LLM应用于解决网络安全的某些难题；\'Security for LLM\'--指对LLM软硬件及其基础设施的网络安全研究。\n以下是论文信息\n<标题>：{title},<简述>：{summary}'
        tags_result = llm.invoke([HumanMessage(content=tags_prompt)])
        tags = tags_result.content.replace('\n','').split(',')  # 假设标签以逗号分隔

        # 打印结果 
        print(f'标题: {title}')
        print(f'链接: {url}')
        print(f'原始简述: {summary}')
        print(f'翻译总结: {translated_summary.content}\n')
        print(f'标签: {tags}\n')
        print(f'引用量: {citation_count}\n')
