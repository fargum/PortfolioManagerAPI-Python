"""PreToolUse guard: block account_id being defined as a schema field or tool parameter.

CLAUDE.md rule: account_id must always come from Depends(get_current_account_id) in
routes -- never from request body or AI tool input. This hook only fires for edits
under src/schemas/ or src/services/ai/tools/, where that rule is easiest to violate
by accident.
"""

import json
import re
import sys

GUARDED_DIRS = ("src/schemas/", "src/services/ai/tools/")

# A field/parameter *definition*, e.g. "account_id: int" or "account_id: Optional[str]".
# Deliberately narrow so normal reads of an already-injected account_id don't trip it.
FIELD_DEF_RE = re.compile(r"^\s*account_id\s*:\s*(int|str|Optional)", re.MULTILINE)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {}) or {}
    file_path = (tool_input.get("file_path") or "").replace("\\", "/")

    if not any(d in file_path for d in GUARDED_DIRS):
        return 0

    if tool_name == "Write":
        content = tool_input.get("content", "") or ""
    elif tool_name == "Edit":
        content = tool_input.get("new_string", "") or ""
    else:
        return 0

    match = FIELD_DEF_RE.search(content)
    if match:
        print(
            "BLOCKED: account_id must never be defined as a schema field or AI tool "
            "parameter.\n"
            f"  File: {file_path}\n"
            f"  Found: {match.group(0).strip()!r}\n"
            "CLAUDE.md: account_id is always injected server-side from "
            "Depends(get_current_account_id) in routes, or closed over per-request in "
            "AI tool factories -- never read from request body or exposed as tool "
            "input. This is the account isolation security boundary.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
