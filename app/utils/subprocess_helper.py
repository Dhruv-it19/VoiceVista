"""Helper utilities for subprocess execution on Windows."""
import subprocess
import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_command_async(cmd: list, check: bool = True) -> subprocess.CompletedProcess:
    """
    Run a command asynchronously using subprocess in a thread pool.
    This is Windows-compatible and avoids asyncio.create_subprocess_exec issues.

    Args:
        cmd: List of command arguments
        check: If True, raises exception on non-zero return code

    Returns:
        subprocess.CompletedProcess with stdout, stderr, and returncode
    """
    def run():
        return subprocess.run(
            cmd,
            capture_output=True,
            check=False  # We'll check manually
        )

    result = await asyncio.to_thread(run)

    if check and result.returncode != 0:
        error_msg = result.stderr.decode() if result.stderr else "Unknown error"
        raise Exception(f"Command failed with return code {result.returncode}: {error_msg}")

    return result
