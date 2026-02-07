# telegram-news-aggregator

A small Telegram bot that aggregates multiple Telegram channel RSS feeds (via RSSHub), sends combined news to an LLM for analysis, and returns a digest to a specified Telegram user.

Features

- RSSHub fetch with fallback instances
- Subscriptions stored in `subscriptions.json`
- LLM analysis with truncation, retry, and continuation handling
- Non-blocking LLM calls via thread pool
- Telegram bot commands and logging

Requirements

- Python 3.8+

Quickstart (local)

1. Create and activate a virtual environment:

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

2. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3. Configure environment variables (copy `.env.example` to `.env`, or set directly):

    Required:
    - `BOT_TOKEN`
    - `CHAT_ID`
    - `LLM_API_KEY`

    Optional:
    - `LLM_BASE_URL` (default `https://api.openai.com/v1`)
    - `LLM_MODEL` (default `gpt-5-mini`)
    - `LLM_MAX_TOKENS` (default `128000`)
    - `LLM_CONTINUATION_MAX_TOKENS` (default `128000`)
    - `LLM_TEMPERATURE` (default `0.4`)
    - `LLM_THREADPOOL_WORKERS` (default `3`)
    - `LLM_TIMEOUT` (default `90`)
    - `LLM_RETRIES` (default `2`)
    - `LLM_RETRY_BACKOFF` (default `1.5`)
    - `LOG_LEVEL` (default `INFO`)
    - `LOG_FILE` (e.g. `./logs/app.log`)
    - `ERROR_REPORT_URL`
    - `RSSHUB_BASE_URL` (default `https://rsshub.app`)
    - `RSSHUB_FALLBACKS` (comma-separated)
    - `RSSHUB_TIMEOUT` (seconds, default `10`)
    - `RSS_ITEMS_PER_CHANNEL` (default `20`)
    - `ARTICLE_MAX_CHARS` (default `1600`)
    - `LLM_CONTEXT_LIMIT` (default `1600000`)
    - `LLM_COMPLETION_LIMIT` (default `512000`)

4. Start the bot:

    ```bash
    python main.py
    ```

Bot Commands

- `/start` — greeting
- `/digest` — fetch and analyze current subscriptions (restricted to `CHAT_ID`)
- `/list_subs` — list saved subscriptions
- `/add_sub <channel_id>` — add a subscription
- `/fetch <channel_id> [limit]` — fetch latest articles from a single subscription

Files of Interest

- `main.py` — entrypoint and Telegram handlers
- `fetcher.py` — subscription management and RSS fetching
- `analyzer.py` — LLM prompt building, truncation, retry, continuation
- `config.py` — env config and defaults
- `logger.py` — logging and optional remote error reporting

Notes

- If `subscriptions.json` does not exist, it will be initialized with `DEFAULT_CHANNELS` from `config.py`. An empty list is respected as “no subscriptions”.
- `/digest` fetches subscriptions in parallel with a per-request timeout (`RSSHUB_TIMEOUT`).
- For reliability, consider running your own RSSHub instance.

RSSHub Fallback Tips

- Set `RSSHUB_FALLBACKS` with multiple instances to reduce downtime, for example:
  `RSSHUB_FALLBACKS=https://rsshub.app,https://rsshub.rssforever.com`
- If you see SSL errors (e.g. `SSLEOFError`) on macOS with LibreSSL, consider using a Homebrew Python build linked against OpenSSL, or switch to a different RSSHub instance.

License

- MIT (add license file if desired)

Manual Sanity Check

Run a minimal end-to-end check (requires env vars configured):

```bash
python -c "import asyncio; from analyzer import analyze_news; news=[{'source':'Test','content':'AI model released.'}]; print(asyncio.run(analyze_news(news))[:200])"
```
