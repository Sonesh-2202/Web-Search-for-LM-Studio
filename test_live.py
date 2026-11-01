"""Live integration check for fresh smart_search results."""
import asyncio
import sys
import time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


async def test_live():
    from mcp_internet.tools.search import smart_search

    print("=" * 60)
    print("LIVE INTEGRATION TEST - smart_search")
    print("=" * 60)

    start = time.perf_counter()
    result = await smart_search("Python programming language", max_sources=2)
    elapsed = time.perf_counter() - start
    print(f"⏱️ Time: {elapsed:.1f}s")
    print(f"📏 Length: {len(result)} chars")
    has_content = len(result) > 500 and "No fresh results" not in result[:100]
    has_clock = "Fresh search performed at" in result and "UTC:" in result
    has_source = "URL: https://" in result
    print(f"{'✅' if has_content else '❌'} Has substantial content: {has_content}")
    print(f"{'✅' if has_clock else '❌'} Includes local/UTC search timestamp: {has_clock}")
    print(f"{'✅' if has_source else '❌'} Includes source URLs: {has_source}")
    print(f"\n--- Preview ---\n{result[:500]}\n--- End ---\n")


asyncio.run(test_live())
