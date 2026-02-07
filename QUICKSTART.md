# 🚀 快速启动指南（优化版）

本指南引导您快速启动改进后的 Telegram 新闻聚合器。

## ✅ 前置条件

- Python 3.8+
- 有效的 Telegram Bot Token（来自 [@BotFather](https://t.me/botfather)）
- LLM API Key（OpenAI、api2gpt 等兼容服务）
- 个人 Telegram Chat ID（用 `/start` 从 bot 获取）

## 📥 安装步骤

### 1. 克隆或进入项目目录

```bash
cd /path/to/telegram-news-aggregator
```

### 2. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# 或
.venv\Scripts\activate      # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环保变量

复制 `.env.example` 到 `.env` 并填入你的值：

```bash
cp .env.example .env
# 用编辑器打开 .env，填入以下必要项：
```

**必需配置：**
```bash
BOT_TOKEN=your_telegram_bot_token_here
CHAT_ID=your_personal_telegram_chat_id
LLM_API_KEY=your_llm_api_key_here
LLM_BASE_URL=https://api.api2gpt.com  # 或其他兼容服务
```

**可选但推荐配置：**
```bash
# RSSHub 配置（防止被公共实例限流）
RSSHUB_BASE_URL=https://rss-hub-cms.zeabur.app/
RSSHUB_FALLBACKS=https://rsshub.axiss.world/,https://rsshub.sxjcu.tk/

# 日志配置
LOG_LEVEL=DEBUG
LOG_FILE=./logs/app.log

# 新的优化配置（已有合理默认值，无需修改）
ARTICLE_MAX_CHARS=800
LLM_CONTEXT_LIMIT=120000
```

### 5. 启动 Bot

```bash
python main.py
```

你应该看到类似的日志：
```
[INFO] telegram.ext.Application: Application started
[DEBUG] fetcher: RSS try: base=... channel=...
```

## 💬 常用命令

在 Telegram 中向 Bot 发送：

| 命令 | 说明 |
|------|------|
| `/start` | 获取问候信息 |
| `/digest` | 获取今日聚合新闻摘要（限你的 CHAT_ID） |
| `/list_subs` | 查看已订阅的频道 |
| `/add_sub <channel_id>` | 添加新订阅源 |
| `/fetch <channel_id> [limit]` | 直接获取某个频道的最新文章 |

### 示例

```
/add_sub TechCrunch
/fetch TechCrunch 5
/digest
```

## 🔍 问题诊断

### Q: 收到 "LLM 未返回可用内容" 错误

**原因**：LLM 因上下文超出或 API Key 无效返回空。

**解决方案**：
1. 检查 `LLM_API_KEY` 是否正确
2. 查看日志文件（`./logs/app.log`）
3. 尝试手动测试 LLM 连接：
   ```bash
   curl -X POST https://api.api2gpt.com/v1/chat/completions \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_KEY" \
     -d '{"model":"gpt-5-mini","messages":[{"role":"user","content":"Hi"}]}'
   ```

### Q: RSSHub 返回 403 或 503

**原因**：公共 RSSHub 实例被限流或被 ISP 封禁。

**解决方案**：
1. 在 `.env` 中配置 `RSSHUB_FALLBACKS`，多个备用实例用逗号分隔
2. 考虑部署自己的 RSSHub（参考 https://github.com/DIYgod/RSSHub）
3. 使用付费稳定的 RSSHub 服务

### Q: Bot 响应缓慢

**原因**：LLM 请求很耗时，但现在已异步化，不应阻塞事件循环。

**调试步骤**：
1. 增加日志级别到 `DEBUG`，观察各步骤耗时
2. 检查网络延迟：
   ```bash
   time curl https://api.api2gpt.com/v1/models
   ```

### Q: 收到空白 Telegram 消息错误

**原因**：已修复，现在有多层保护防止空内容被发送。

**验证**：检查日志是否出现 "LLM 返回空内容"，应该自动重试而非失败。

## 📊 性能调优

### 内存使用
- 默认线程池 3 个 worker，可根据需要在 `analyzer.py` 中调整
- RSSHub 和 LLM 调用都在线程池中运行

### Token 使用
- `ARTICLE_MAX_CHARS=800`：每篇文章最多 800 字符
- `LLM_CONTEXT_LIMIT=120000`：假设模型支持 128k 上下文
- 自动删除冗余文章，保留高质量内容

### 响应时间
- `/digest` 通常需要 10-30 秒（取决于 RSSHub 和 LLM 延迟）
- `/fetch` 通常需要 3-10 秒（仅抓取，不分析）

## 📚 进阶话题

### 1. 自定义频道订阅

编辑 `config.py` 的 `CHANNELS` 列表，或使用 `/add_sub` 命令。

### 2. 自定义分析 Prompt

编辑 `analyzer.py` 中的 prompt 模板，例如：
```python
prompt = f"""你是一个技术博客编辑...
请按照以下格式输出：
1. 头条（最重要的新闻）
2. 深度分析
3. 行业趋势
..."""
```

### 3. 集成到 Heroku/Zeabur

- `Procfile` 已配置为 `web: python main.py`
- 在托管平台中设置环保变量即可部署

### 4. 远程错误上报

在 `.env` 中配置 `ERROR_REPORT_URL=https://your-error-tracking-service`，所有错误将以 JSON POST 发送。

## 📖 完整文档

- `README.md` — 项目概述和完整功能列表
- `ANALYZER_OPTIMIZATION.md` — 优化改进的详细说明
- 各文件注释 — 代码逻辑说明

## 🛠️ 开发与测试

运行单元测试（analyzer 部分）：
```bash
python test_analyzer.py
```

监控日志：
```bash
tail -f logs/app.log
```

## 🎯 下一步

1. 确保 LLM API Key 有效（手工测试一次）
2. 配置至少一个可用的 RSSHub 实例
3. 启动 Bot 并发送 `/digest` 测试
4. 观察日志，确认抓取和分析都能正常进行
5. 根据日志调整 `ARTICLE_MAX_CHARS` 和 `LLM_CONTEXT_LIMIT`

祝您使用愉快！有问题请查看日志或提交 Issue。 🎉
