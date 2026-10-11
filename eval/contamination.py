"""Check that builder/ holds no value from any brief.

    python eval/contamination.py      exits 1 and prints file:line: token for each leak

A brief token is an ISO date, a number with a decimal point or with 3 or more digits, or a back-quoted
snake_case word. Tokens that also appear in kit/docs/*.md, or that name a tool API operation, are allowed.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATE = r"\d{4}-\d{2}-\d{2}"
NUMBER = r"(?<![\w.-])\d+\.\d+(?![\w.-])|(?<![\w.-])\d{3,}(?![\w.-])"
SNAKE = r"`([a-z][a-z0-9]*(?:_[a-z0-9]+)+)`"
WORD = r"[A-Za-z_][A-Za-z0-9_]*"
SKIP = ("runs", "tests/fixtures")


def brief_tokens(text):
    return set(re.findall(DATE, text)) | set(re.findall(NUMBER, text)) | set(re.findall(SNAKE, text))


def _line_tokens(line):
    return set(re.findall(DATE, line)) | set(re.findall(NUMBER, line)) | set(re.findall(WORD, line))


def find_leaks(builder_dir, briefs, allowed):
    wanted = set().union(*(brief_tokens(Path(b).read_text()) for b in briefs)) - allowed if briefs else set()
    leaks = []
    for path in sorted(builder_dir.rglob("*")):
        rel = path.relative_to(builder_dir).as_posix()
        if not path.is_file() or path.suffix not in (".py", ".md", ".json") or any(rel.startswith(s + "/") for s in SKIP):
            continue
        for n, line in enumerate(path.read_text().splitlines(), 1):
            for token in sorted(_line_tokens(line) & wanted):
                leaks.append(f"{path}:{n}: {token}")
    return leaks


def allowed_tokens():
    docs = " ".join(p.read_text() for p in (REPO / "kit" / "docs").glob("*.md"))
    ops = {p.strip("/") for p in json.load(open(REPO / "kit" / "tools" / "openapi.json"))["paths"]}
    return brief_tokens(docs) | set(re.findall(WORD, docs)) | ops


def brief_files():
    """The kit and eval briefs, and every Markdown file in briefs/ (the final case folder, runbook)."""
    return [p for d, pattern in (("kit/briefs", "*.md"), ("eval/briefs", "*.md"), ("briefs", "**/*.md"))
            for p in sorted((REPO / d).glob(pattern))]


def main():
    briefs = brief_files()
    leaks = find_leaks(REPO / "builder", briefs, allowed_tokens())
    for leak in leaks:
        print(leak)
    print(f"contamination: {len(leaks)} leaks in builder/ against {len(briefs)} briefs")
    return 1 if leaks else 0


if __name__ == "__main__":
    sys.exit(main())
