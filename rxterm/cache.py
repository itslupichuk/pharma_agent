"""Tiny SQLite-backed TTL cache for API responses (pickled values)."""

from __future__ import annotations

import pickle
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class Cache:
    def __init__(self, path: Path | None):
        self._lock = threading.Lock()
        self._mem: dict[str, tuple[float, Any]] = {}
        self._db: sqlite3.Connection | None = None
        if path is not None:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                self._db = sqlite3.connect(str(path), check_same_thread=False)
                self._db.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, ts REAL, v BLOB)")
                self._db.commit()
            except sqlite3.Error:
                self._db = None

    def get(self, key: str, ttl: float) -> Any | None:
        now = time.time()
        with self._lock:
            hit = self._mem.get(key)
            if hit and now - hit[0] < ttl:
                return hit[1]
            if self._db is None:
                return None
            row = self._db.execute("SELECT ts, v FROM kv WHERE k = ?", (key,)).fetchone()
        if row and now - row[0] < ttl:
            try:
                value = pickle.loads(row[1])
            except Exception:
                return None
            with self._lock:
                self._mem[key] = (row[0], value)
            return value
        return None

    def set(self, key: str, value: Any) -> None:
        now = time.time()
        with self._lock:
            self._mem[key] = (now, value)
            if self._db is not None:
                try:
                    self._db.execute(
                        "INSERT OR REPLACE INTO kv (k, ts, v) VALUES (?, ?, ?)",
                        (key, now, pickle.dumps(value)),
                    )
                    self._db.commit()
                except (sqlite3.Error, pickle.PicklingError):
                    pass

    def memo(self, key: str, ttl: float, fn: Callable[[], T]) -> T:
        value = self.get(key, ttl)
        if value is None:
            value = fn()
            if value is not None:
                self.set(key, value)
        return value
