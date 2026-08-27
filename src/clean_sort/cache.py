"""Content-hash cache for skipping already-sorted files.

The cache maps ``f"{config_signature}:{source_hash}"`` to the hash of the
sorted output. A file is skipped when:

1. its cache key is present, AND
2. the hash of the file's current content equals the stored sorted-output hash.

This invariant means the cache can only ever cause us to skip a file we would
not have modified anyway. Any edit drifts the content hash and forces a full
sort; any config/version change drifts the signature and forces a full sort.

Each entry also stores a ``seen`` timestamp (epoch seconds).  On load,
entries older than ``ttl_days`` are pruned so the cache stays lean even
when files are deleted or projects are abandoned.
"""

from __future__ import annotations

import json
import time
from hashlib import sha256
from pathlib import Path
from typing import Any


class Cache:
    """On-disk content-hash cache keyed by ``config_signature:source_hash``.

    The cache is loaded once at the start of a run and saved once at the end
    (if any new entries were recorded). Reads/writes are atomic on save
    (temp file + rename) to avoid corruption on crash.

    Parameters:
        path: Cache file location (``None`` = in-memory/no-op).
        ttl_days: Entries not seen within this many days are pruned on load.
            ``0`` disables TTL pruning.
    """

    def __init__(self, path: Path | None, *, ttl_days: int = 30) -> None:
        self._path = path
        self._entries: dict[str, dict[str, Any]] = {}
        self._dirty = False
        self._ttl_days = ttl_days

    @property
    def path(self) -> Path | None:
        """Where this cache is stored on disk (``None`` = in-memory/no-op)."""
        return self._path

    def load(self) -> None:
        """Read the cache file. Missing or corrupt files are treated as empty.

        Old-format caches (plain hash strings) are migrated to the new
        ``{hash, seen}`` format with ``seen`` set to *now*.  Entries whose
        ``seen`` timestamp is older than ``ttl_days`` days are dropped.
        """
        if self._path is None or not self._path.exists():
            self._entries = {}
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                self._entries = {}
                return
            now = time.time()
            migrated: dict[str, dict[str, Any]] = {}
            for k, v in data.items():
                if not isinstance(k, str):
                    continue
                if isinstance(v, str):
                    # Old format: plain hash string -> migrate.
                    migrated[k] = {"hash": v, "seen": now}
                elif isinstance(v, dict) and "hash" in v and "seen" in v:
                    migrated[k] = v
            self._entries = migrated
        except (json.JSONDecodeError, OSError):
            # Corrupt cache: silently start fresh. Better a few redundant sorts
            # than a crashed run.
            self._entries = {}
            return
        # Prune expired entries.
        if self._ttl_days > 0:
            cutoff = time.time() - self._ttl_days * 86400
            before = len(self._entries)
            self._entries = {k: v for k, v in self._entries.items() if v.get("seen", 0) >= cutoff}
            if len(self._entries) != before:
                self._dirty = True

    def lookup(self, config_sig: str, source_hash: str, current_content_hash: str) -> bool:
        """True when the file can be skipped (already in sorted state).

        A hit requires the stored sorted-output hash to match the file's current
        content hash -- otherwise the file was edited after caching and must sort.
        On a hit the ``seen`` timestamp is refreshed.
        """
        key = f"{config_sig}:{source_hash}"
        entry = self._entries.get(key)
        if entry is None or entry.get("hash") != current_content_hash:
            return False
        # Refresh last-seen timestamp.
        entry["seen"] = time.time()
        self._dirty = True
        return True

    def record(self, config_sig: str, source_hash: str, sorted_hash: str) -> None:
        """Record (or refresh) the sorted-output hash for a source hash."""
        key = f"{config_sig}:{source_hash}"
        existing = self._entries.get(key)
        if existing is None or existing.get("hash") != sorted_hash:
            self._entries[key] = {"hash": sorted_hash, "seen": time.time()}
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

    def merge(self, entries: dict[str, dict[str, Any]]) -> None:
        """Merge external cache entries (e.g. from parallel workers) into this cache."""
        for key, value in entries.items():
            if self._entries.get(key) != value:
                self._entries[key] = value
                self._dirty = True


def hash_text(text: str) -> str:
    """Stable hex digest of *text*."""
    return sha256(text.encode("utf-8")).hexdigest()
