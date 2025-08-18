import asyncio
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

import threading
import re
from pathlib import Path
from pydantic import BaseModel

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession


@dataclass
class ProcessInfo:
    id: int
    command: str
    process: asyncio.subprocess.Process
    start_time: float
    cwd: Optional[str]
    stdout_buffer: str = ""
    stderr_buffer: str = ""
    stdout_position: int = 0
    stderr_position: int = 0
    accessed: bool = False
    finished: bool = False
    exit_code: Optional[int] = None


class ProcessManager:
    # Global counter for unique process IDs across all sessions
    _global_next_id = 1
    _global_id_lock = threading.Lock()

    def __init__(self):
        self._processes: Dict[int, ProcessInfo] = {}
        self._lock = threading.Lock()

    @classmethod
    def _get_next_global_id(cls) -> int:
        with cls._global_id_lock:
            current_id = cls._global_next_id
            cls._global_next_id += 1
            return current_id

    def _get_next_id(self) -> int:
        return self._get_next_global_id()

    def _validate_command(self, command: str) -> None:
        """Validate command for security issues"""
        if not command or not command.strip():
            raise ValueError("Command cannot be empty")

        # Basic length check to prevent extremely long commands
        if len(command) > 10000:
            raise ValueError("Command too long (max 10000 characters)")

        # Check for potentially dangerous patterns
        dangerous_patterns = [
            r"rm\s+-rf\s+/",  # rm -rf /
            r":\(\)\{\s*:\|:\s*&\s*\};:",  # fork bomb
            r"dd\s+if=/dev/zero",  # disk filling
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                raise ValueError(
                    f"Command contains potentially dangerous pattern: {pattern}"
                )

    def _validate_cwd(self, cwd: Optional[str]) -> Optional[str]:
        """Validate and normalize working directory path"""
        if cwd is None:
            return None

        if not cwd.strip():
            raise ValueError("Working directory cannot be empty string")

        try:
            # Resolve and validate path
            path = Path(cwd).resolve()

            # Check if path exists and is a directory
            if not path.exists():
                raise ValueError(f"Working directory does not exist: {cwd}")
            if not path.is_dir():
                raise ValueError(f"Working directory is not a directory: {cwd}")

            # Convert back to string
            return str(path)
        except (OSError, ValueError) as e:
            raise ValueError(f"Invalid working directory: {e}")

    async def spawn_process(self, command: str, cwd: Optional[str] = None) -> int:
        # Validate inputs
        self._validate_command(command)
        validated_cwd = self._validate_cwd(cwd)

        shell = os.environ.get("SHELL", "/bin/bash")

        # Use the user's shell to execute the command
        proc = await asyncio.create_subprocess_exec(
            shell,
            "-c",
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=validated_cwd,
        )

        process_id = self._get_next_id()
        process_info = ProcessInfo(
            id=process_id,
            command=command,
            process=proc,
            start_time=time.time(),
            cwd=validated_cwd,
        )

        with self._lock:
            self._processes[process_id] = process_info
            # Start background task to read output while holding lock
            asyncio.create_task(self._read_process_output(process_info))

        return process_id

    async def _read_process_output(self, process_info: ProcessInfo):
        async def read_stream(stream, buffer_attr, position_attr):
            while True:
                try:
                    data = await stream.read(1024)
                    if not data:
                        break

                    with self._lock:
                        current_buffer = getattr(process_info, buffer_attr)
                        setattr(
                            process_info,
                            buffer_attr,
                            current_buffer + data.decode("utf-8", errors="replace"),
                        )
                except Exception:
                    break

        # Read stdout and stderr concurrently
        await asyncio.gather(
            read_stream(
                process_info.process.stdout, "stdout_buffer", "stdout_position"
            ),
            read_stream(
                process_info.process.stderr, "stderr_buffer", "stderr_position"
            ),
            return_exceptions=True,
        )

        # Wait for process to complete
        exit_code = await process_info.process.wait()

        with self._lock:
            process_info.finished = True
            process_info.exit_code = exit_code

    def list_processes(self) -> List[Dict[str, Union[int, str, bool]]]:
        with self._lock:
            # Clean up accessed processes - create a copy to avoid modification during iteration
            processes_copy = dict(self._processes)
            to_remove = [pid for pid, proc in processes_copy.items() if proc.accessed]
            for pid in to_remove:
                if pid in self._processes:  # Double-check it still exists
                    del self._processes[pid]

            return [
                {"ID": proc.id, "command": proc.command, "done": proc.finished}
                for proc in self._processes.values()
            ]

    async def poll_process(
        self, process_id: int, wait_ms: int = 0, terminate: bool = False
    ) -> Dict[str, Union[str, float, bool, int]]:
        with self._lock:
            if process_id not in self._processes:
                raise ValueError(f"Process {process_id} not found")

            process_info = self._processes[process_id]

        # Terminate process if requested
        if terminate and not process_info.finished:
            try:
                process_info.process.terminate()
                await asyncio.wait_for(process_info.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process_info.process.kill()
                await process_info.process.wait()

            # Update finished status after termination
            with self._lock:
                process_info.finished = True
                if process_info.exit_code is None:
                    process_info.exit_code = process_info.process.returncode

        # Wait for specified time or process completion
        if wait_ms > 0 and not process_info.finished:
            try:
                await asyncio.wait_for(
                    self._wait_for_finish(process_info), timeout=wait_ms / 1000.0
                )
            except asyncio.TimeoutError:
                pass

        with self._lock:
            # Get new output since last poll
            new_stdout = process_info.stdout_buffer[process_info.stdout_position :]
            new_stderr = process_info.stderr_buffer[process_info.stderr_position :]

            # Update positions
            process_info.stdout_position = len(process_info.stdout_buffer)
            process_info.stderr_position = len(process_info.stderr_buffer)


            elapsed_time = (time.time() - process_info.start_time) * 1000

            result = {
                "stdout": new_stdout,
                "stderr": new_stderr,
                "elapsedTime": elapsed_time,
                "finished": process_info.finished,
            }

            if process_info.finished:
                # Mark as accessed
                process_info.accessed = True
                process_info.stdout_buffer = ""
                process_info.stderr_buffer = ""
                result["exitCode"] = process_info.exit_code

            return result

    async def _wait_for_finish(self, process_info: ProcessInfo):
        while not process_info.finished:
            await asyncio.sleep(0.1)


# Pydantic models for structured output
class SpawnResult(BaseModel):
    id: int


class ProcessListItem(BaseModel):
    ID: int
    command: str
    done: bool


class ListResult(BaseModel):
    processes: List[ProcessListItem]


class PollResult(BaseModel):
    stdout: str
    stderr: str
    elapsedTime: float
    finished: bool
    exitCode: Optional[int] = None


# Client-based process manager storage
client_managers: Dict[str, ProcessManager] = {}
client_lock = threading.Lock()


def get_client_process_manager(client_id: str) -> ProcessManager:
    """Get or create a ProcessManager for a specific client"""
    with client_lock:
        if client_id not in client_managers:
            client_managers[client_id] = ProcessManager()
        return client_managers[client_id]


def cleanup_client_manager(client_id: str):
    """Clean up ProcessManager when client disconnects"""
    with client_lock:
        if client_id in client_managers:
            pm = client_managers[client_id]
            # Terminate all processes for this client
            with pm._lock:
                for process_info in pm._processes.values():
                    if not process_info.finished:
                        try:
                            process_info.process.terminate()
                        except ProcessLookupError:
                            pass  # Process already terminated
            del client_managers[client_id]


@asynccontextmanager
async def lifespan(app):
    yield {"client_managers": client_managers}


# Create FastMCP server
mcp = FastMCP("async-bash-mcp", lifespan=lifespan)


@mcp.tool()
async def spawn(
    command: str, cwd: Optional[str] = None, ctx: Context[ServerSession, dict] = None
) -> SpawnResult:
    """
    Launch a bash command asynchronously in a subshell.

    Returns a unique process ID that can be used to check progress with the poll tool. **ALWAYS POLL THE PROCESS AFTER SPAWNING**.

    Multiple commands can be spawned in parallel and independently polled. If the task requires running independent bash commands, run them in parrallel.

    Example:

        1. User requests the results of `test a` and `test b`
        2. spawn `test a`
        3. spawn `test b`
        4. while test a is running: poll test a
        5. while test b is running: poll test b

    Args:
        command: The bash command to execute
        cwd: Optional working directory path (defaults to current directory)

    Returns:
        SpawnResult with the unique process ID
    """
    pm = get_client_process_manager(ctx.client_id)
    process_id = await pm.spawn_process(command, cwd)
    return SpawnResult(id=process_id)


@mcp.tool()
async def list_processes(ctx: Context[ServerSession, dict] = None) -> ListResult:
    """
    List all currently running or recently finished processes. Processes are removed from this list once their results have been accessed via the poll tool.

    Returns:
        ListResult containing list of processes with their ID, command, and completion status
    """
    pm = get_client_process_manager(ctx.client_id)
    processes = pm.list_processes()
    return ListResult(processes=[ProcessListItem(**proc) for proc in processes])


@mcp.tool()
async def poll(
    process_id: int,
    wait: int,
    terminate: bool = False,
    ctx: Context[ServerSession, dict] = None,
) -> PollResult:
    """
    Check the progress of a spawned process. Returns stdout/stderr output produced since the last poll call. Can optionally wait for completion or terminate the process.

    **NEVER LEAVE A PROCESS RUNNING UNPOLLLED**. Always poll the process after spawning it to ensure resources are cleaned up.

    **TERMINATE THE PROCESS IF YOU NO LONGER NEED IT**. If you don't poll the process, it will continue running indefinitely.

    Args:
        process_id: The process ID returned by spawn
        wait: Maximum milliseconds to wait for process completion. Must be greater that 0
        terminate: If True, terminate the process with SIGTERM before returning results

    Returns:
        PollResult with incremental stdout/stderr, elapsed time, and completion status
    """
    if wait <= 0:
        raise ValueError("Wait time must be greater than 0 milliseconds")
    pm = get_client_process_manager(ctx.client_id)
    try:
        result = await pm.poll_process(process_id, wait, terminate)
        return PollResult(**result)
    except ValueError as e:
        raise ValueError(str(e))


def main():
    """Entry point for the MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Async Bash MCP Server")
    parser.add_argument(
        "--transport", default="stdio", choices=["stdio", "sse", "streamable-http"]
    )
    args = parser.parse_args()

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
