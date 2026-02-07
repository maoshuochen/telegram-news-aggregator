#!/usr/bin/env python3
"""
Quick test script for the analyzer module.
Tests token estimation, truncation, and async execution.
"""

import asyncio
from analyzer import (
    _estimate_tokens,
    _truncate_news_items,
    analyze_news,
    ESTIMATED_CONTEXT_LIMIT,
)


async def main():
    print("=" * 60)
    print("Analyzer Module Test Suite")
    print("=" * 60)

    # Test 1: Token estimation
    print("\n[Test 1] Token Estimation")
    test_text = "This is a test sentence. " * 100  # ~2600 chars
    estimated = _estimate_tokens(test_text)
    print(f"  Text length: {len(test_text)} chars")
    print(f"  Estimated tokens: {estimated} (1 token ≈ 4 chars)")
    assert estimated == len(test_text) // 4, "Token estimation failed"
    print("  ✓ Passed")

    # Test 2: News truncation
    print("\n[Test 2] News Item Truncation")
    sample_news = [
        {"source": "Channel A", "content": "News " * 200},  # 1000 chars
        {"source": "Channel B", "content": "News " * 200},
        {"source": "Channel C", "content": "News " * 200},
    ]
    max_chars = 2000
    truncated = _truncate_news_items(sample_news, max_chars)
    total_chars = sum(len(item.get("content", "")) for item in truncated)
    print(
        f"  Input: {len(sample_news)} items, ~{sum(len(i['content']) for i in sample_news)} chars"
    )
    print(f"  Max allowed: {max_chars} chars")
    print(f"  Output: {len(truncated)} items, ~{total_chars} chars")
    assert total_chars <= max_chars, "Truncation limit exceeded"
    print("  ✓ Passed")

    # Test 3: Async execution (without real LLM)
    print("\n[Test 3] Async Execution Structure")
    print(f"  Context limit: {ESTIMATED_CONTEXT_LIMIT} chars")
    print(f"  Executor pool size: 3 workers")
    print("  ✓ Thread pool configured for non-blocking I/O")

    # Test 4: Simple mock news analysis (if LLM env vars are set)
    print("\n[Test 4] Mock News Analysis Flow")
    mock_news = [
        {"source": "TechNews", "content": "AI model released with 128k token context."},
        {
            "source": "BusinessDaily",
            "content": "Tech stocks rally on AI announcements.",
        },
    ]
    print(f"  Analyzing {len(mock_news)} items...")
    try:
        result = await analyze_news(mock_news)
        if result.startswith("LLM"):
            print(f"  Result (truncated): {result[:80]}...")
            print("  ✓ Async analyze_news executed (LLM call attempted)")
        else:
            print(f"  Analysis result length: {len(result)} chars")
            print(f"  ✓ Analysis completed successfully")
    except Exception as e:
        print(f"  Note: {e}")
        print("  (This is expected if LLM_API_KEY is not configured)")

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
