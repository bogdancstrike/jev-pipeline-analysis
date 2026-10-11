"""Admin API: edit task settings (labels, instructions, thresholds, engine) at runtime.

Overrides are stored in PostgreSQL and laid over the YAML defaults (top-level keys replace).
Every save is validated by building the whole module graph with it first: an override that
would break a module (too few labels, an engine of the wrong kind, a disabled dependency)
is refused with the reason, and nothing changes.

Not authenticated in this PoC: put it behind the UI's SSO (e.g. oauth2-proxy + Keycloak).
"""
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ..errors import InvalidInput, NotFound
from .deps import PlatformDep

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Keys the editor must never change: they shape code paths, not options.
FORBIDDEN = {"name", "kind", "scope", "requires"}


def _view(platform, cls) -> dict[str, Any]:
    name = cls.name
    defaults = platform.defaults(name)
    override = platform.overrides.get(name)
    live = name in platform.registry
    return {
        "name": name, "title": cls.title, "description": cls.description, "kind": str(cls.kind),
        "enabled": live, "requires": list(cls.requires),
        "engine_kinds": list(cls.engine_kinds),
        "engine_choices": [n for n, c in platform.engines.configs.items() if c.get("kind") in cls.engine_kinds],
        "defaults": defaults, "override": override,
        "effective": {**defaults, **(override or {})},
    }


@router.get("/modules")
async def modules(platform: PlatformDep) -> list[dict[str, Any]]:
    return [_view(platform, c) for c in platform.catalog]


@router.get("/modules/{name}")
async def module(platform: PlatformDep, name: str) -> dict[str, Any]:
    try:
        return _view(platform, platform.module_class(name))
    except KeyError:
        raise NotFound(f"no module {name!r}") from None


class OverrideBody(BaseModel):
    config: dict[str, Any] = Field(description="top-level keys that replace the YAML defaults")
    changed_by: str = "admin"


@router.put("/modules/{name}")
async def save(platform: PlatformDep, name: str, body: OverrideBody) -> dict[str, Any]:
    try:
        cls = platform.module_class(name)
    except KeyError:
        raise NotFound(f"no module {name!r}") from None
    bad = sorted(FORBIDDEN & set(body.config))
    if bad:
        raise InvalidInput(f"these keys cannot be overridden: {', '.join(bad)}")
    defaults = platform.defaults(name)
    # Store only what differs from the defaults: a "save" of unchanged values is a reset.
    override = {k: v for k, v in body.config.items() if defaults.get(k) != v}
    candidate = {**platform.overrides}
    if override:
        candidate[name] = override
    else:
        candidate.pop(name, None)
    try:
        await platform.apply_overrides(candidate)
    except (ValueError, TypeError, KeyError) as e:
        raise InvalidInput(f"not saved: {e}", details={"module": name}) from e
    if override:
        await platform.store.set_override(name, override, body.changed_by)
    else:
        await platform.store.reset_override(name, body.changed_by)
    return _view(platform, cls)


@router.delete("/modules/{name}")
async def reset(platform: PlatformDep, name: str, changed_by: str = "admin") -> dict[str, Any]:
    try:
        cls = platform.module_class(name)
    except KeyError:
        raise NotFound(f"no module {name!r}") from None
    candidate = {k: v for k, v in platform.overrides.items() if k != name}
    try:
        await platform.apply_overrides(candidate)
    except ValueError as e:
        raise InvalidInput(f"not reset: {e}") from e
    await platform.store.reset_override(name, changed_by)
    return _view(platform, cls)


@router.get("/history")
async def history(platform: PlatformDep, module: str | None = None,
                  limit: int = Query(50, ge=1, le=500)) -> list[dict[str, Any]]:
    return await platform.store.history(module, limit)


@router.get("/engines")
async def engines(platform: PlatformDep) -> dict[str, Any]:
    """The engine catalogue (config/engines.yaml, read-only here: it is infrastructure)."""
    return {"store": platform.store.kind, "engines": platform.engines.configs}
