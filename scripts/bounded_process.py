"""Run local child processes with a bounded lifetime for the entire process group."""

import asyncio
import locale
import math
import os
import signal
import subprocess
from collections.abc import Sequence
from pathlib import Path

_KILL_GRACE = 1.0


def _timeout(value: float) -> float:
    if not math.isfinite(value) or value <= 0:
        raise ValueError("timeout must be a finite positive number")
    return value


def _signal_group(pid: int, sig: signal.Signals) -> None:
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        pass


def run_bounded(
    command: Sequence[str], *, timeout: float, cwd: str | Path | None = None,
    input: str | bytes | None = None, text: bool = True, capture_output: bool = False,
    check: bool = False, env: dict[str, str] | None = None, terminate_grace: float = 1.0,
) -> subprocess.CompletedProcess:
    """Run a command, terminating then killing its group on timeout/interruption.

    Timeout raises subprocess.TimeoutExpired; nonzero status raises CalledProcessError
    only when check=True. The caller must handle failure of the command separately.
    """
    _timeout(timeout)
    _timeout(terminate_grace)
    process = subprocess.Popen(
        command, cwd=cwd, env=env, stdin=subprocess.PIPE if input is not None else None,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        text=text, start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(input=input, timeout=timeout)
    except BaseException:
        _signal_group(process.pid, signal.SIGTERM)
        try:
            process.communicate(timeout=terminate_grace)
        except (subprocess.TimeoutExpired, OSError, ValueError):
            pass
        finally:
            _signal_group(process.pid, signal.SIGKILL)
            try:
                process.communicate(timeout=_KILL_GRACE)
            except (subprocess.TimeoutExpired, OSError, ValueError):
                if process.poll() is None:
                    process.kill()
                try:
                    process.wait(timeout=_KILL_GRACE)
                except subprocess.TimeoutExpired:
                    pass
        raise
    completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if check:
        completed.check_returncode()
    return completed


async def _stop_async(process: asyncio.subprocess.Process, terminate_grace: float) -> None:
    _signal_group(process.pid, signal.SIGTERM)
    try:
        await asyncio.wait_for(process.communicate(), terminate_grace)
    except (asyncio.TimeoutError, OSError, ValueError):
        pass
    finally:
        _signal_group(process.pid, signal.SIGKILL)
        try:
            await asyncio.wait_for(process.communicate(), _KILL_GRACE)
        except (asyncio.TimeoutError, OSError, ValueError):
            if process.returncode is None:
                process.kill()
            try:
                await asyncio.wait_for(process.wait(), _KILL_GRACE)
            except asyncio.TimeoutError:
                pass


async def run_bounded_async(
    command: Sequence[str], *, timeout: float, cwd: str | Path | None = None,
    input: str | bytes | None = None, text: bool = True, capture_output: bool = False,
    check: bool = False, env: dict[str, str] | None = None, terminate_grace: float = 1.0,
) -> subprocess.CompletedProcess:
    """Asynchronous equivalent; cancellation waits for child-group cleanup."""
    _timeout(timeout)
    _timeout(terminate_grace)
    spawning = asyncio.create_task(asyncio.create_subprocess_exec(
        *command, cwd=cwd, env=env, stdin=asyncio.subprocess.PIPE if input is not None else None,
        stdout=asyncio.subprocess.PIPE if capture_output else None,
        stderr=asyncio.subprocess.PIPE if capture_output else None,
        start_new_session=True,
    ))
    try:
        process = await asyncio.shield(spawning)
    except asyncio.CancelledError:
        # The spawn can complete after cancellation; do not orphan that process.
        process = await spawning
        await _stop_async(process, terminate_grace)
        raise
    encoding = locale.getpreferredencoding(False)
    payload = input.encode(encoding) if text and isinstance(input, str) else input
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(payload), timeout)
    except BaseException as error:
        cleanup = asyncio.create_task(_stop_async(process, terminate_grace))
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            await cleanup
        if isinstance(error, asyncio.TimeoutError):
            raise subprocess.TimeoutExpired(command, timeout) from error
        raise
    if text:
        stdout = stdout.decode(encoding) if stdout is not None else None
        stderr = stderr.decode(encoding) if stderr is not None else None
    completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if check:
        completed.check_returncode()
    return completed
