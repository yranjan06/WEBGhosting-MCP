import asyncio
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    server_params = StdioServerParameters(
        command="./tmp_webmcp",
        args=[],
        env=os.environ.copy()
    )

    print("Connecting to WebMCP Server...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Connected! Available tools:")
            tools = await session.list_tools()
            for t in tools.tools:
                print(f" - {t.name}")
                
            print("\n1. Testing Memory Store...")
            await session.call_tool("memorize_data", {"key": "test_key", "value": {"hello": "world"}})
            mem = await session.call_tool("recall_data", {"key": "test_key"})
            print(f"Retrieved memory: {mem.content[0].text}")
            
            print("\n2. Testing Labeled Snapshot (navigating to example.com first)...")
            await session.call_tool("browse", {"url": "https://example.com"})
            snap = await session.call_tool("capture_labeled_snapshot", {})
            content = snap.content[0].text
            print(f"Snapshot received! Length: {len(content)} characters")
            print("Contains labels? ", "e1" in content)
            
            print("\nEverything looks good!")

if __name__ == "__main__":
    asyncio.run(main())
