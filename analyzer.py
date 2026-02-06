from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL

client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)


def analyze_news(all_news):
    # 将多源消息格式化为 LLM 易读的文本
    context = ""
    for item in all_news:
        context += f"【来源: {item['source']}】\n内容: {item['content']}\n---\n"

    prompt = f"""
    你是一个资深的新闻分析师。以下是过去几个小时内不同来源的资讯信息：
    {context}

    请执行以下任务：
    1. 聚合相同事件：将讨论同一件事的新闻归类。
    2. 多维度分析：如果同一个事件有多个来源，请对比它们在报道立场、侧重点或细节上的差异。
    3. 每日精选：选出最值得关注的 3 条新闻。
    
    请用 Markdown 格式输出，语言简洁专业。
    """

    response = client.chat.completions.create(
        model="gpt-5-mini",  # 或 deepseek-chat
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content
