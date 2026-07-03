"""Append-only JSONL history of dictations."""

import json
from datetime import datetime
from pathlib import Path


class History:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, text: str, duration_s: float = 0.0, backend: str = "") -> None:
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "text": text,
            "duration_s": round(float(duration_s), 2),
            "backend": backend,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def last(self, n: int = 20) -> list:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        entries = []
        for line in lines:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries[-n:]
