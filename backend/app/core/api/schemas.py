"""Response shapes, so /api/docs documents the contract the frontend relies on.

Module results stay `Any`: their shape belongs to each module (see `core.modules.Kind`).
"""
from typing import Any

from pydantic import BaseModel


class ErrorBody(BaseModel):
    error: str
    message: str
    details: dict[str, Any] | None = None


class ModuleProgress(BaseModel):
    done: int
    errors: int


class JobSnapshot(BaseModel):
    id: str
    filename: str
    status: str
    error: str | None
    modules: list[str]
    total: int
    done: int
    progress: dict[str, ModuleProgress]
    percent: float
    failed_rows: int
    rows_per_s: float
    eta_s: int | None
    elapsed_s: float
    created_at: float


class RowItem(BaseModel):
    idx: int
    id: str
    preview: str
    results: dict[str, Any]
    review: list[str]
    errors: list[str]


class RowPage(BaseModel):
    total: int
    items: list[RowItem]


class RowDetail(BaseModel):
    idx: int
    id: str
    text: str
    results: dict[str, Any]
    review: list[str]
    errors: dict[str, str]


class AppConfig(BaseModel):
    modules: list[dict[str, Any]]
    engines: dict[str, dict[str, Any]]
    defaults: list[str]
    limits: dict[str, int]
    samples: list[dict[str, Any]]
