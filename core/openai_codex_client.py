import base64
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()


CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class OpenAICodexClient:
    """Wrapper around Codex CLI using ChatGPT/Codex OAuth credentials."""

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("OPENAI_CODEX_MODEL", "gpt-5.4-mini")
        self.codex_bin = os.getenv("CODEX_BIN", "codex")
        self.token_path = Path(
            os.path.expanduser(
                os.getenv("OPENAI_CODEX_TOKEN_PATH", "~/.agent_openai_codex_auth.json")
            )
        )
        self.codex_home = Path(
            os.path.expanduser(
                os.getenv("OPENAI_CODEX_HOME", "~/.agent_openai_codex_home")
            )
        )
        self.workdir = Path(
            os.path.expanduser(os.getenv("OPENAI_CODEX_WORKDIR", str(PROJECT_ROOT)))
        ).resolve()
        self.sandbox = os.getenv("OPENAI_CODEX_SANDBOX", "read-only").strip()
        self.bypass_sandbox = _env_truthy("OPENAI_CODEX_BYPASS_SANDBOX")

        if shutil.which(self.codex_bin) is None:
            raise ValueError("Codex CLI not found. Install @openai/codex or set CODEX_BIN.")
        if not self.token_path.exists():
            raise ValueError(
                "OpenAI Codex OAuth token not found. Run 'python3 agent.py login' "
                "and choose OpenAI ChatGPT/Codex Web Auth."
            )
        if not self.workdir.exists():
            raise ValueError(f"OpenAI Codex workdir does not exist: {self.workdir}")

        self._sync_auth_file()

    def create_message(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
        max_tokens: int = 4096,
    ) -> Any:
        prompt = self._build_prompt(messages, system_prompt, tools)

        with tempfile.NamedTemporaryFile("r", delete=False) as output_file:
            output_path = output_file.name

        try:
            env = os.environ.copy()
            env["CODEX_HOME"] = str(self.codex_home)

            cmd = [self.codex_bin, "exec"]
            if self.bypass_sandbox:
                cmd.append("--dangerously-bypass-approvals-and-sandbox")
            else:
                cmd.extend(["--sandbox", self.sandbox])
            cmd.extend(
                [
                    "--skip-git-repo-check",
                    "--cd",
                    str(self.workdir),
                    "--color",
                    "never",
                    "-m",
                    self.model,
                    "--output-last-message",
                    output_path,
                    "-",
                ]
            )

            result = subprocess.run(
                cmd,
                input=prompt,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=int(os.getenv("OPENAI_CODEX_TIMEOUT_SECONDS", "900")),
                env=env,
                cwd=str(self.workdir),
            )

            output = Path(output_path).read_text().strip()
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip()
                raise RuntimeError(f"Codex CLI failed: {detail}")
            if not output:
                output = _strip_codex_noise(result.stdout)
            tool_call = _parse_tool_call(output, tools)
            if tool_call:
                return OpenAICodexToolResponse(tool_call)
            return OpenAICodexResponse(output)
        finally:
            try:
                Path(output_path).unlink()
            except OSError:
                pass

    def _sync_auth_file(self) -> None:
        source = json.loads(self.token_path.read_text())
        tokens = source.get("tokens", {})
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")

        if not access_token or not refresh_token:
            raise ValueError(
                "OpenAI Codex OAuth token file is missing access_token or refresh_token. "
                "Run 'python3 agent.py login' and choose OpenAI ChatGPT/Codex Web Auth."
            )

        account_id = tokens.get("account_id") or _extract_chatgpt_account_id(access_token)
        auth_payload = {
            "auth_mode": "chatgpt",
            "OPENAI_API_KEY": None,
            "tokens": {
                "id_token": tokens.get("id_token"),
                "access_token": access_token,
                "refresh_token": refresh_token,
                "account_id": account_id,
            },
            "last_refresh": source.get("last_refresh"),
        }

        self.codex_home.mkdir(parents=True, exist_ok=True)
        (self.codex_home / "auth.json").write_text(json.dumps(auth_payload, indent=2))

    def _build_prompt(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str | None,
        tools: list[dict[str, Any]] | None = None,
    ) -> str:
        parts = []
        if system_prompt:
            parts.append(f"System instructions:\n{system_prompt}")
        parts.append(
            "Respond as the assistant for the latest user message. "
            "Do not edit files or run commands unless the user explicitly asks."
        )
        if tools:
            tool_names = [tool["name"] for tool in tools]
            parts.append(
                "Local tool protocol:\n"
                "You can request one local tool call at a time. If you need a local tool, "
                "respond with only compact JSON in this exact shape: "
                '{"tool": "tool_name", "input": {}}. '
                "After a Tool result appears in the transcript, answer the user normally or "
                "request another tool with the same JSON shape.\n"
                f"Available local tools: {', '.join(tool_names)}"
            )
        parts.append(
            f"Workspace root: {self.workdir}\n"
            "If a workspace/README.md file exists, read it before making workspace changes. "
            "Use workspace/agent_memory for local work memory, workspace/scratch for temporary files, "
            "and workspace/tasks for task notes. Never store secrets in workspace files."
        )

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = _flatten_content_blocks(content)
            parts.append(f"{role.upper()}:\n{content}")

        return "\n\n".join(parts)


class OpenAICodexResponse:
    def __init__(self, text: str):
        self.content = [TextBlock(text)] if text else []
        self.stop_reason = "stop"


class OpenAICodexToolResponse:
    def __init__(self, tool_call: dict[str, Any]):
        self.content = [
            ToolUseBlock(
                tool_call["id"],
                tool_call["name"],
                tool_call["input"],
            )
        ]
        self.stop_reason = "tool_use"


class TextBlock:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class ToolUseBlock:
    type = "tool_use"

    def __init__(self, id: str, name: str, input_args: dict[str, Any]):
        self.id = id
        self.name = name
        self.input = input_args


def _flatten_content_blocks(content: list[Any]) -> str:
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_result":
            parts.append(f"Tool result: {block.get('content', '')}")
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
        elif isinstance(block, str):
            parts.append(block)
    return "\n".join(part for part in parts if part)


def _extract_chatgpt_account_id(access_token: str) -> str | None:
    try:
        payload = access_token.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        claims = json.loads(decoded)
        auth_claims = claims.get("https://api.openai.com/auth", {})
        return auth_claims.get("chatgpt_account_id")
    except Exception:
        return None


def _strip_codex_noise(stdout: str) -> str:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    filtered = []
    skip_prefixes = (
        "OpenAI Codex",
        "--------",
        "workdir:",
        "model:",
        "provider:",
        "approval:",
        "sandbox:",
        "reasoning ",
        "session id:",
        "tokens used",
        "user",
        "codex",
    )
    for line in lines:
        if any(line.startswith(prefix) for prefix in skip_prefixes):
            continue
        filtered.append(line)
    return "\n".join(filtered).strip()


def _parse_tool_call(output: str, tools: list[dict[str, Any]]) -> dict[str, Any] | None:
    text = output.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None

    name = payload.get("tool") or payload.get("name")
    if not name:
        tool_use = payload.get("tool_use")
        if isinstance(tool_use, dict):
            name = tool_use.get("name")
            payload = tool_use

    valid_names = {tool["name"] for tool in tools}
    if name not in valid_names:
        return None

    input_args = payload.get("input", {})
    if not isinstance(input_args, dict):
        input_args = {}

    return {
        "id": payload.get("id") or f"codex_tool_{abs(hash(text))}",
        "name": name,
        "input": input_args,
    }


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}
