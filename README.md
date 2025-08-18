# async-bash-mcp

[![pypi](https://img.shields.io/pypi/v/async-bash-mcp)](https://pypi.org/project/async-bash-mcp/) [![Test](https://github.com/xhuw/async-bash-mcp/actions/workflows/test.yaml/badge.svg)](https://github.com/xhuw/async-bash-mcp/actions/workflows/test.yaml)

An MCP server for spawning and managing bash commands asynchronously. Run multiple shell commands in parallel and check their progress independently.

## Usage with opencode

Add to your `opencode.json` config:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "async-bash": {
      "type": "local",
      "command": ["uvx", "async-bash-mcp"],
      "enabled": true
    }
  }
}
```

Then use commands like:
- "Spawn a long-running build in the background"
- "Run tests in parallel and show me the results"
- "Start a server and tell me when it's ready"

## Tools

**spawn** - Launch a bash command asynchronously
- `command` (str): The bash command to run
- `cwd` (str, optional): Working directory path
- Returns a process ID for tracking

**list_processes** - Show all running/recent processes
- No parameters
- Returns array of `{"ID": int, "command": str, "done": bool}`

**poll** - Check progress of a spawned process
- `process_id` (int): ID from spawn command
- `wait` (int): Wait time in milliseconds
- `terminate` (bool, optional): Kill process before returning results
- Returns `{"stdout": str, "stderr": str, "elapsedTime": float, "finished": bool, "exitCode": int}`

## Installation

```bash
uvx async-bash-mcp
```
