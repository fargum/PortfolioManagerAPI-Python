"""PreToolUse guard: block module-level AI tool instantiation.

CLAUDE.md rule: AI tools must never be created as module-level globals. They must be
built per-request by a create_X_tool(service, account_id) factory so account_id is
closed over in the inner function rather than settable by the LLM.
"""

import json
import re
import sys

GUARDED_DIR = "src/services/ai/tools/"

# Anchored at column 0 (no leading whitespace) => not inside a function/class body.
# Covers both a bare call and "name = StructuredTool...." assignments.
MODULE_LEVEL_RE = re.compile(
    r"^(?:\w+\s*=\s*)?(StructuredTool\.from_function|StructuredTool\()", re.MULTILINE
)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {}) or {}
    file_path = (tool_input.get("file_path") or "").replace("\\", "/")

    if GUARDED_DIR not in file_path or not file_path.endswith(".py"):
        return 0

    if tool_name == "Write":
        content = tool_input.get("content", "") or ""
    elif tool_name == "Edit":
        content = tool_input.get("new_string", "") or ""
    else:
        return 0

    match = MODULE_LEVEL_RE.search(content)
    if match:
        print(
            "BLOCKED: AI tool instantiated at module level.\n"
            f"  File: {file_path}\n"
            f"  Found: {match.group(0).strip()!r} at column 0 (not indented)\n"
            "CLAUDE.md: never create AI tools as module-level globals. Wrap this in "
            "a create_<name>_tool(service, account_id) factory called per-request, "
            "so account_id is closed over in the inner async function instead of "
            "being settable by the LLM.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
