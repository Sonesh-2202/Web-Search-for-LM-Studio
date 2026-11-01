"""Live integration check for smart_search with real web data."""
import asyncio
import sys
import time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


async def test_live():
    from mcp_internet.tools.search import smart_search
    from mcp_internet.utils.cache import cache_clear

    await cache_clear()

    print("=" * 60)
    print("LIVE INTEGRATION TEST - smart_search")
    print("=" * 60)

    start = time.time()
    result = await smart_search("Python programming language", max_sources=2)
    elapsed = time.time() - start
    print(f"⏱️ Time: {elapsed:.1f}s")
    print(f"📏 Length: {len(result)} chars")
    has_content = len(result) > 500 and "Error" not in result[:50]
    print(f"{'✅' if has_content else '❌'} Has substantial content: {has_content}")
    print(f"\n--- Preview ---\n{result[:500]}\n--- End ---\n")

    start = time.time()
    await smart_search("Python programming language", max_sources=2)
    elapsed_cached = time.time() - start
    print(f"Cached response: {elapsed_cached:.3f}s (initial: {elapsed:.1f}s)")
    print(f"{'✅' if elapsed_cached < 0.5 else '❌'} Cache working: {elapsed_cached < 0.5}")


asyncio.run(test_live())
