"""The build trace: one plain-text line on stdout and one JSON line in a file per event. Keys are redacted."""
import json
import re
import time

KEY_PATTERN = re.compile(r"(fak_|sk-ant-)[A-Za-z0-9_\-]+")     # Freya keys and Anthropic keys or tokens


class Trace:
    def __init__(self, path, secrets):
        self.path = path
        self.secrets = [s for s in secrets if s]
        path.parent.mkdir(parents=True, exist_ok=True)

    def redact(self, text):
        for s in self.secrets:
            text = text.replace(s, "[REDACTED]")
        return KEY_PATTERN.sub("[REDACTED]", text)

    def log(self, kind, **fields):
        at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        line = self.redact(json.dumps({"at": at, "kind": kind, **fields}, default=str))
        with open(self.path, "a") as f:
            f.write(line + "\n")
        text = " ".join(f"{k}={v}" for k, v in fields.items())
        print(self.redact(f"{at} {kind} {text}"), flush=True)
