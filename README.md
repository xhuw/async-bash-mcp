# MCP spawning and managing bash tasks

tools provided:

1. spawn : lauch a command
  - parameters:
    - command: str, the bash command to run
    - cwd: str, optional path to the cwd to use.
  - Spawns a bash command in a subshell asynchronously, returns a ID (int) of the newly launched task
2. list :
  - parameters: none
  - Returns a list of the currently running processes each is a dictionary of `[{"ID": int, "command": str, "done": bool}]`.
          Tasks will be removed from the list when their result has been accessed via `wait` or `poll`
3. poll, check the progress of a task
  - parameters: `ID: int` the command to check, `wait: int` wait for the process to finish executing or for `wait` ms to elapse. `terminate: bool = false` an optional parameter which triggers the command to be terminated with SIG_TERM before returning the command results
  - If poll is executed multiple times for a single process it will only return the stdout and stderr that was produced since the last call to poll (no duplicate outputs)
  - returns dictionary `{"stdout": str, "stderr": str, "elapsedTime": float, "finished": bool, "exitCode": int}` exitCode will only be present if `finished` is true. elapsedTime will be the number of milliseconds since the command started.

## Requirements

1. Must support multiple concurrent clients
2. Each tool must have a description which is well designed to be consumed by an LLM
3. Results should be presented in a format which is suitable for and LLM
4. Uses the users default shell (bash, zsh, fish)

## launching the MCP

This MCP is launched with `uv` via

```
uv run async-bash-mcp
```
