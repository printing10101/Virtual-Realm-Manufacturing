"""Scan for exception leak patterns in the codebase."""
import re
import sys
from pathlib import Path

ROOT = Path("app")

# Patterns that indicate exception message may leak to client
PATTERNS = [
    # str(e), str(exc), str(error), str(err) used outside logger
    (re.compile(r'\bstr\((?:e|exc|error|err|exception)\)(?!\s*[,)])'), "str_exception"),
    # f"...{e}" or f"...{exc}" in return statements
    (re.compile(r'return\s+["\']?.*f["\'].*\{(?:e|exc|error|err)\b'), "fstring_return"),
    # HTTPException(detail=... f"...{e}..." or str(e))
    (re.compile(r'HTTPException\([^)]*(?:str\([a-z]+\)|f["\'].*\{(?:e|exc)\b)'), "httpexception_leak"),
    # message=f"...{e}..." in error()/success()
    (re.compile(r'message\s*=\s*["\']?.*f["\'].*\{(?:e|exc|error)\b'), "message_leak"),
]

# Allowlist: contexts where these are safe
SAFE_CONTEXT_KEYWORDS = (
    "logger.",
    "logging.",
    "_record_stage_error",  # our wrapper
    "safe_error_message",  # our wrapper
    "# ",  # comments
)


def is_safe_context(line: str) -> bool:
    return any(kw in line for kw in SAFE_CONTEXT_KEYWORDS)


def main() -> int:
    dangerous = []
    for p in ROOT.rglob("*.py"):
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if is_safe_context(line):
                continue
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            for pat, label in PATTERNS:
                if pat.search(line):
                    dangerous.append((str(p), n, label, line.strip()[:120]))
                    break

    if not dangerous:
        print("OK: No exception leak patterns detected.")
        return 0

    print(f"Found {len(dangerous)} potential issues:")
    for path, n, label, l in dangerous:
        print(f"  {path}:{n} [{label}]: {l}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
