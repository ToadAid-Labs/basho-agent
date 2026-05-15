import importlib
import logging
import pkgutil
import sys
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Global registry: tool_name -> (definition, handler, metadata)
_TOOL_REGISTRY: dict[str, tuple[dict[str, Any], Callable, dict[str, Any]]] = {}
_TOOLS_LOADED = False


def register_tool(
    name: str,
    description: str,
    input_schema: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> Callable:
    """Decorator to register a tool with the agent."""

    def decorator(func: Callable) -> Callable:
        tool_definition = {
            "name": name,
            "description": description,
            "input_schema": input_schema,
        }
        tool_metadata = dict(metadata or {})
        _TOOL_REGISTRY[name] = (
            tool_definition,
            func,
            tool_metadata,
        )
        return func

    return decorator


def load_tools(force_reload: bool = False) -> None:
    """Auto-load all tool modules from the tools package once."""
    global _TOOLS_LOADED
    if _TOOLS_LOADED and not force_reload:
        return

    _TOOL_REGISTRY.clear()
    for _, module_name, _ in pkgutil.iter_modules(["tools"]):
        if module_name in ("__init__",):
            continue
        full_name = f"tools.{module_name}"
        try:
            if full_name in sys.modules:
                importlib.reload(sys.modules[full_name])
            else:
                importlib.import_module(full_name)
        except Exception as e:
            logger.error(f"Failed to load tool module {full_name}: {e}")

    _TOOLS_LOADED = True


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return the tool definitions list for the Claude API."""
    load_tools()
    return [defn for defn, _, _ in _TOOL_REGISTRY.values()]


def get_tool_metadata(name: str) -> dict[str, Any]:
    """Return internal metadata for a tool, if any."""
    load_tools()
    if name not in _TOOL_REGISTRY:
        return {}
    _, _, metadata = _TOOL_REGISTRY[name]
    return dict(metadata)


def execute_tool(name: str, raw_input: dict[str, Any]) -> str:
    """Execute a registered tool by name with the given input."""
    load_tools()
    if name not in _TOOL_REGISTRY:
        return f"Error: unknown tool '{name}'"

    _, handler, _ = _TOOL_REGISTRY[name]
    try:
        result = handler(**raw_input)
        return result if result is not None else "Tool executed successfully (no output)."
    except Exception as e:  # noqa: BLE001
        return f"Error executing tool '{name}': {type(e).__name__}: {e}"
