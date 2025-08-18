# async-bash-mcp

[![pypi](https://img.shields.io/pypi/v/async-bash-mcp)](https://pypi.org/project/async-bash-mcp/) [![Test](https://github.com/xhuw/async-bash-mcp/actions/workflows/test.yaml/badge.svg)](https://github.com/xhuw/async-bash-mcp/actions/workflows/test.yaml)

An MCP server for spawning and managing bash commands asynchronously. Run multiple shell commands in parallel and check their progress independently.

## Usage with opencode

Add to your `opencode.json` config to replace the bash tool with async-bash-mcp:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "tools": {
    "bash": false
  },
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

## Why async bash?

When working with long-running commands like builds, tests, or servers, the agent needs to:
- Monitor progress incrementally without committing to a fixed timeout
- Run multiple commands in parallel and check each independently
- Make decisions about continuing or terminating based on partial output
- Process real-time feedback as commands generate output

This tool provides the agent with better information for decision-making, leading to faster task completion and fewer confused responses.

**Key advantages over the built-in bash tool:**
- **Better decision making**: Agents can see partial output and make informed choices about continuing or terminating
- **Parallel execution**: Run multiple commands simultaneously
- **No timeout guessing**: Check progress incrementally instead of setting timeouts upfront
- **Faster iterations**: No waiting for arbitrary timeouts when errors are already visible

This tool is designed to replace opencode's bash tool for any scenario involving potentially long-running commands, giving agents the information they need to make better decisions and save you time.

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
