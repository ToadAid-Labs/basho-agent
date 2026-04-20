import subprocess
import tempfile
from pathlib import Path

from core.tools import register_tool

TIMEOUT_SEC = 120


@register_tool(
    name="bash",
    description="Execute a shell command and return its stdout/stderr. Use this to run programs, scripts, git commands, or any system operation.",
    input_schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute. E.g. 'ls -la' or 'python script.py'",
            },
        },
        "required": ["command"],
    },
)
def bash(command: str) -> str:
    """Run a shell command and return combined stdout+stderr."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEC,
        )
        output = ""
        if result.stdout:
            output += f"[stdout]\n{result.stdout}"
        if result.stderr:
            output += f"[stderr]\n{result.stderr}"
        if not output:
            output = "(no output)"
        output += f"\n[exit code: {result.returncode}]"
        return output
    except subprocess.TimeoutExpired:
        return f"[error] Command timed out after {TIMEOUT_SEC}s"
    except Exception as e:  # noqa: BLE001
        return f"[error] {type(e).__name__}: {e}"


@register_tool(
    name="read_file",
    description="Read the contents of a file from the local filesystem.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file to read.",
            },
        },
        "required": ["path"],
    },
)
def read_file(path: str) -> str:
    """Read a file and return its contents."""
    try:
        file_path = Path(path).expanduser().resolve()
        return file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"[error] File not found: {path}"
    except Exception as e:  # noqa: BLE001
        return f"[error] {type(e).__name__}: {e}"


@register_tool(
    name="write_file",
    description="Write text content to a file, creating parent directories if needed.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file to write.",
            },
            "content": {
                "type": "string",
                "description": "The text content to write to the file.",
            },
        },
        "required": ["path", "content"],
    },
)
def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    try:
        file_path = Path(path).expanduser().resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} characters to {file_path}"
    except Exception as e:  # noqa: BLE001
        return f"[error] {type(e).__name__}: {e}"
