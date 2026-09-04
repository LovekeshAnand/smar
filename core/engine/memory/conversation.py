"""
backend/memory/conversation.py
===============================
Persistent conversation memory stored in a JSON file on disk.

Fixes in this version:
  - Added flush() method (called by main.py on shutdown)
  - Fixed turn_count() — was referencing non-existent self.turns
  - Atomic writes via a .tmp file + rename (prevents corruption on crash)
"""

import json
import os
from pathlib import Path


class ConversationMemory:
    """
    Reads and writes conversation history to a JSON file.

    Usage:
        mem = ConversationMemory("/path/to/conversation.json", max_turns=10)
        mem.add("user", "write a fibonacci function")
        mem.add("assistant", "def fibonacci(n): ...")
        context = mem.get_context_string()
    """

    def __init__(self, memory_path: str, max_turns: int = 10):
        self.path      = Path(memory_path)
        self.max_turns = max_turns
        self._cache: list | None = None   # in-memory write buffer
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("[]", encoding="utf-8")

    def _load(self) -> list:
        """Load from disk (or return cached write buffer)."""
        if self._cache is not None:
            return self._cache
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            pass
        return []

    def _save(self, messages: list) -> None:
        """Atomic write: write to .tmp then rename."""
        self._cache = messages          # update in-memory cache immediately
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(
                json.dumps(messages, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(self.path)      # atomic on POSIX; best-effort on Windows
        except Exception as e:
            print(f"[Memory] Write error: {e}")
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    def add(self, role: str, content: str) -> None:
        """Append a message and trim to max_turns * 2."""
        messages = self._load()
        messages.append({"role": role, "content": content})

        max_messages = self.max_turns * 2
        if len(messages) > max_messages:
            messages = messages[-max_messages:]

        self._save(messages)

    def get_recent(self) -> list:
        return self._load()

    def get_context_string(self) -> str:
        """
        Format recent conversation for model context injection.
        Returns empty string if no history.
        """
        messages = self._load()
        if not messages:
            return ""

        lines = ["### Previous conversation (for context):"]
        for msg in messages:
            role    = "User" if msg["role"] == "user" else "Assistant"
            content = msg["content"]
            if len(content) > 300:
                content = content[:300] + "..."
            lines.append(f"{role}: {content}")

        lines.append("")
        return "\n".join(lines)

    def flush(self) -> None:
        """
        Ensure the write buffer is persisted to disk.
        Called by main.py on clean shutdown.
        """
        if self._cache is not None:
            self._save(self._cache)
            print("[Memory] Flushed to disk")

    def clear(self) -> None:
        """Wipe all conversation history."""
        self._cache = []
        self._save([])
        print("[Memory] Conversation history cleared")

    def turn_count(self) -> int:
        """Return the number of complete user↔assistant turns."""
        messages = self._load()
        return len(messages) // 2

    def stats(self) -> dict:
        messages = self._load()
        return {
            "total_messages": len(messages),
            "turns":          len(messages) // 2,
            "max_turns":      self.max_turns,
            "file_path":      str(self.path),
        }