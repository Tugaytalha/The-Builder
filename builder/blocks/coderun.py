"""Run code-node snippets locally, with the same date helpers the workflow gets."""
from pathlib import Path

from builder.blocks import datelib

DATES_SOURCE = Path(datelib.__file__).read_text()


def with_dates(body):
    return DATES_SOURCE + "\n" + body


def run_snippet(code, vars):
    scope = {"vars": dict(vars)}
    exec(code, scope)
    return scope["vars"]
