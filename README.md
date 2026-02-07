# telegram-news-aggregator

A small Telegram bot that aggregates multiple Telegram channel RSS feeds (via RSSHub), sends combined news to an LLM for analysis, and returns a digest to a specified Telegram user.

Features

- Fetch RSS for Telegram channels via RSSHub (with fallback support)
- Manage subscriptions stored in `subscriptions.json`
- Aggregate and analyze multi-source news using an LLM (OpenAI-compatible)
- **Intelligent token management**: automatically truncates input when approaching LLM context limits
- **Continuation handling**: attempts to continue LLM output if truncated mid-response
- **Non-blocking I/O**: uses `asyncio.run_in_executor` to prevent blocking the event loop
- Telegram bot commands for manual operations
- Logging and optional remote error reporting

Requirements

- Python 3.8+
- See `requirements.txt` for Python packages

Quickstart (local)

1. Create and activate a virtual environment (macOS/zsh):

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

2. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3. Configure environment variables:
    - Copy `.env.example` to `.env` and fill in values, or set env vars directly.

    **Required:**
    - `BOT_TOKEN`: Telegram bot token
    - `CHAT_ID`: your Telegram chat id (bot restricts commands to this ID)
    - `LLM_API_KEY`: OpenAI API key (or compatible)

    **Optional:**
    - `LLM_BASE_URL`: default `https://api.openai.com/v1`
    - `LOG_LEVEL`: `INFO`/`DEBUG`/etc. (default: `INFO`)
    - `LOG_FILE`: path to write logs (e.g., `./logs/app.log`)
    - `ERROR_REPORT_URL`: optional endpoint to POST error reports
    - `RSSHUB_BASE_URL`: base URL of an RSSHub instance (default: `https://rsshub.app`)
    - `RSSHUB_FALLBACKS`: optional comma-separated fallback RSSHub instances to try if the primary is blocked or returns no entries
    - `ARTICLE_MAX_CHARS`: max characters per article before truncation (default: `800`)
    - `LLM_CONTEXT_LIMIT`: estimated LLM context limit in characters, ~1 token per 4 chars (default: `120000`)

4. Start the bot:

    ```bash
    python main.py
    ```

Bot Commands

- `/start` — greeting
- `/digest` — (restricted to CHAT_ID) fetch and analyze current channels
- `/list_subs` — list saved subscriptions
- `/add_sub <channel_id>` — add a subscription
- `/fetch <channel_id> [limit]` — (restricted to CHAT_ID) fetch and show the latest articles from a single subscription via RSSHub (default limit=5)

Files of Interest

- `main.py` — entrypoint and Telegram handlers
- `fetcher.py` — subscription management and RSS fetching with RSSHub fallback support
- `analyzer.py` — intelligent LLM prompt building with token estimation, continuation, and async execution
- `config.py` — reads env vars and default channels
- `logger.py` — logging and optional remote error reporting

Analyzer Optimizations

The analyzer module now includes several improvements:

1. **Token Estimation**: estimates prompt size using character count (1 token ≈ 4 chars) and automatically truncates articles if approaching the LLM context limit.
2. **Multi-attempt Retry**: if LLM returns empty content due to context limits, automatically retries with more aggressive truncation.
3. **Continuation on Truncation**: if LLM output is cut short (finish_reason="length") but has partial content, attempts to request continuation of the analysis.
4. **Non-blocking Execution**: all LLM and network calls run in a thread pool executor to prevent blocking the async event loop.

Deployment

- Use environment variables provided by your hosting provider.
- `Procfile` is included for platforms like Heroku/Zeabur.

Security

- Do not commit real secrets into the repo. `.env` is included in `.gitignore`.

Notes & Possible Future Improvements

- RSSHub fallback strategy is active; monitor logs to see which instances are available/reliable in your region.
- Consider configuring your own RSSHub instance for reliability (see https://github.com/DIYgod/RSSHub).
- Subscription storage uses local JSON file; for concurrent access, consider migrating to SQLite or Redis.
- Event loop may still be briefly occupied by `get_channel_news()` (synchronous); consider wrapping it in `run_in_executor` if needed for very high concurrency.

License

- MIT (add license file if desired)
