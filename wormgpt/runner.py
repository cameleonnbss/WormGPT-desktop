"""Local command execution for the agent (Claude-Code style) feature.

Runs a single shell command in a working directory with a hard timeout and a
bounded output, so a misbehaving model cannot hang the machine or flood the
context. Commands are only ever executed when the user enabled the feature
and (in "ask" mode) approved the exact command.
"""

import subprocess

DEFAULT_TIMEOUT = 120
MAX_TIMEOUT = 600
MAX_OUTPUT = 8000


def run_command(command, cwd=None, timeout=DEFAULT_TIMEOUT, max_output=MAX_OUTPUT):
    """Execute ``command`` via the system shell.

    Returns a short status string that is fed back to the model:
    normal output, "[exit N]" on non-zero exit, timeout or error notes.
    ``timeout`` is clamped to [1, MAX_TIMEOUT] so a model cannot request an
    effectively infinite run.
    """
    try:
        timeout = max(1, min(MAX_TIMEOUT, int(timeout or DEFAULT_TIMEOUT)))
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT
    try:
        proc = subprocess.run(
            command, shell=True, cwd=cwd or None,
            capture_output=True, text=True, timeout=timeout,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        out = out.strip()
        if len(out) > max_output:
            out = out[:max_output] + "\n… (output truncated)"
        if proc.returncode != 0:
            return f"[exit {proc.returncode}]\n{out}" if out else f"[exit {proc.returncode}]"
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return f"[command timed out after {timeout}s]"
    except Exception as exc:
        return f"[error: {exc}]"


RUN_COMMAND_TOOL = {
    "type": "function",
    "function": {
        "name": "run_command",
        "description": (
            "Run a shell command on the user's machine (Windows shell). "
            "Use it to inspect files, run scripts, search the system, test "
            "code, etc. Prefer single, focused commands. The output is "
            "returned to you."),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The exact command to run.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Directory to run it in (default: working directory).",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Seconds before the command is killed (default 120).",
                },
            },
            "required": ["command"],
        },
    },
}