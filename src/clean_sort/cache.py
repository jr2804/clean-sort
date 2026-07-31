"""Content-hash cache for skipping already-sorted files.

The cache maps ``f"{config_signature}:{source_hash}"`` to the hash of the
sorted output. A file is skipped when:

1. its cache key is present, AND
2. the hash of the file's current content equals the stored sorted-output hash.

This invariant means the cache can only ever cause us to skip a file we would
not have modified anyway. Any edit drifts the content hash and forces a full
sort; any config/version change drifts the signature and forces a full sort.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

__all__ = ["Cache", "hash_text"]


class Cache:
    """On-disk content-hash cache keyed by ``config_signature:source_hash``.

    The cache is loaded once at the start of a run and saved once at the end
    (if any new entries were recorded). Reads/writes are atomic on save
    (temp file + rename) to avoid corruption on crash.
    """

    def __init__(self, path: Path | None) -> None:
        self._path = path
        self._entries: dict[str, str] = {}
        self._dirty = False

    @property
    def path(self) -> Path | None:
        """Where this cache is stored on disk (``None`` = in-memory/no-op)."""
        return self._path

    def load(self) -> None:
        """Read the cache file. Missing or corrupt files are treated as empty."""
        if self._path is None or not self._path.exists():
            self._entries = {}
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and all(
                isinstance(k, str) and isinstance(v, str) for k, v in data.items()
            ):
                self._entries = data
            else:
                self._entries = {}
        except (json.JSONDecodeError, OSError):
            # Corrupt cache: silently start fresh. Better a few redundant sorts
            # than a crashed run.
            self._entries = {}

    def lookup(self, config_sig: str, source_hash: str, current_content_hash: str) -> bool:
        """True when the file can be skipped (already in sorted state).

        A hit requires the stored sorted-output hash to match the file's current
        content hash — otherwise the file was edited after caching and must sort.
        """
        key = f"{config_sig}:{source_hash}"
        stored = self._entries.get(key)
        return stored is not None and stored == current_content_hash

    def record(self, config_sig: str, source_hash: str, sorted_hash: str) -> None:
        """Record (or refresh) the sorted-output hash for a source hash."""
        key = f"{config_sig}:{source_hash}"
        if self._entries.get(key) != sorted_hash:
            self._entries[key] = sorted_hash
            self._dirty = True

    def save(self) -> None:
        """Atomically write the cache if it changed. No-op without a path."""
        if self._path is None or not self._dirty:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        payload: dict[str, Any] = self._entries
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(self._path)
        self._dirty = False

    def merge(self, entries: dict[str, str]) -> None:
        """Merge external cache entries (e.g. from parallel workers) into this cache."""
        for key, value in entries.items():
            if self._entries.get(key) != value:
                self._entries[key] = value
                self._dirty = True


def hash_text(text: str) -> str:
    """Stable hex digest of a string (used for both source and sorted output)."""
    return sha256(text.encode("utf-8")).hexdigest()
