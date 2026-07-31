"""Tests for the content-hash skip cache."""
from __future__ import annotations

import json
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
        json.dumps({"sig:src_hash": "sorted_hash"}),
        encoding="utf-8",
    )
    cache = Cache(cache_file)
    cache.load()
    assert cache.lookup("sig", "src_hash", "sorted_hash") is True


def test_cache_lookup_miss_wrong_key(tmp_path: Path) -> None:
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(
        json.dumps({"sig:other_hash": "sorted_hash"}),
        encoding="utf-8",
    )
    cache = Cache(cache_file)
    cache.load()
    assert cache.lookup("sig", "src_hash", "sorted_hash") is False


def test_cache_lookup_miss_content_changed(tmp_path: Path) -> None:
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(
        json.dumps({"sig:src_hash": "sorted_hash"}),
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
    assert data["sig:src_hash"] == "sorted_hash"


def test_cache_save_is_atomic(tmp_path: Path) -> None:
    cache_file = tmp_path / "cache.json"
    cache = Cache(cache_file)
    cache.load()
    cache.record("sig", "src_hash", "sorted_hash")
    cache.save()
    # Verify no .tmp file remains
    assert not list(tmp_path.glob("*.tmp"))
    # Verify content is valid JSON
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert data["sig:src_hash"] == "sorted_hash"


def test_cache_corrupt_file_treated_as_empty(tmp_path: Path) -> None:
    cache_file = tmp_path / "cache.json"
    cache_file.write_text("not valid json", encoding="utf-8")
    cache = Cache(cache_file)
    cache.load()
    assert not cache.lookup("sig", "src_hash", "sorted_hash")


def test_cache_no_save_when_not_dirty(tmp_path: Path) -> None:
    cache_file = tmp_path / "cache.json"
    cache = Cache(cache_file)
    cache.load()
    cache.save()  # no-op, no dirty flag
    assert not cache_file.exists()


def test_cache_config_signature_changes_with_fields() -> None:
    cfg1 = Config()
    cfg2 = Config(strategies={"functions": "alpha"})
    assert cfg1.config_signature() != cfg2.config_signature()


def test_cache_config_signature_stable() -> None:
    cfg = Config()
    assert cfg.config_signature() == cfg.config_signature()
