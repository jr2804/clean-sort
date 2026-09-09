"""Tests for the content-hash skip cache."""

from __future__ import annotations

import json
import time
from pathlib import Path

from clean_sort import Config
from clean_sort.cache import Cache, hash_text


def test_hash_text_deterministic() -> None:
    assert hash_text("hello") == hash_text("hello")
    assert hash_text("hello") != hash_text("world")


def test_cache_empty_on_missing_path() -> None:
    cache = Cache(None)
    cache.load()
    assert cache.path is None
    assert not cache.lookup("sig", "src_hash", "cur_hash")


def test_cache_lookup_hit(tmp_path: Path) -> None:
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(
        json.dumps({"sig:src_hash": {"hash": "sorted_hash", "seen": time.time()}}),
        encoding="utf-8",
    )
    cache = Cache(cache_file)
    cache.load()
    assert cache.lookup("sig", "src_hash", "sorted_hash") is True


def test_cache_lookup_miss_wrong_key(tmp_path: Path) -> None:
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(
        json.dumps({"sig:other_hash": {"hash": "sorted_hash", "seen": time.time()}}),
        encoding="utf-8",
    )
    cache = Cache(cache_file)
    cache.load()
    assert cache.lookup("sig", "src_hash", "sorted_hash") is False


def test_cache_lookup_miss_content_changed(tmp_path: Path) -> None:
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(
        json.dumps({"sig:src_hash": {"hash": "sorted_hash", "seen": time.time()}}),
        encoding="utf-8",
    )
    cache = Cache(cache_file)
    cache.load()
    # Current content hash differs from stored sorted hash → miss
    assert cache.lookup("sig", "src_hash", "different_hash") is False


def test_cache_record_and_save(tmp_path: Path) -> None:
    cache_file = tmp_path / "cache.json"
    cache = Cache(cache_file)
    cache.load()
    cache.record("sig", "src_hash", "sorted_hash")
    cache.save()
    assert cache_file.exists()
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert data["sig:src_hash"]["hash"] == "sorted_hash"
    assert "seen" in data["sig:src_hash"]


def test_cache_idempotent_save(tmp_path: Path) -> None:
    cache_file = tmp_path / "cache.json"
    cache = Cache(cache_file)
    cache.load()
    cache.record("sig", "src_hash", "sorted_hash")
    cache.save()
    first = cache_file.read_text(encoding="utf-8")
    # Save again without changes → no write
    cache.save()
    second = cache_file.read_text(encoding="utf-8")
    assert first == second


def test_cache_old_format_migration(tmp_path: Path) -> None:
    """Old-format caches (plain hash strings) are migrated on load."""
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(
        json.dumps({"sig:src_hash": "sorted_hash"}),
        encoding="utf-8",
    )
    cache = Cache(cache_file)
    cache.load()
    assert cache.lookup("sig", "src_hash", "sorted_hash") is True


def test_cache_ttl_pruning(tmp_path: Path) -> None:
    """Entries older than ttl_days are pruned on load."""
    cache_file = tmp_path / "cache.json"
    old_seen = time.time() - 31 * 86400
    cache_file.write_text(
        json.dumps({"sig:src_hash": {"hash": "sorted_hash", "seen": old_seen}}),
        encoding="utf-8",
    )
    cache = Cache(cache_file, ttl_days=30)
    cache.load()
    assert cache.lookup("sig", "src_hash", "sorted_hash") is False


def test_cache_ttl_disabled(tmp_path: Path) -> None:
    """ttl_days=0 disables pruning."""
    cache_file = tmp_path / "cache.json"
    old_seen = time.time() - 365 * 86400
    cache_file.write_text(
        json.dumps({"sig:src_hash": {"hash": "sorted_hash", "seen": old_seen}}),
        encoding="utf-8",
    )
    cache = Cache(cache_file, ttl_days=0)
    cache.load()
    assert cache.lookup("sig", "src_hash", "sorted_hash") is True


def test_cache_seen_refresh(tmp_path: Path) -> None:
    """Lookup refreshes the seen timestamp."""
    cache_file = tmp_path / "cache.json"
    old_seen = time.time() - 29 * 86400
    cache_file.write_text(
        json.dumps({"sig:src_hash": {"hash": "sorted_hash", "seen": old_seen}}),
        encoding="utf-8",
    )
    cache = Cache(cache_file, ttl_days=30)
    cache.load()
    cache.lookup("sig", "src_hash", "sorted_hash")
    cache.save()
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert data["sig:src_hash"]["seen"] > old_seen + 86000


def test_cache_config_signature_changes_invalidate(tmp_path: Path) -> None:
    """Changing config signature invalidates the cache."""
    cache_file = tmp_path / "cache.json"
    cache = Cache(cache_file)
    cache.load()
    cache.record("old_sig", "src_hash", "sorted_hash")
    cache.save()
    # New config signature → miss
    assert cache.lookup("new_sig", "src_hash", "sorted_hash") is False


def test_cache_merge(tmp_path: Path) -> None:
    """Merge external entries into the cache."""
    cache_file = tmp_path / "cache.json"
    cache = Cache(cache_file)
    cache.load()
    cache.record("sig1", "src1", "sorted1")
    cache.save()
    # Simulate parallel worker entries
    cache.merge({"sig2:src2": {"hash": "sorted2", "seen": time.time()}})
    cache.save()
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert "sig1:src1" in data
    assert "sig2:src2" in data


def test_cache_corrupt_file(tmp_path: Path) -> None:
    """Corrupt cache files are treated as empty."""
    cache_file = tmp_path / "cache.json"
    cache_file.write_text("not json", encoding="utf-8")
    cache = Cache(cache_file)
    cache.load()
    assert not cache.lookup("sig", "src_hash", "sorted_hash")


def test_cache_config_signature_from_config() -> None:
    """Config.config_signature() is deterministic."""
    cfg1 = Config()
    cfg2 = Config()
    assert cfg1.config_signature() == cfg2.config_signature()


def test_cache_config_signature_changes_with_sections() -> None:
    """Changing sections changes the config signature."""
    cfg1 = Config()
    cfg2 = Config()
    cfg2.sections = ["imports", "functions"]
    assert cfg1.config_signature() != cfg2.config_signature()
