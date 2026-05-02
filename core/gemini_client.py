import base64
import os
import json
import logging
import tempfile
import warnings
import uuid
from collections.abc import Iterable, Mapping
from typing import Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

warnings.filterwarnings(
    "ignore",
    message=r"Unrecognized FinishReason enum value.*",
    category=UserWarning,
)

REQUIRED_OAUTH_SCOPES = {
    "https://www.googleapis.com/auth/generative-language.retriever",
}


def validate_gemini_oauth_scopes(creds) -> None:
    """Fail early when an old Google token cannot call the Gemini API."""
    scopes = set(creds.scopes or [])
    missing_scopes = sorted(REQUIRED_OAUTH_SCOPES - scopes)
    if missing_scopes:
        raise ValueError(
            "Google OAuth token is missing required Gemini scopes: "
            f"{', '.join(missing_scopes)}. Run 'python3 agent.py login' and "
            "choose Google/Gemini Web Auth again, or choose Gemini API Key."
        )


def _gemini_reauth_message() -> str:
    return (
        "Gemini OAuth needs reauthentication. Run `python3 agent.py login` and "
        "choose Google/Gemini Web Auth again, or set `GEMINI_API_KEY` in `.env`."
    )


class GeminiClient:
    """Wrapper around the Google Gemini API."""

    def __init__(self, model: str | None = None):
        self.token_path = os.path.expanduser(os.getenv("GOOGLE_TOKEN_PATH", "~/.agent_google_token.json"))
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.request_timeout_seconds = float(os.getenv("GEMINI_REQUEST_TIMEOUT_SECONDS", "45"))
        self._token_mtime: float | None = None
        raw_model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        # Ensure model name doesn't have double prefix if using legacy SDK
        if raw_model.startswith("models/"):
            self.model_name = raw_model.replace("models/", "")
        else:
            self.model_name = raw_model
        
        self.uses_legacy_oauth_sdk = False
        
        if os.path.exists(self.token_path) and not self.api_key:
            self._configure_legacy_oauth_client()
        elif self.api_key:
            # Use simple API Key
            from google import genai
            from google.genai import types

            self.client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=int(self.request_timeout_seconds * 1000)),
            )
        else:
            raise ValueError("No Gemini authentication found. Run 'python3 agent.py login'.")

    def _configure_legacy_oauth_client(self) -> None:
        """Load OAuth credentials from disk and rebuild the legacy SDK client."""
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            import google.generativeai as legacy_genai
            from google.ai import generativelanguage as proto

        creds = Credentials.from_authorized_user_file(self.token_path)
        validate_gemini_oauth_scopes(creds)
        if creds.expired:
            try:
                creds.refresh(Request())
            except RefreshError as exc:
                raise ValueError(_gemini_reauth_message()) from exc
            self._persist_legacy_oauth_credentials(creds)
        legacy_genai.configure(credentials=creds)
        self.client = legacy_genai.GenerativeModel(model_name=self.model_name)
        self.proto = proto
        self.creds = creds
        self.uses_legacy_oauth_sdk = True
        self._token_mtime = self._current_token_mtime()

    def _persist_legacy_oauth_credentials(self, creds) -> None:
        """Write refreshed OAuth credentials back to disk so future runs reuse them."""
        token_dir = os.path.dirname(self.token_path) or "."
        os.makedirs(token_dir, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix=".google-token-", suffix=".json", dir=token_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(creds.to_json())
            os.replace(temp_path, self.token_path)
        except OSError:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            logger.warning("Failed to persist refreshed Gemini OAuth credentials.", exc_info=True)
            return
        self._token_mtime = self._current_token_mtime()

    def _current_token_mtime(self) -> float | None:
        try:
            return os.path.getmtime(self.token_path)
        except OSError:
            return None

    def _reload_legacy_oauth_if_token_changed(self, force: bool = False) -> bool:
        """Reload OAuth credentials after web login refreshes the token file."""
        if not self.uses_legacy_oauth_sdk or self.api_key:
            return False

        current_mtime = self._current_token_mtime()
        if current_mtime is None:
            return False
        if not force and self._token_mtime == current_mtime:
            return False

        logger.info("Reloading Gemini OAuth credentials from updated token file.")
        self._configure_legacy_oauth_client()
        return True

    def _ensure_legacy_oauth_fresh(self) -> None:
        if not self.uses_legacy_oauth_sdk or self.api_key:
            return
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request

        creds = getattr(self, "creds", None)
        if creds is None:
            return
        if not creds.valid or creds.expired:
            try:
                creds.refresh(Request())
            except RefreshError as exc:
                raise ValueError(_gemini_reauth_message()) from exc
            self._persist_legacy_oauth_credentials(creds)

    def create_message(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
        max_tokens: int = 4096,
    ) -> Any:
        # Gemini is sensitive to schema fields like 'default' or 'enum' in some versions
        cleaned_tools = []
        for t in tools:
            cleaned_t = t.copy()
            if "input_schema" in cleaned_t:
                cleaned_t["input_schema"] = self._clean_schema(cleaned_t["input_schema"])
            cleaned_tools.append(cleaned_t)

        if self.uses_legacy_oauth_sdk:
            self._reload_legacy_oauth_if_token_changed()
            self._ensure_legacy_oauth_fresh()
            # Legacy SDK Tool mapping
            legacy_tools = []
            if cleaned_tools:
                function_declarations = []
                for t in cleaned_tools:
                    function_declarations.append({
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t.get("input_schema", {})
                    })
                legacy_tools = [{"function_declarations": function_declarations}]

            contents = self._build_contents_legacy(messages, system_prompt)
            response = self.client.generate_content(
                contents,
                tools=legacy_tools if legacy_tools else None,
                request_options={"timeout": self.request_timeout_seconds},
            )
            return GeminiResponse(response)

        from google.genai import types
        
        config = None
        google_tools = []
        if cleaned_tools:
            function_declarations = []
            for t in cleaned_tools:
                function_declarations.append(types.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters=t.get("input_schema")
                ))
            google_tools = [types.Tool(function_declarations=function_declarations)]

        if system_prompt or google_tools:
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=google_tools if google_tools else None,
                max_output_tokens=max_tokens
            )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=self._build_contents_new(messages),
            config=config,
        )
        return GeminiResponse(response)

    def analyze_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        max_tokens: int = 1000,
    ) -> str:
        """Analyze one inline image with Gemini and return user-facing text."""
        safe_prompt = prompt.strip() or "Describe this image briefly."

        if self.uses_legacy_oauth_sdk:
            self._reload_legacy_oauth_if_token_changed()
            self._ensure_legacy_oauth_fresh()
            response = self.client.generate_content(
                [
                    {"mime_type": mime_type, "data": image_bytes},
                    safe_prompt,
                ],
                request_options={"timeout": self.request_timeout_seconds},
            )
            return getattr(response, "text", "") or _empty_response_message(response)

        from google.genai import types

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                safe_prompt,
            ],
            config=types.GenerateContentConfig(max_output_tokens=max_tokens),
        )
        return getattr(response, "text", "") or _empty_response_message(response)

    def _clean_schema(self, schema: dict) -> dict:
        """Surgically clean up JSON schema for Gemini SDK (strips 'default', etc)."""
        if not isinstance(schema, dict):
            return schema
            
        new_schema = schema.copy()
        
        # 'default' is not supported in many Gemini Schema versions and causes crashes
        if "default" in new_schema:
            del new_schema["default"]
            
        # Ensure type is present for objects
        if "type" in new_schema and new_schema["type"] == "object":
            if "properties" not in new_schema:
                new_schema["properties"] = {}
                
        # Recursively clean properties
        if "properties" in new_schema:
            new_properties = {}
            for k, v in new_schema["properties"].items():
                new_properties[k] = self._clean_schema(v)
            new_schema["properties"] = new_properties
            
        return new_schema

    def _clean_legacy_schema(self, schema: dict) -> dict:
        """Deprecated: use _clean_schema instead."""
        return self._clean_schema(schema)

    def _build_contents_new(self, messages: list[dict[str, Any]]) -> list[Any]:
        """Build contents for the new google-genai SDK."""
        from google.genai import types
        contents = []
        unsigned_tool_call_ids: set[str] = set()
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            
            # Map role
            google_role = "user" if role in ("user", "system") else "model"
            
            parts = []
            if isinstance(content, str):
                parts.append(types.Part(text=content))
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text":
                        parts.append(types.Part(text=block.get("text", "")))
                    elif block.get("type") == "thought":
                        parts.append(types.Part(thought=block.get("text", "")))
                    elif block.get("type") == "tool_use":
                        # Gemini 3 requires thought_signature to match the one sent by model
                        if not block.get("thought_signature"):
                            call_id = str(block.get("id") or "")
                            if call_id:
                                unsigned_tool_call_ids.add(call_id)
                            parts.append(types.Part(text=_format_unsigned_tool_call_text(block)))
                            continue

                        sig = _decode_thought_signature(block.get("thought_signature"))
                        parts.append(types.Part(
                            thought_signature=sig,
                            function_call=types.FunctionCall(
                                name=block["name"],
                                args=block["input"],
                                id=_function_call_id(block, sig)
                            )
                        ))
                    elif block.get("type") == "tool_result":
                        if str(block.get("tool_use_id") or "") in unsigned_tool_call_ids:
                            parts.append(types.Part(text=_format_tool_result_context_text(block)))
                            continue

                        # Tool results must follow the function call in the same role (user/model)
                        # but Gemini expects them as a separate turn with role 'user' usually
                        # or 'function' in some SDKs.
                        try:
                            # Try parsing result as JSON for structured response
                            res_val = json.loads(block["content"])
                            if not isinstance(res_val, dict):
                                res_val = {"result": res_val}
                        except:
                            res_val = {"result": block["content"]}
                            
                        parts.append(types.Part(
                            function_response=types.FunctionResponse(
                                name=block.get("name", "unknown"), # We might need to track name
                                response=res_val
                            )
                        ))
            
            if parts:
                contents.append(types.Content(role=google_role, parts=parts))
                
        return contents

    def _build_contents_legacy(self, messages: list[dict[str, Any]], system_prompt: str | None) -> list[Any]:
        """Build contents for the legacy google-generativeai SDK using explicit Protos."""
        contents = []
        proto = self.proto
        unsigned_tool_call_ids: set[str] = set()
        
        # System prompt as first user message in legacy
        if system_prompt:
            contents.append({
                "role": "user", 
                "parts": [proto.Part(text=f"SYSTEM INSTRUCTION: {system_prompt}")]
            })

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            
            google_role = "user" if role in ("user", "system") else "model"
            parts = []
            
            if isinstance(content, str):
                parts.append(proto.Part(text=content))
            elif isinstance(content, list):
                for block in content:
                    if block.get("type") == "text":
                        parts.append(proto.Part(text=block.get("text", "")))
                    elif block.get("type") == "thought":
                        # Attempt to set thought if part supports it
                        try:
                            parts.append(proto.Part(thought=block.get("text", "")))
                        except:
                            # Fallback to text for thought in legacy if thought field is missing
                            parts.append(proto.Part(text=f"[Thought]: {block.get('text', '')}"))
                    elif block.get("type") == "tool_use":
                        if not block.get("thought_signature"):
                            call_id = str(block.get("id") or "")
                            if call_id:
                                unsigned_tool_call_ids.add(call_id)
                            parts.append(proto.Part(text=_format_unsigned_tool_call_text(block)))
                            continue

                        sig = _decode_thought_signature(block.get("thought_signature"))
                        
                        # Use explicit proto objects to bypass SDK's dict guessing logic
                        fc = proto.FunctionCall(
                            name=block["name"],
                            args=block["input"]
                        )
                        # FunctionCall.id is text in some SDK versions; thought_signature is binary.
                        if hasattr(fc, "id"):
                            fc.id = _function_call_id(block, sig)
                        
                        p = proto.Part(function_call=fc)
                        if hasattr(p, "thought_signature"):
                            p.thought_signature = sig
                            
                        parts.append(p)
                    elif block.get("type") == "tool_result":
                        if str(block.get("tool_use_id") or "") in unsigned_tool_call_ids:
                            parts.append(proto.Part(text=_format_tool_result_context_text(block)))
                            continue

                        try:
                            res_val = json.loads(block["content"])
                            if not isinstance(res_val, dict):
                                res_val = {"result": res_val}
                        except:
                            res_val = {"result": block["content"]}
                            
                        fr = proto.FunctionResponse(
                            name=block.get("name", "unknown"),
                            response=res_val
                        )
                        parts.append(proto.Part(function_response=fr))
            
            if parts:
                contents.append({"role": google_role, "parts": parts})
        
        return contents

class GeminiResponse:
    def __init__(self, response):
        self.content = []
        
        # Extract text and tool calls
        found_blocks = _extract_blocks(response)
        if found_blocks:
            self.content = found_blocks
        else:
            self.content.append(TextBlock(_empty_response_message(response)))
        
        self.stop_reason = _extract_finish_reason(response) or "stop"

class TextBlock:
    type = "text"
    def __init__(self, text):
        self.text = text

class ThoughtBlock:
    type = "thought"
    def __init__(self, text):
        self.text = text

class ToolUseBlock:
    type = "tool_use"
    def __init__(self, tool_use_id, name, tool_input, thought_signature=None):
        self.id = tool_use_id
        self.name = name
        self.input = tool_input
        self.thought_signature = thought_signature


def _encode_thought_signature(value: Any) -> Any:
    """Store Gemini thought signatures in JSON-safe form."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    return value


def _decode_thought_signature(value: Any) -> Any:
    """Convert persisted thought signatures back to bytes for the SDK."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        try:
            return base64.b64decode(value.encode("ascii"), validate=True)
        except Exception:
            return value.encode("utf-8")
    return value


def _json_safe_value(value: Any) -> Any:
    """Convert SDK/protobuf containers into JSON-serializable Python values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, Mapping):
        return {str(k): _json_safe_value(v) for k, v in value.items()}
    if hasattr(value, "items"):
        return {str(k): _json_safe_value(v) for k, v in value.items()}
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe_value(item) for item in value]
    if hasattr(value, "model_dump"):
        return _json_safe_value(value.model_dump())
    if hasattr(value, "to_dict"):
        return _json_safe_value(value.to_dict())
    return str(value)


def _format_unsigned_tool_call_text(block: dict[str, Any]) -> str:
    name = block.get("name", "unknown")
    return f"[Tool call recorded without Gemini thought signature: {name}]"


def _format_tool_result_context_text(block: dict[str, Any]) -> str:
    name = block.get("name", "unknown")
    content = block.get("content", "")
    return f"[Tool result from {name}]\n{content}"

def _extract_blocks(response) -> list[Any]:
    blocks = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            # Check for text
            text = getattr(part, "text", None)
            if text:
                blocks.append(TextBlock(text))
            
            # Check for thought
            thought = getattr(part, "thought", None)
            if thought:
                blocks.append(ThoughtBlock(thought))
                
            # Check for function call
            fn_call = getattr(part, "function_call", None)
            if fn_call:
                # Handle both legacy and new SDK formats
                name = getattr(fn_call, "name", None)
                args = getattr(fn_call, "args", {})
                args = _json_safe_value(args)
                if not isinstance(args, dict):
                    args = {}
                
                # Capture the binary thought_signature from the Part when available.
                thought_sig = getattr(part, "thought_signature", None)
                if not thought_sig:
                    thought_sig = getattr(fn_call, "thought_signature", None)
                thought_sig = _encode_thought_signature(thought_sig)
                call_id = getattr(fn_call, "id", None)
                    
                blocks.append(ToolUseBlock(
                    tool_use_id=call_id or thought_sig or f"call_{uuid.uuid4().hex[:12]}",
                    name=name,
                    tool_input=args,
                    thought_signature=thought_sig
                ))
    return blocks

def _extract_finish_reason(response) -> str | None:
    for candidate in getattr(response, "candidates", []) or []:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            finish_reason = getattr(candidate, "finish_reason", None)
        if finish_reason is not None:
            # 12 is MALFORMED_PROMPT in some versions, but we should treat it as a stop if we can't do more
            return str(finish_reason)
    return None


def _function_call_id(block: dict[str, Any], sig: Any) -> str:
    """Return a text-safe function call id; never pass raw signature bytes as id."""
    call_id = block.get("id")
    if isinstance(call_id, str) and call_id:
        return call_id
    if isinstance(sig, bytes):
        return base64.b64encode(sig).decode("ascii")
    if isinstance(sig, str) and sig:
        return sig
    return f"call_{uuid.uuid4().hex[:12]}"

def _empty_response_message(response) -> str:
    finish_reason = _extract_finish_reason(response) or "unknown"
    prompt_feedback = getattr(response, "prompt_feedback", None)
    feedback_text = ""
    if prompt_feedback:
        feedback_text = f" Prompt feedback: {prompt_feedback}."

    return (
        "Gemini returned no text for this request "
        f"(finish_reason={finish_reason}).{feedback_text} "
        "Try rephrasing the request or use the openai-codex provider for this action."
    )
