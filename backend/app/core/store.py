"""Persistence: admin overrides of module settings (+ their audit trail) and finished runs.

PostgreSQL in deployment (DATABASE_URL); an in-memory store with the same interface when
it is unset (tests, laptop dev). The schema is created on startup, idempotently: three small
tables do not justify a migration framework, and every statement is `IF NOT EXISTS`.
"""
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

log = logging.getLogger("store")

SCHEMA = """
CREATE TABLE IF NOT EXISTS module_settings (
    module      text PRIMARY KEY,
    config      jsonb NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  text NOT NULL DEFAULT 'admin'
);
CREATE TABLE IF NOT EXISTS module_settings_history (
    id          bigserial PRIMARY KEY,
    module      text NOT NULL,
    action      text NOT NULL,              -- update | reset
    before      jsonb,
    after       jsonb,
    changed_at  timestamptz NOT NULL DEFAULT now(),
    changed_by  text NOT NULL DEFAULT 'admin'
);
CREATE INDEX IF NOT EXISTS module_settings_history_module ON module_settings_history (module, changed_at DESC);
CREATE TABLE IF NOT EXISTS runs (
    id          text PRIMARY KEY,
    filename    text NOT NULL,
    status      text NOT NULL,
    total       integer NOT NULL,
    modules     jsonb NOT NULL,
    created_at  timestamptz NOT NULL,
    wall_s      double precision,
    rows_per_s  double precision,
    metrics     jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS runs_created ON runs (created_at DESC);
"""


class Store(ABC):
    kind: str

    async def start(self) -> None: ...

    async def close(self) -> None: ...

    @abstractmethod
    async def overrides(self) -> dict[str, dict[str, Any]]: ...

    @abstractmethod
    async def set_override(self, module: str, config: dict[str, Any], by: str) -> None: ...

    @abstractmethod
    async def reset_override(self, module: str, by: str) -> None: ...

    @abstractmethod
    async def history(self, module: str | None, limit: int) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def save_run(self, run: dict[str, Any]) -> None: ...

    @abstractmethod
    async def runs(self, limit: int) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def delete_runs(self, ids: list[str]) -> None: ...


class MemoryStore(Store):
    kind = "memory"

    def __init__(self) -> None:
        self._over: dict[str, dict[str, Any]] = {}
        self._meta: dict[str, dict[str, Any]] = {}
        self._hist: list[dict[str, Any]] = []
        self._runs: dict[str, dict[str, Any]] = {}

    async def overrides(self) -> dict[str, dict[str, Any]]:
        return {k: dict(v) for k, v in self._over.items()}

    async def set_override(self, module: str, config: dict[str, Any], by: str) -> None:
        self._hist.append({"id": len(self._hist) + 1, "module": module, "action": "update",
                           "before": self._over.get(module), "after": config, "changed_at": time.time(),
                           "changed_by": by})
        self._over[module] = dict(config)

    async def reset_override(self, module: str, by: str) -> None:
        if module in self._over:
            self._hist.append({"id": len(self._hist) + 1, "module": module, "action": "reset",
                               "before": self._over.pop(module), "after": None, "changed_at": time.time(),
                               "changed_by": by})

    async def history(self, module: str | None, limit: int) -> list[dict[str, Any]]:
        rows = [h for h in self._hist if module is None or h["module"] == module]
        return list(reversed(rows))[:limit]

    async def save_run(self, run: dict[str, Any]) -> None:
        self._runs[run["id"]] = run

    async def runs(self, limit: int) -> list[dict[str, Any]]:
        return sorted(self._runs.values(), key=lambda r: r["created_at"], reverse=True)[:limit]

    async def delete_runs(self, ids: list[str]) -> None:
        for run_id in ids:
            self._runs.pop(run_id, None)


class PostgresStore(Store):
    kind = "postgres"

    def __init__(self, url: str):
        self.url = url
        self.pool = None

    async def start(self) -> None:
        from psycopg_pool import AsyncConnectionPool

        self.pool = AsyncConnectionPool(self.url, min_size=1, max_size=5, open=False,
                                        kwargs={"autocommit": True})
        await self.pool.open(wait=True, timeout=60)
        async with self.pool.connection() as c:
            await c.execute(SCHEMA)
        log.info("postgres store ready")

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    async def overrides(self) -> dict[str, dict[str, Any]]:
        async with self.pool.connection() as c:
            cur = await c.execute("SELECT module, config FROM module_settings")
            return {m: cfg for m, cfg in await cur.fetchall()}

    async def set_override(self, module: str, config: dict[str, Any], by: str) -> None:
        async with self.pool.connection() as c, c.transaction():
            cur = await c.execute("SELECT config FROM module_settings WHERE module = %s FOR UPDATE", (module,))
            row = await cur.fetchone()
            await c.execute(
                "INSERT INTO module_settings (module, config, updated_at, updated_by) VALUES (%s, %s, now(), %s) "
                "ON CONFLICT (module) DO UPDATE SET config = EXCLUDED.config, updated_at = now(), "
                "updated_by = EXCLUDED.updated_by", (module, json.dumps(config), by))
            await c.execute("INSERT INTO module_settings_history (module, action, before, after, changed_by) "
                            "VALUES (%s, 'update', %s, %s, %s)",
                            (module, json.dumps(row[0]) if row else None, json.dumps(config), by))

    async def reset_override(self, module: str, by: str) -> None:
        async with self.pool.connection() as c, c.transaction():
            cur = await c.execute("DELETE FROM module_settings WHERE module = %s RETURNING config", (module,))
            row = await cur.fetchone()
            if row:
                await c.execute("INSERT INTO module_settings_history (module, action, before, after, changed_by) "
                                "VALUES (%s, 'reset', %s, NULL, %s)", (module, json.dumps(row[0]), by))

    async def history(self, module: str | None, limit: int) -> list[dict[str, Any]]:
        async with self.pool.connection() as c:
            cur = await c.execute(
                "SELECT id, module, action, before, after, extract(epoch FROM changed_at), changed_by "
                "FROM module_settings_history WHERE (%s::text IS NULL OR module = %s) "
                "ORDER BY changed_at DESC, id DESC LIMIT %s", (module, module, limit))
            keys = ("id", "module", "action", "before", "after", "changed_at", "changed_by")
            return [dict(zip(keys, (*r[:5], float(r[5]), r[6]))) for r in await cur.fetchall()]

    async def save_run(self, run: dict[str, Any]) -> None:
        async with self.pool.connection() as c:
            await c.execute(
                "INSERT INTO runs (id, filename, status, total, modules, created_at, wall_s, rows_per_s, metrics) "
                "VALUES (%s, %s, %s, %s, %s, to_timestamp(%s), %s, %s, %s) ON CONFLICT (id) DO UPDATE SET "
                "status = EXCLUDED.status, wall_s = EXCLUDED.wall_s, rows_per_s = EXCLUDED.rows_per_s, "
                "metrics = EXCLUDED.metrics",
                (run["id"], run["filename"], run["status"], run["total"], json.dumps(run["modules"]),
                 run["created_at"], run["wall_s"], run["rows_per_s"], json.dumps(run["metrics"])))

    async def runs(self, limit: int) -> list[dict[str, Any]]:
        async with self.pool.connection() as c:
            cur = await c.execute(
                "SELECT id, filename, status, total, modules, extract(epoch FROM created_at), wall_s, rows_per_s, "
                "metrics FROM runs ORDER BY created_at DESC LIMIT %s", (limit,))
            keys = ("id", "filename", "status", "total", "modules", "created_at", "wall_s", "rows_per_s", "metrics")
            return [dict(zip(keys, (*r[:5], float(r[5]), *r[6:]))) for r in await cur.fetchall()]

    async def delete_runs(self, ids: list[str]) -> None:
        async with self.pool.connection() as c:
            await c.execute("DELETE FROM runs WHERE id = ANY(%s)", (ids,))


def make_store(database_url: str) -> Store:
    return PostgresStore(database_url) if database_url else MemoryStore()
