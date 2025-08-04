#!/usr/bin/env python3
"""
Example script demonstrating the async-bash-mcp server usage.
This shows how to use the MCP tools for spawning and managing processes.
"""

import asyncio
import json
from mcp import ClientSession
from mcp.client.stdio import stdio_client


async def demo_async_bash_mcp():
    """Demonstrate the async-bash-mcp functionality"""
    print("🚀 Starting async-bash-mcp demo...")

    # Start the MCP server as a subprocess
    server_params = {"command": "uv", "args": ["run", "async-bash-mcp"]}

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("✅ Connected to MCP server")

            # List available tools
            tools_result = await session.list_tools()
            print(f"📋 Available tools: {[tool.name for tool in tools_result.tools]}")

            # Test 1: Spawn a simple command
            print("\n🔧 Test 1: Spawning a simple echo command")
            spawn_result = await session.call_tool(
                "spawn", {"command": "echo 'Hello from async-bash-mcp!'"}
            )
            process_id = spawn_result.content[0].text
            process_data = json.loads(process_id)
            pid = process_data["id"]
            print(f"   Spawned process with ID: {pid}")

            # Wait a moment and poll the result
            await asyncio.sleep(0.1)
            poll_result = await session.call_tool("poll", {"ID": pid})
            poll_data = json.loads(poll_result.content[0].text)
            print(f"   Output: {poll_data['stdout'].strip()}")
            print(f"   Finished: {poll_data['finished']}")

            # Test 2: Spawn a long-running command
            print("\n⏱️  Test 2: Spawning a long-running command")
            long_spawn_result = await session.call_tool(
                "spawn",
                {"command": "for i in {1..5}; do echo 'Step $i'; sleep 0.5; done"},
            )
            long_process_data = json.loads(long_spawn_result.content[0].text)
            long_pid = long_process_data["id"]
            print(f"   Spawned long-running process with ID: {long_pid}")

            # List all processes
            print("\n📋 Listing all processes:")
            list_result = await session.call_tool("list_processes", {})
            processes_data = json.loads(list_result.content[0].text)
            for proc in processes_data["processes"]:
                print(
                    f"   ID: {proc['ID']}, Command: {proc['command']}, Done: {proc['done']}"
                )

            # Poll the long-running process multiple times to see incremental output
            print(
                f"\n🔍 Polling process {long_pid} multiple times for incremental output:"
            )
            for i in range(3):
                await asyncio.sleep(1.5)
                poll_result = await session.call_tool("poll", {"ID": long_pid})
                poll_data = json.loads(poll_result.content[0].text)
                if poll_data["stdout"]:
                    print(f"   Poll {i + 1}: {poll_data['stdout'].strip()}")
                print(f"   Finished: {poll_data['finished']}")
                if poll_data["finished"]:
                    print(f"   Exit code: {poll_data.get('exitCode', 'N/A')}")
                    break

            # Test 3: Test working directory
            print("\n📁 Test 3: Testing working directory")
            cwd_spawn_result = await session.call_tool(
                "spawn", {"command": "pwd", "cwd": "/tmp"}
            )
            cwd_process_data = json.loads(cwd_spawn_result.content[0].text)
            cwd_pid = cwd_process_data["id"]

            await asyncio.sleep(0.1)
            cwd_poll_result = await session.call_tool("poll", {"ID": cwd_pid})
            cwd_poll_data = json.loads(cwd_poll_result.content[0].text)
            print(f"   Working directory: {cwd_poll_data['stdout'].strip()}")

            print("\n✅ Demo completed successfully!")


if __name__ == "__main__":
    asyncio.run(demo_async_bash_mcp())
