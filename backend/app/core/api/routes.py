"""HTTP API. Thin: parse, call the platform, shape the answer."""
import asyncio
import json
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from ..csv_io import CsvError, parse_csv
from ..errors import Conflict, InvalidInput, NotFound, PayloadTooLarge, Unavailable
from ..pipeline import JobStatus
from .deps import JobDep, PlatformDep
from .schemas import AppConfig, ErrorBody, JobSnapshot, RowDetail, RowPage

router = APIRouter(prefix="/api", responses={404: {"model": ErrorBody}, 422: {"model": ErrorBody}})


# ------------------------------------------------------------------------ system
@router.get("/health", tags=["system"])
async def health(platform: PlatformDep) -> dict[str, Any]:
    """Readiness of every module and backing model service. Always 200: the UI reads it."""
    return platform.health()


@router.get("/config", response_model=AppConfig, tags=["system"])
async def config(platform: PlatformDep):
    """Enabled modules (with their labels), default selection and upload limits."""
    return platform.describe()


@router.get("/samples", tags=["system"])
async def samples(platform: PlatformDep) -> list[dict[str, Any]]:
    """Sample datasets on the server (files + row counts)."""
    return platform.samples()


@router.get("/samples/{name}", tags=["system"])
async def sample_file(platform: PlatformDep, name: str):
    try:
        return FileResponse(platform.sample_path(name), media_type="text/csv", filename=name)
    except KeyError:
        raise NotFound(f"no sample named {name!r}") from None


# ------------------------------------------------------------------------ jobs
@router.get("/jobs", response_model=list[JobSnapshot], tags=["jobs"])
async def list_jobs(platform: PlatformDep):
    return [j.snapshot() for j in platform.jobs.all()]


def _selected_modules(platform, modules: str | list[str]):
    names = modules if isinstance(modules, list) else [n.strip() for n in modules.split(",") if n.strip()]
    selected = platform.registry.closure(names or platform.registry.defaults())
    not_ready = [m.name for m in selected if not m.ready]
    if not_ready:
        raise Unavailable(f"still loading: {', '.join(not_ready)}. Try again in a minute.",
                          details={"modules": not_ready}, headers={"retry-after": "10"})
    return selected


async def _submit(platform, filename: str, data: bytes, selected):
    try:
        df = await asyncio.to_thread(parse_csv, data, platform.settings.max_rows, platform.output_columns())
    except CsvError as e:
        raise InvalidInput(str(e)) from e
    return platform.jobs.submit(filename, df, selected).snapshot()


@router.post("/jobs", status_code=202, response_model=JobSnapshot, tags=["jobs"],
             responses={413: {"model": ErrorBody}, 503: {"model": ErrorBody}})
async def create_job(platform: PlatformDep, file: UploadFile,
                     modules: Annotated[str, Form(description="comma-separated module names; empty = defaults")] = ""):
    s = platform.settings
    selected = _selected_modules(platform, modules)
    limit = s.max_upload_mb * 1024 * 1024
    buf = bytearray()
    while chunk := await file.read(1 << 20):  # stream, never trust Content-Length
        buf.extend(chunk)
        if len(buf) > limit:
            raise PayloadTooLarge(f"file larger than {s.max_upload_mb} MB")
    return await _submit(platform, file.filename or "upload.csv", bytes(buf), selected)


class TextJob(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=1000, description="one article per item")
    modules: list[str] = Field(default_factory=list, description="empty = defaults")


@router.post("/jobs/text", status_code=202, response_model=JobSnapshot, tags=["jobs"],
             responses={503: {"model": ErrorBody}})
async def create_text_job(platform: PlatformDep, body: TextJob):
    """Start a job on pasted text: no CSV needed to try an article or two."""
    import pandas as pd
    texts = [t for t in body.texts if t.strip()]
    if not texts:
        raise InvalidInput("paste at least one non-empty text")
    if any(len(t) > platform.settings.max_text_chars for t in texts):
        raise InvalidInput(f"a text is longer than {platform.settings.max_text_chars:,} characters")
    selected = _selected_modules(platform, body.modules)
    df = pd.DataFrame({"id": [str(i + 1) for i in range(len(texts))], "text": texts})
    name = "pasted text" if len(texts) == 1 else f"pasted texts ({len(texts)})"
    return platform.jobs.submit(name, df, selected).snapshot()


@router.get("/runs", tags=["jobs"])
async def runs(platform: PlatformDep, limit: int = Query(100, ge=1, le=1000)) -> list[dict[str, Any]]:
    """Finished runs with their metrics, from the store (survives restarts)."""
    return await platform.store.runs(limit)


class SampleJob(BaseModel):
    sample: str = Field(description="a file name from GET /api/samples")
    modules: list[str] = Field(default_factory=list, description="empty = defaults")


@router.post("/jobs/sample", status_code=202, response_model=JobSnapshot, tags=["jobs"],
             responses={503: {"model": ErrorBody}})
async def create_sample_job(platform: PlatformDep, body: SampleJob):
    """Start a job on a server-side sample: no 250 MB round trip through the browser."""
    selected = _selected_modules(platform, body.modules)
    try:
        path = platform.sample_path(body.sample)
    except KeyError:
        raise NotFound(f"no sample named {body.sample!r}") from None
    return await _submit(platform, path.name, await asyncio.to_thread(path.read_bytes), selected)


@router.get("/jobs/{job_id}", response_model=JobSnapshot, tags=["jobs"])
async def get_job(job: JobDep):
    return job.snapshot()


@router.post("/jobs/{job_id}/cancel", response_model=JobSnapshot, tags=["jobs"],
             responses={409: {"model": ErrorBody}})
async def cancel_job(job: JobDep, platform: PlatformDep):
    if not platform.jobs.cancel(job):
        raise Conflict(f"job is already {job.status}")
    for _ in range(40):  # let the task observe the cancellation, so the answer is final
        if job.status.terminal:
            break
        await asyncio.sleep(0.05)
    return job.snapshot()


@router.delete("/jobs/{job_id}", status_code=204, tags=["jobs"])
async def delete_job(job: JobDep, platform: PlatformDep):
    platform.jobs.delete(job)
    return Response(status_code=204)


@router.get("/jobs/{job_id}/events", tags=["jobs"])
async def job_events(request: Request, job: JobDep):
    """Server-Sent Events: one snapshot whenever the job changed, at most once a second
    (the UI commits at most every 2 s; a keep-alive comment keeps proxies from timing out)."""
    async def stream():
        seen = -1
        while not await request.is_disconnected():
            if job.version != seen:
                seen = job.version
                yield f"data: {json.dumps(job.snapshot())}\n\n"
                if job.status.terminal:
                    return
            else:
                yield ": keep-alive\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/jobs/{job_id}/summary", tags=["jobs"])
async def job_summary(job: JobDep, platform: PlatformDep) -> dict[str, Any]:
    """Per-module aggregates (label counts, top entities, event clusters)."""
    return platform.summary(job)


@router.get("/jobs/{job_id}/metrics", tags=["jobs"])
async def job_metrics(job: JobDep, platform: PlatformDep) -> dict[str, Any]:
    """Timings for the dashboard: per-module windows, latencies, throughput timeline, engines."""
    return platform.job_metrics(job)


@router.get("/engines/metrics", tags=["system"])
async def engine_metrics(platform: PlatformDep) -> dict[str, Any]:
    """Per-engine request counts, errors, retries, in-flight and latency since start."""
    return platform.engine_metrics()


@router.get("/jobs/{job_id}/rows", response_model=RowPage, tags=["jobs"])
async def job_rows(job: JobDep, platform: PlatformDep,
                   offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500),
                   f: Annotated[list[str], Query(description="module:value, e.g. sentiment:negative")] = [],  # noqa: B006
                   review: bool = False, errors: bool = False, q: str = ""):
    filters = []
    for item in f:
        name, sep, value = item.partition(":")
        if not sep or name not in job.modules:
            raise InvalidInput(f"bad filter {item!r}: expected module:value for a module of this job")
        filters.append((name, value))
    query = q.strip().casefold()
    idx = [i for i in range(job.total) if platform.row_matches(job, i, filters, review, errors, query)]
    return {"total": len(idx), "items": [platform.row_item(job, i) for i in idx[offset: offset + limit]]}


@router.get("/jobs/{job_id}/rows/{idx}", response_model=RowDetail, tags=["jobs"])
async def job_row(job: JobDep, platform: PlatformDep, idx: int):
    if not 0 <= idx < job.total:
        raise NotFound("row out of range")
    return platform.row_detail(job, idx)


@router.get("/jobs/{job_id}/result.csv", tags=["jobs"], responses={409: {"model": ErrorBody}})
async def job_result(job: JobDep, platform: PlatformDep):
    """The original CSV plus every module's columns. Partial results once a job stopped."""
    if not job.status.terminal:
        raise Conflict(f"job is {job.status}; the CSV is available once it stops")
    data = await asyncio.to_thread(platform.export, job)
    stem = job.filename.rsplit(".", 1)[0]
    name = f"{stem}.enriched.csv" if job.status == JobStatus.DONE else f"{stem}.partial.csv"
    ascii_name = "".join(ch if ch.isascii() and ch.isprintable() and ch not in '"\\' else "_" for ch in name)
    return Response(data, media_type="text/csv; charset=utf-8", headers={
        # RFC 6266/5987: ASCII fallback + UTF-8 name (Romanian filenames would break latin-1 headers)
        "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"})
