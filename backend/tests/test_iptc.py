import json
import logging
from types import SimpleNamespace

import pandas as pd
import pytest

from app.core.engines import Classification, EngineRegistry, load_engine_config
from app.core.modules import ModuleContext
from app.core.pipeline import Job
from app.modules.iptc import IptcModule, flatten, option_key, taxonomy
from tests.conftest import make_settings
from .test_api import api  # noqa: F401 — shared HTTP fixture


def module(**overrides):
    settings = make_settings()
    registry = EngineRegistry(settings, load_engine_config(settings.engines_path))
    return IptcModule(ModuleContext(settings, {'engine': 'laya', 'instructions': 'Classify the main subject.', **overrides}, registry, logging.getLogger('test')))


def test_official_snapshot_has_valid_unique_active_topics_and_semantic_options():
    ref = taxonomy()
    nodes = list(flatten(ref['tree']))
    assert len(ref['tree']) == 17 and len(nodes) == ref['concepts'] == 1085
    assert len({n['id'] for n in nodes}) == len(nodes)
    assert next(n['name'] for n in nodes if n['id'] == 'medtop:20000750') == 'linguistics'
    assert all(n['name'] and n['definition'] for n in nodes)
    for parent in nodes:
        children = parent.get('children', [])
        assert len({option_key(c) for c in children}) == len(children)
    question, _ = module().question(ref['tree'])
    assert all('medtop:' not in key for key in question.criteria)
    assert 'CC BY 4.0' == ref['license']


@pytest.mark.asyncio
async def test_hierarchy_batches_by_branch_and_filters_by_ancestor():
    m = module(max_depth=3)
    calls = []
    async def classify(texts, question, options):
        calls.append((len(texts), question))
        return [Classification('sport' if question.key == 'iptc_root' else next(key for key in question.criteria if key != 'broader_topic_only'), .9, {next(iter(question.criteria)): .9}) for _ in texts]
    m.engine.classify = classify
    job = Job('test', 'test', pd.DataFrame({'id':['a','b','empty'], 'text':['Match report','Another match',' ']}), ['iptc'])
    out = await m.process_rows(job, [0,1,2])
    assert out[2] is None
    assert out[0]['path'][0]['id'] == 'medtop:15000000'
    assert m.matches(out[0], 'medtop:15000000') and m.matches(out[0], 'sport')
    assert not m.matches(out[0], 'medtop:11000000')
    assert all(count == 2 for count, _ in calls)
    columns = m.to_columns(out[0])
    assert json.loads(columns['iptc_path'])[0]['name'] == 'sport'
    assert columns['iptc_name'] == out[0]['name']


@pytest.mark.asyncio
@pytest.mark.parametrize('answer,confidence,reason,review', [('broader_topic_only',.9,'broader_topic',False),('child',.3,'low_confidence',True)])
async def test_unsupported_child_stops_at_supported_parent(answer, confidence, reason, review):
    m = module(max_depth=5, child_min_confidence=.5)
    async def classify(texts, question, options):
        key = 'sport' if question.key == 'iptc_root' else answer if answer != 'child' else next(iter(question.criteria))
        score = .95 if question.key == 'iptc_root' else confidence
        return [Classification(key, score, {key:score}) for _ in texts]
    m.engine.classify = classify
    job = Job('test','test',pd.DataFrame({'id':['a'],'text':['Sport report']}), ['iptc'])
    result = (await m.process_rows(job,[0]))[0]
    assert len(result['path']) == 1 and result['stop_reason'] == reason
    assert m.needs_review(result) is review


@pytest.mark.asyncio
async def test_reference_api_works_offline_and_does_not_depend_on_task_being_enabled(api):
    response = await api.get('/api/modules/iptc/reference')
    assert response.status_code == 200 and len(response.json()['tree']) == 17
    assert (await api.get('/api/modules/ner/reference')).status_code == 404
    assert (await api.get('/api/modules/unknown/reference')).status_code == 404
