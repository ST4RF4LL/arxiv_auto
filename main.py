import os
import requests
import configparser
from langchain_openai import ChatOpenAI
import asyncio
import json

import xml.etree.ElementTree as ET
from datetime import datetime,timedelta
from log import logger as log
from agent_reader import read

os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'

config = configparser.ConfigParser()
config.read('config.ini')  # 读取配置文件

# 获取配置项的值
model = config['llm']['model']
base_url = config['llm']['base_url']
api_key = config['llm']['api_key']
llm_service_type = config['general']['LLM_SERVICE_TYPE']

# 初始化
# 初始化 ChatOpenAI 模型
llm=ChatOpenAI(model=model,openai_api_base=base_url,openai_api_key=api_key)

# 获取 Arxiv 上的论文信息，TODO：根据关键词列表筛选
def get_arxiv(topics,days=7,):
    # 定义 API URL
    topics = list(set(topics))
    max_results = 1000  # 每页最多返回的结果数
    arxiv_base_url = 'http://export.arxiv.org/api/query'
    today = datetime.today().strftime('%Y%m%d')  # 获取今天的日期，格式为 YYYYMMDD
    last_week = (datetime.today() - timedelta(days)).strftime('%Y%m%d')  # 获取一周前的日期，格式为 YYYYMMDD
    topic_str = ' AND '.join([f'all:{topic}' for topic in topics])
    search_query = f'submittedDate:[{last_week} TO {today}] AND {topic_str}'
    arxiv_url = f'{arxiv_base_url}?search_query={search_query}&max_results={max_results}'
    log.debug(arxiv_url)
    try:
        # 发送 GET 请求
        response = requests.get(arxiv_url)
        # 检查响应状态码
        response.raise_for_status()
        # 打印响应内容
        # print(response.text)
        return response.text
    except requests.exceptions.RequestException as e:
        log.error(f'请求出错: {e}')
        return ''

# 获取论文的引用量
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

# 下载PDF文件
def download_pdf(pdf_url, pdf_filename):
    # 检查保存目录是否存在，如果不存在则创建
    os.makedirs(os.path.dirname(pdf_filename), exist_ok=True)
    
    try:
        # 添加请求头模拟浏览器访问
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 发送GET请求获取PDF文件，使用stream=True进行流式下载
        response = requests.get(pdf_url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()  # 检查请求是否成功
        
        # 以二进制模式写入文件
        with open(pdf_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # 过滤掉保持连接的空块
                    f.write(chunk)
        
        log.info(f'PDF已成功下载: {pdf_filename}')
        return True
        
    except requests.exceptions.RequestException as e:
        log.error(f'下载PDF失败 {pdf_url}: {str(e)}')
    except IOError as e:
        log.error(f'保存PDF文件失败 {pdf_filename}: {str(e)}')
    except Exception as e:
        log.error(f'下载PDF时发生未知错误: {str(e)}')
    
    return False

# 使用llm阅读论文正文，看需求是否需要换LLM
# 优先html，提取文本比较方便
# 如果html提取失败，再用pdf
def paper_read(reader_llm,html_url,pdf_url=None):
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    
    if html_url:
        # 从html中提取文本
        try:
            # 添加请求头模拟浏览器访问
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(html_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取论文正文（根据arXiv HTML结构调整选择器）
            content_div = soup.find('div', class_='ltx_page_content')
            if not content_div:
                content_div = soup.find('body')  # 备选方案
            
            # 提取文本内容
            text_content = content_div.get_text(separator='\n', strip=True) if content_div else ''
            
            # 使用LLM分析内容（仅文本输入）
            analysis_prompt = f"分析以下论文内容: \n{text_content[:8000]}..."
            analysis_result = reader_llm.invoke(analysis_prompt)  # 不再传递images参数
            
            return {
                'text': text_content,
                'analysis': analysis_result
            }
            
        except Exception as e:
            log.error(f'HTML内容提取失败: {str(e)}')
            if pdf_url:
                return paper_read(reader_llm, None, pdf_url)
            return {'error': str(e)}
        
    elif pdf_url:
        # 从pdf中提取文本
        pass
    else:
        return {'error': '未提供论文链接'}



def run(topics = ['agent','red team'],days=360,deep_read = True):
    # 获取 Arxiv 上的论文信息
    t
    arxiv_data = get_arxiv(topics,days=days)

    # 创建输出目录
    output_dir = 'output'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 初始化Markdown内容
    markdown_content = '# arXiv论文信息汇总\n\n'
    
    # 解析 Arxiv 数据
    if arxiv_data:
        # 解析 XML 数据
        root = ET.fromstring(arxiv_data)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('.//atom:entry', ns)
        log.info(f'总论文数: {len(entries)}')
        # log.info(entries)

        # 生成带时间戳的文件名
        current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        topic_filename = '_'.join(topics)
        md_filename = os.path.join(output_dir, f'arxiv_{topic_filename}_{current_time}.md')
        

        for entry in entries:
            # 提取标题和简述
            title = entry.find('atom:title', ns).text.strip().replace('\n',' ') # 标题
            summary = entry.find('atom:summary', ns).text.strip().replace('\n',' ') # 简述
            url = entry.find('atom:id', ns).text.strip() # 链接
            arxiv_id = entry.find('atom:id', ns).text.strip().split('/')[-1].split('v')[0] # arxiv_id

            # 使用 LLM 对简述进行翻译总结
            with open('prompts/summarize_a_paper.txt', 'r') as f:
                prompt = f.read().format(title=title,summary=summary)
            translated_summary = llm.invoke(prompt).content
            citation_count = get_citation_count(arxiv_id) 
            
            # 使用 LLM 根据简述生成标签
            with open('prompts/tag_a_paper.txt', 'r') as f:
                tags_prompt = f.read().format(title=title,summary=translated_summary)
            tags_result = llm.invoke(tags_prompt).content
            tags = tags_result.replace('\n','').split(',')  # 假设标签以逗号分隔

            # 打印结果 
            log.info(f'arXiv ID: {arxiv_id}')
            log.info(f'标题: {title}')
            log.info(f'链接: {url}')
            log.info(f'原始简述: {summary}')
            log.info(f'翻译总结: {translated_summary}\n')
            log.info(f'标签: {tags}\n')
            log.info(f'引用量: {citation_count}')

            # 提取论文ID并构建PDF和HTML链接
            paper_id = url.split('/')[-1]
            pdf_url = f'https://arxiv.org/pdf/{paper_id}.pdf'
            html_url = f'https://arxiv.org/html/{paper_id}'
            log.info(f'PDF链接: {pdf_url}')
            log.info(f'HTML链接: {html_url}\n')

            deep_read_success = False
            if deep_read:
                # 下载pdf
                pdf_filename = os.path.join(os.getcwd(),'pdf_downloads', f'{paper_id}.pdf')
                download_pdf(pdf_url, pdf_filename)
                # 异步分析论文
                try:
                    asyncio.run(read(pdf_filename))
                    log.info(f'分析论文完成: {paper_id}')
                    deep_read_success = True
                except Exception as e:
                    log.error(f'分析论文失败: {paper_id}')
                    continue
                # 没有文件则生成markdown 有则追加
            with open(md_filename, 'a', encoding='utf-8') as f:
                # f.write(markdown_content)
                markdown_content = f'# {title}\n\n'
                markdown_content += f'## 链接\n[{url}]({url})\n'
                markdown_content += f'## 原始简述\n{summary}\n'
                markdown_content += f'## 翻译总结\n{translated_summary}\n'
                markdown_content += f'## 标签\n{tags}\n' 
                markdown_content += f'## 引用量\n{citation_count}\n'
                markdown_content += f'## PDF链接\n[{pdf_url}]({pdf_url})\n'
                markdown_content += f'## HTML链接\n[{html_url}]({html_url})\n'
                if deep_read_success:
                    markdown_content += f'## 分析总结\n请查看 `summary_result/{paper_id}_summary.md` 文件\n'
                markdown_content += '\n\n---- \n\n'
                f.write(markdown_content)

        log.info(f'论文信息已保存到: {md_filename}')

def run2(pasa_file, deep_read=True):
    """
    基于指定的JSON文件运行论文分析流程
    
    参数:
    - pasa_file: 包含论文信息的JSON文件路径，例如"paper-agent-download.json"
    - deep_read: 是否深度阅读论文内容
    """
    
    
    # 创建输出目录
    output_dir = 'output'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 初始化Markdown内容
    markdown_content = '# arXiv论文信息汇总\n\n'    
    
    try:
        # 读取JSON文件
        with open(pasa_file, 'r', encoding='utf-8') as f:
            papers_data = json.load(f)
        
        log.info(f'从文件{pasa_file}中读取到{len(papers_data)}篇论文')
        
        # 生成带时间戳的文件名
        current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        md_filename = os.path.join(output_dir, f'papers_from_json_{current_time}.md')
        
        # 处理每篇论文
        for paper in papers_data:
            # 提取论文基本信息
            title = paper.get('title', '未知标题')
            summary = paper.get('summary', '无摘要信息')
            url = paper.get('url', '')
            arxiv_id = url.split('/')[-1].split('v')[0] if url else 'unknown'
            
            # 使用LLM对简述进行翻译总结
            with open('prompts/summarize_a_paper.txt', 'r') as f:
                prompt = f.read().format(title=title, summary=summary)
            translated_summary = llm.invoke(prompt).content
            citation_count = get_citation_count(arxiv_id) if arxiv_id != 'unknown' else None
            
            # 使用LLM根据简述生成标签
            with open('prompts/tag_a_paper.txt', 'r') as f:
                tags_prompt = f.read().format(title=title, summary=translated_summary)
            tags_result = llm.invoke(tags_prompt).content
            tags = tags_result.replace('\n', '').split(',')  # 假设标签以逗号分隔
            
            # 提取论文ID并构建PDF和HTML链接
            paper_id = url.split('/')[-1] if url else arxiv_id
            pdf_url = f'https://arxiv.org/pdf/{paper_id}.pdf' if paper_id != 'unknown' else ''
            html_url = f'https://arxiv.org/html/{paper_id}' if paper_id != 'unknown' else ''
            
            # 打印结果
            log.info(f'arXiv ID: {arxiv_id}')
            log.info(f'标题: {title}')
            log.info(f'链接: {url}')
            log.info(f'原始简述: {summary}')
            log.info(f'翻译总结: {translated_summary}\n')
            log.info(f'标签: {tags}\n')
            log.info(f'引用量: {citation_count}')
            
            deep_read_success = False
            if deep_read and pdf_url:
                # 下载pdf
                pdf_filename = os.path.join(os.getcwd(), 'pdf_downloads', f'{paper_id}.pdf')
                download_pdf(pdf_url, pdf_filename)
                # 异步分析论文
                try:
                    asyncio.run(read(pdf_filename))
                    log.info(f'分析论文完成: {paper_id}')
                    deep_read_success = True
                except Exception as e:
                    log.error(f'分析论文失败: {paper_id}')
                    # 即使分析失败也继续处理其他论文
                    
            # 将结果写入markdown文件
            with open(md_filename, 'a', encoding='utf-8') as f:
                markdown_content = f'# {title}\n\n'
                markdown_content += f'## 链接\n[{url}]({url})\n' if url else '## 链接\n无\n'
                markdown_content += f'## 原始简述\n{summary}\n'
                markdown_content += f'## 翻译总结\n{translated_summary}\n'
                markdown_content += f'## 标签\n{tags}\n'
                markdown_content += f'## 引用量\n{citation_count}\n' if citation_count is not None else '## 引用量\n无法获取\n'
                markdown_content += f'## PDF链接\n[{pdf_url}]({pdf_url})\n' if pdf_url else '## PDF链接\n无\n'
                markdown_content += f'## HTML链接\n[{html_url}]({html_url})\n' if html_url else '## HTML链接\n无\n'
                if deep_read_success:
                    markdown_content += f'## 分析总结\n请查看 `summary_result/{paper_id}_summary.md` 文件\n'
                markdown_content += '\n\n---- \n\n'
                f.write(markdown_content)
        
        log.info(f'论文信息已保存到: {md_filename}')
        return md_filename
        
    except json.JSONDecodeError as e:
        log.error(f'JSON文件解析错误: {str(e)}')
    except FileNotFoundError:
        log.error(f'文件不存在: {pasa_file}')
    except Exception as e:
        log.error(f'处理论文数据时发生错误: {str(e)}')
    
    return None

if __name__ == '__main__':
    # run()
    # 如果需要运行run2函数，可以取消下面一行的注释并指定JSON文件路径
    run2('test/paper-agent-download.json', deep_read=False)
