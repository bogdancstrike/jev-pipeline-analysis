"""Named model engines, built from `config/engines.yaml`.

    engines:
      laya:   {kind: systemone, url: http://laya:8000, ...}
      gliner: {kind: gliner2,   url: http://extractor:8080, ...}

A module picks one by name (`engine: laya` in its YAML). Only engines some enabled module
uses are started, so an unused engine's service does not have to be running.
"""
import asyncio
from pathlib import Path
from typing import Any

import yaml

from ..config import Settings
from .base import Classification, Engine, EngineError, Question
from .gliner2 import Gliner2Engine
from .systemone import QuestionTooLong, StateTooLong, SystemOneEngine

KINDS: dict[str, type[Engine]] = {"systemone": SystemOneEngine, "gliner2": Gliner2Engine}

__all__ = ["Classification", "Engine", "EngineError", "EngineRegistry", "Gliner2Engine", "Question",
           "QuestionTooLong", "StateTooLong", "SystemOneEngine", "KINDS", "load_engine_config"]


def load_engine_config(path: str) -> dict[str, dict[str, Any]]:
    p = Path(path)
    if not p.is_file():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    engines = data.get("engines") or {}
    if not isinstance(engines, dict):
        raise ValueError(f"{path}: `engines` must be a mapping of name -> config")
    return engines


class EngineRegistry:
    def __init__(self, settings: Settings, configs: dict[str, dict[str, Any]]):
        self.settings, self.configs = settings, configs
        self._engines: dict[str, Engine] = {}

    def get(self, name: str, kinds: tuple[str, ...] | None = None) -> Engine:
        """The engine called `name`, created on first use. `kinds` restricts what the caller accepts."""
        if name not in self._engines:
            cfg = self.configs.get(name)
            if cfg is None:
                raise ValueError(f"engine {name!r} is not defined in engines.yaml (defined: {sorted(self.configs)})")
            kind = cfg.get("kind")
            if kind not in KINDS:
                raise ValueError(f"engine {name!r}: unknown kind {kind!r} (known: {sorted(KINDS)})")
            self._engines[name] = KINDS[kind](name, cfg, self.settings)
        engine = self._engines[name]
        if kinds and engine.kind not in kinds:
            raise ValueError(f"engine {name!r} is {engine.kind}; this module needs one of {kinds}")
        return engine

    def add(self, engine: Engine) -> None:
        """Register a ready-made engine (tests, embedding)."""
        self._engines[engine.name] = engine

    @property
    def used(self) -> list[Engine]:
        return list(self._engines.values())

    async def aclose(self) -> None:
        await asyncio.gather(*(e.aclose() for e in self._engines.values()), return_exceptions=True)
