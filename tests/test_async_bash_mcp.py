import asyncio
import pytest
import tempfile
import time
import uuid

from async_bash_mcp import (
    ProcessManager,
    spawn,
    list_processes,
    poll,
    SpawnResult,
    ListResult,
    PollResult,
)


class MockRequestContext:
    def __init__(self):
        self.meta = None


class MockContext:
    def __init__(self, client_id=None):
        if client_id is None:
            client_id = str(uuid.uuid4())  # Generate unique client ID
        self.client_id = client_id
        self.request_context = MockRequestContext()

    async def report_progress(self, progress, message=None):
        """Mock progress reporting method"""
        pass


@pytest.fixture
def process_manager():
    return ProcessManager()


@pytest.fixture
def mock_context():
    return MockContext()


@pytest.fixture
def mock_context_2():
    return MockContext()


@pytest.mark.asyncio
async def test_process_manager_spawn_simple_command(process_manager):
    """Test spawning a simple echo command"""
    process_id = await process_manager.spawn_process("echo 'Hello World'")
    assert isinstance(process_id, int)
    assert process_id > 0

    # Wait a bit for process to complete
    await asyncio.sleep(0.1)

    # Check process is in the list
    processes = process_manager.list_processes()
    assert len(processes) == 1
    assert processes[0]["ID"] == process_id
    assert processes[0]["command"] == "echo 'Hello World'"


@pytest.mark.asyncio
async def test_process_manager_multiple_processes(process_manager):
    """Test spawning multiple processes"""
    id1 = await process_manager.spawn_process("echo 'First'")
    id2 = await process_manager.spawn_process("echo 'Second'")

    assert id1 != id2

    processes = process_manager.list_processes()
    assert len(processes) == 2

    ids = [p["ID"] for p in processes]
    assert id1 in ids
    assert id2 in ids


@pytest.mark.asyncio
async def test_process_manager_poll_output(process_manager):
    """Test polling process output"""
    process_id = await process_manager.spawn_process("echo 'Test Output'")

    # Wait for process to complete
    await asyncio.sleep(0.2)

    result = await process_manager.poll_process(process_id, wait_ms=100)

    assert result["stdout"].strip() == "Test Output"
    assert result["stderr"] == ""
    assert result["finished"] is True
    assert result["exitCode"] == 0
    assert result["elapsedTime"] > 0


@pytest.mark.asyncio
async def test_process_manager_incremental_output(process_manager):
    """Test that polling returns incremental output"""
    # Use a command that produces output in stages
    process_id = await process_manager.spawn_process(
        "echo 'First'; sleep 0.1; echo 'Second'"
    )

    # First poll - might get partial output
    await asyncio.sleep(0.05)
    result1 = await process_manager.poll_process(process_id)

    # Second poll - should get remaining output
    await asyncio.sleep(0.2)
    result2 = await process_manager.poll_process(process_id)

    # Combined output should contain both lines
    combined_stdout = result1["stdout"] + result2["stdout"]
    assert "First" in combined_stdout
    assert "Second" in combined_stdout

    # Second poll should not repeat first poll's output
    assert result1["stdout"] != result2["stdout"]


@pytest.mark.asyncio
async def test_process_manager_working_directory(process_manager):
    """Test spawning process with custom working directory"""
    with tempfile.TemporaryDirectory() as temp_dir:
        process_id = await process_manager.spawn_process("pwd", cwd=temp_dir)

        await asyncio.sleep(0.1)
        result = await process_manager.poll_process(process_id, wait_ms=100)

        assert temp_dir in result["stdout"]


@pytest.mark.asyncio
async def test_process_manager_terminate(process_manager):
    """Test terminating a long-running process"""
    # Start a long-running process
    process_id = await process_manager.spawn_process("sleep 10")

    # Terminate it immediately
    result = await process_manager.poll_process(process_id, wait_ms=100, terminate=True)

    assert result["finished"] is True
    # Process should be terminated (exit code may vary by system)
    assert "exitCode" in result


@pytest.mark.asyncio
async def test_process_manager_wait_timeout(process_manager):
    """Test waiting for process with timeout"""
    process_id = await process_manager.spawn_process("sleep 1")

    start_time = time.time()
    result = await process_manager.poll_process(process_id, wait_ms=200)
    elapsed = time.time() - start_time

    # Should timeout after ~200ms
    assert elapsed < 0.5
    assert result["finished"] is False


@pytest.mark.asyncio
async def test_process_manager_cleanup_accessed(process_manager):
    """Test that accessed processes are cleaned up from list"""
    process_id = await process_manager.spawn_process("echo 'test'")

    # Process should be in list
    processes = process_manager.list_processes()
    assert len(processes) == 1

    # Poll it (marks as accessed)
    await asyncio.sleep(0.1)
    await process_manager.poll_process(process_id)

    # Should be removed from list after next list call
    processes = process_manager.list_processes()
    assert len(processes) == 0


@pytest.mark.asyncio
async def test_process_manager_error_handling(process_manager):
    """Test error handling for invalid process ID"""
    with pytest.raises(ValueError, match="Process 999 not found"):
        await process_manager.poll_process(999)


@pytest.mark.asyncio
async def test_spawn_tool(mock_context):
    """Test the spawn MCP tool"""
    result = await spawn("echo 'Hello from tool'", ctx=mock_context)

    assert isinstance(result, SpawnResult)
    assert result.id > 0


@pytest.mark.asyncio
async def test_spawn_tool_with_cwd(mock_context):
    """Test spawn tool with working directory"""
    with tempfile.TemporaryDirectory() as temp_dir:
        result = await spawn("pwd", cwd=temp_dir, ctx=mock_context)
        assert isinstance(result, SpawnResult)


@pytest.mark.asyncio
async def test_list_tool(mock_context):
    """Test the list MCP tool"""
    # Spawn a process first
    await spawn("echo 'test'", ctx=mock_context)

    result = await list_processes(ctx=mock_context)

    assert isinstance(result, ListResult)
    assert len(result.processes) == 1
    assert result.processes[0].command == "echo 'test'"


@pytest.mark.asyncio
async def test_poll_tool(mock_context):
    """Test the poll MCP tool"""
    # Spawn a process
    spawn_result = await spawn("echo 'Poll test'", ctx=mock_context)

    # Wait and poll
    await asyncio.sleep(0.1)
    result = await poll(spawn_result.id, wait=100, ctx=mock_context)

    assert isinstance(result, PollResult)
    assert "Poll test" in result.stdout
    assert result.finished is True
    assert result.exitCode == 0


@pytest.mark.asyncio
async def test_poll_tool_with_wait(mock_context):
    """Test poll tool with wait parameter"""
    spawn_result = await spawn("sleep 0.1; echo 'Done'", ctx=mock_context)

    # Poll with wait
    result = await poll(spawn_result.id, wait=500, ctx=mock_context)

    assert result.finished is True
    assert "Done" in result.stdout


@pytest.mark.asyncio
async def test_poll_tool_with_terminate(mock_context):
    """Test poll tool with terminate parameter"""
    spawn_result = await spawn("sleep 10", ctx=mock_context)

    # Terminate immediately
    result = await poll(spawn_result.id, wait=100, terminate=True, ctx=mock_context)

    assert result.finished is True


@pytest.mark.asyncio
async def test_poll_tool_invalid_id(mock_context):
    """Test poll tool with invalid process ID"""
    with pytest.raises(ValueError):
        await poll(999, wait=100, ctx=mock_context)


@pytest.mark.asyncio
async def test_stderr_capture(process_manager):
    """Test that stderr is captured correctly"""
    process_id = await process_manager.spawn_process("echo 'error message' >&2")

    await asyncio.sleep(0.1)
    result = await process_manager.poll_process(process_id, wait_ms=100)

    assert "error message" in result["stderr"]
    assert result["stdout"] == ""


@pytest.mark.asyncio
async def test_shell_detection(process_manager):
    """Test that user's shell is used"""
    # This test assumes bash-like shell behavior
    process_id = await process_manager.spawn_process("echo $0")

    await asyncio.sleep(0.1)
    result = await process_manager.poll_process(process_id, wait_ms=100)

    # Should contain shell name (bash, zsh, etc.)
    assert any(
        shell in result["stdout"]
        for shell in ["/bin/bash", "/bin/zsh", "/bin/sh", "bash", "zsh"]
    )


@pytest.mark.asyncio
async def test_concurrent_processes(process_manager):
    """Test multiple concurrent processes"""
    # Start several processes concurrently
    tasks = []
    for i in range(5):
        task = process_manager.spawn_process(f"echo 'Process {i}'; sleep 0.1")
        tasks.append(task)

    process_ids = await asyncio.gather(*tasks)

    # All should have unique IDs
    assert len(set(process_ids)) == 5

    # Wait for completion
    await asyncio.sleep(0.3)

    # Check all processes
    for process_id in process_ids:
        result = await process_manager.poll_process(process_id, wait_ms=100)
        assert result["finished"] is True
        assert f"Process {process_ids.index(process_id)}" in result["stdout"]


@pytest.mark.asyncio
async def test_long_output_handling(process_manager):
    """Test handling of processes with large output"""
    # Generate a lot of output - use seq which is more portable
    process_id = await process_manager.spawn_process(
        "seq 1 100 | while read i; do echo 'Line '$i; done"
    )

    await asyncio.sleep(0.3)
    result = await process_manager.poll_process(process_id, wait_ms=100)

    assert result["finished"] is True
    assert "Line 1" in result["stdout"]
    assert "Line 100" in result["stdout"]
    # Should have 100 lines
    assert len([line for line in result["stdout"].split("\n") if line.strip()]) == 100


@pytest.mark.asyncio
async def test_session_isolation():
    """Test that different clients cannot access each other's processes"""
    context1 = MockContext("client_1")
    context2 = MockContext("client_2")

    # Spawn a process in client 1
    spawn_result1 = await spawn("echo 'Client 1 process'", ctx=context1)
    pid1 = spawn_result1.id

    # Spawn a process in client 2
    spawn_result2 = await spawn("echo 'Client 2 process'", ctx=context2)
    pid2 = spawn_result2.id

    # Client 1 should not be able to access client 2's process
    with pytest.raises(ValueError, match=f"Process {pid2} not found"):
        await poll(pid2, wait=100, ctx=context1)

    # Client 2 should not be able to access client 1's process
    with pytest.raises(ValueError, match=f"Process {pid1} not found"):
        await poll(pid1, wait=100, ctx=context2)

    # Each client should only see its own processes
    list1 = await list_processes(ctx=context1)
    list2 = await list_processes(ctx=context2)

    assert len(list1.processes) == 1
    assert len(list2.processes) == 1
    assert list1.processes[0].ID == pid1
    assert list2.processes[0].ID == pid2


@pytest.mark.asyncio
async def test_command_validation_security():
    """Test command validation security features"""
    process_manager = ProcessManager()

    # Test empty command
    with pytest.raises(ValueError, match="Command cannot be empty"):
        await process_manager.spawn_process("")

    with pytest.raises(ValueError, match="Command cannot be empty"):
        await process_manager.spawn_process("   ")

    # Test extremely long command
    long_command = "echo " + "a" * 10000
    with pytest.raises(ValueError, match="Command too long"):
        await process_manager.spawn_process(long_command)

    # Test dangerous patterns
    dangerous_commands = [
        "rm -rf /",
        ":(){ :|: & };:",  # fork bomb
        "dd if=/dev/zero of=/dev/sda",  # disk filling
    ]

    for cmd in dangerous_commands:
        with pytest.raises(ValueError, match="potentially dangerous pattern"):
            await process_manager.spawn_process(cmd)


@pytest.mark.asyncio
async def test_cwd_validation_security():
    """Test working directory validation security features"""
    process_manager = ProcessManager()

    # Test empty cwd
    with pytest.raises(ValueError, match="Working directory cannot be empty"):
        await process_manager.spawn_process("echo test", cwd="   ")

    # Test non-existent directory
    with pytest.raises(ValueError, match="Working directory does not exist"):
        await process_manager.spawn_process("echo test", cwd="/nonexistent/path")

    # Test file instead of directory
    with tempfile.NamedTemporaryFile() as tmp_file:
        with pytest.raises(ValueError, match="not a directory"):
            await process_manager.spawn_process("echo test", cwd=tmp_file.name)


@pytest.mark.asyncio
async def test_poll_parameter_consistency(mock_context):
    """Test that poll tool uses consistent parameter naming"""
    spawn_result = await spawn("echo 'test'", ctx=mock_context)

    await asyncio.sleep(0.1)
    # Should work with process_id parameter (not ID)
    result = await poll(spawn_result.id, wait=100, ctx=mock_context)

    assert result.finished is True
    assert "test" in result.stdout


@pytest.mark.asyncio
async def test_process_cleanup_on_disconnect():
    """Test that processes are properly cleaned up when client disconnects"""
    from async_bash_mcp import cleanup_client_manager, get_client_process_manager

    client_id = "test_client_cleanup"
    pm = get_client_process_manager(client_id)

    # Start a long-running process
    await pm.spawn_process("sleep 10")

    # Verify process is running
    processes = pm.list_processes()
    assert len(processes) == 1

    # Cleanup client
    cleanup_client_manager(client_id)

    # Verify process was terminated (process manager should be gone)
    # Getting a new manager should be empty
    new_pm = get_client_process_manager(client_id)
    assert len(new_pm.list_processes()) == 0


if __name__ == "__main__":
    pytest.main([__file__])
