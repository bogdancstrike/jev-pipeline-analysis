"""End to end over HTTP: real modules, real config, the curated edge-case CSV, fake model services."""
import asyncio
import csv
import io
import json

import httpx
import pytest

from app.main import create_app

from .conftest import SAMPLE, build_platform, make_settings


@pytest.fixture
async def api():
    p = build_platform()
    app = create_app(make_settings(), platform=p)
    async with app.router.lifespan_context(app):
        for e in p.engines.used:
            await e.wait_ready()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            yield c


async def run_sample(api, modules: str = "") -> dict:
    files = {"file": ("sample.csv", SAMPLE.read_bytes(), "text/csv")}
    r = await api.post("/api/jobs", files=files, data={"modules": modules})
    assert r.status_code == 202, r.text
    job = r.json()
    for _ in range(500):
        job = (await api.get(f"/api/jobs/{job['id']}")).json()
        if job["status"] in ("done", "failed", "cancelled"):
            break
        await asyncio.sleep(0.02)
    assert job["status"] == "done", job
    return job


@pytest.mark.asyncio
async def test_health_and_config_describe_every_module(api):
    h = (await api.get("/api/health")).json()
    assert h["status"] == "ready" and set(h["engines"]) == {"gliner", "laya"}
    assert all(e["ready"] for e in h["engines"].values())
    cfg = (await api.get("/api/config")).json()
    names = [m["name"] for m in cfg["modules"]]
    assert names == ["language", "category", "relevance", "routing", "risk", "ner", "entity_resolution",
                     "relations", "fields", "event", "event_coreference", "sentiment", "intent",
                     "toxicity", "propaganda"]
    engine_of = {m["name"]: m["engine"] for m in cfg["modules"]}
    assert engine_of["ner"] == engine_of["category"] == engine_of["fields"] == "gliner"
    assert engine_of["sentiment"] == engine_of["risk"] == engine_of["routing"] == "laya"
    assert [x["rows"] for x in cfg["samples"]][:5] == [50, 500, 5000, 15000, 30000]
    assert all(m["labels"] for m in cfg["modules"] if m["kind"] == "label")


@pytest.mark.asyncio
async def test_full_run_on_the_sample(api):
    job = await run_sample(api)
    assert job["total"] == 50 and job["failed_rows"] == 0
    assert set(job["progress"]) == set(job["modules"])

    summary = (await api.get(f"/api/jobs/{job['id']}/summary")).json()["modules"]
    assert summary["language"]["counts"].get("ro", 0) > 10
    assert summary["entity_resolution"]["entities"] > 0
    assert sum(summary["sentiment"]["counts"].values()) == 49  # the empty row is left blank, not guessed

    row = (await api.get(f"/api/jobs/{job['id']}/rows/0")).json()
    assert set(row["results"]) == set(job["modules"])

    r = await api.get(f"/api/jobs/{job['id']}/result.csv")
    out = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert len(out) == 50
    for col in ("language", "category", "category_confidence", "relevance", "relevance_score", "routing",
                "risk", "risk_score", "fields", "NER", "entities", "relations", "event",
                "event_cluster", "sentiment", "sentiment_score", "intent", "toxicity", "toxicity_score",
                "propaganda", "propaganda_techniques"):
        assert col in out[0], col
    json.loads(out[0]["NER"])
    # OWASP: a cell starting with "=" is neutralized in the export.
    assert all(not v.startswith("=") for row in out for v in row.values() if v)


@pytest.mark.asyncio
async def test_module_selection_pulls_in_dependencies(api):
    job = await run_sample(api, "relations")
    assert job["modules"] == ["ner", "entity_resolution", "relations"]


@pytest.mark.asyncio
async def test_row_filters(api):
    job = await run_sample(api, "language,sentiment")
    jid = job["id"]
    ro = (await api.get(f"/api/jobs/{jid}/rows", params={"f": "language:ro", "limit": 500})).json()
    assert ro["total"] > 0 and all(i["results"]["language"]["label"] == "ro" for i in ro["items"])
    q = (await api.get(f"/api/jobs/{jid}/rows", params={"q": "galați"})).json()
    assert all("galați" in i["preview"].lower() for i in q["items"])
    bad = await api.get(f"/api/jobs/{jid}/rows", params={"f": "nope:x"})
    assert bad.status_code == 422 and bad.json()["error"] == "invalid_input"


@pytest.mark.asyncio
async def test_errors_have_one_shape_and_a_request_id(api):
    r = await api.get("/api/jobs/doesnotexist")
    assert r.status_code == 404 and r.json()["error"] == "not_found" and r.headers["x-request-id"]
    r = await api.post("/api/jobs", files={"file": ("x.csv", b"id,body\n1,x\n", "text/csv")})
    assert r.status_code == 422 and "'id' and 'text'" in r.json()["message"]
    r = await api.post("/api/jobs", files={"file": ("x.csv", b"id,text\n1,x\n", "text/csv")},
                       data={"modules": "nope"})
    assert r.status_code == 422 and r.json()["details"]["available"]


@pytest.mark.asyncio
async def test_job_from_a_server_side_sample(api):
    r = await api.post("/api/jobs/sample", json={"sample": "sample-50.csv", "modules": ["language"]})
    assert r.status_code == 202, r.text
    assert r.json()["total"] == 50 and r.json()["modules"] == ["language"]
    bad = await api.post("/api/jobs/sample", json={"sample": "../../etc/passwd"})
    assert bad.status_code == 404


@pytest.mark.asyncio
async def test_admin_override_is_validated_applied_and_audited(api):
    labels = (await api.get("/api/admin/modules/sentiment")).json()["effective"]["labels"]
    new = {**labels, "sarcastic": "ironic or mocking tone"}
    r = await api.put("/api/admin/modules/sentiment", json={"config": {"labels": new}, "changed_by": "test"})
    assert r.status_code == 200, r.text
    cfg = (await api.get("/api/config")).json()
    assert "sarcastic" in next(m for m in cfg["modules"] if m["name"] == "sentiment")["labels"]
    # Invalid: one label is not a classification. Refused, nothing changes.
    bad = await api.put("/api/admin/modules/sentiment", json={"config": {"labels": {"only": ""}}})
    assert bad.status_code == 422 and "at least 2 labels" in bad.json()["message"]
    # A module on an engine of the wrong kind is refused too.
    bad = await api.put("/api/admin/modules/ner", json={"config": {"engine": "laya"}})
    assert bad.status_code == 422
    hist = (await api.get("/api/admin/history", params={"module": "sentiment"})).json()
    assert hist[0]["changed_by"] == "test" and hist[0]["action"] == "update"
    r = await api.delete("/api/admin/modules/sentiment")
    assert r.json()["override"] is None


@pytest.mark.asyncio
async def test_job_from_pasted_text(api):
    r = await api.post("/api/jobs/text", json={"texts": ["NATO ministers met in Brussels on Thursday."],
                                               "modules": ["language", "ner"]})
    assert r.status_code == 202 and r.json()["total"] == 1 and r.json()["filename"] == "pasted text"
