import logging

import pandas as pd
import pytest

from app.core.engines import Classification, EngineRegistry, load_engine_config
from app.core.modules import ModuleContext
from app.core.pipeline import Job
from app.modules.event import EventModule
from tests.conftest import make_settings


@pytest.mark.asyncio
async def test_fast_pass_keeps_confident_answers_and_refines_uncertain_and_missing_in_order():
    settings = make_settings()
    registry = EngineRegistry(settings, load_engine_config(settings.engines_path))
    m = EventModule(ModuleContext(settings, {'engine':'laya', 'instructions':'Choose event', 'labels':{'yes':'event','no':'none'}, 'max_chars':100, 'engine_options':{'max_len':1024}, 'fast_pass':{'engines':['laya'], 'max_chars':10, 'engine_options':{'max_len':512}, 'confidence_threshold':.8}}, registry, logging.getLogger('test')))
    calls = []
    async def classify(texts, question, options):
        calls.append((texts, options))
        return [Classification('yes',.95,{'yes':.95}), Classification('no',.4,{'no':.4}), None] if len(calls)==1 else [Classification('yes',.9,{'yes':.9}), Classification('no',.85,{'no':.85})]
    m.engine.classify = classify
    job=Job('test','test',pd.DataFrame({'id':['a','empty','b','c'],'text':['A long first report',' ','A long second report','A long third report']}), ['event'])
    out=await m.process_rows(job,[0,1,2,3])
    assert [r['label'] if r else None for r in out] == ['yes',None,'yes','no']
    assert calls[0][0] == ['A long fir','A long sec','A long thi']
    assert calls[1][0] == ['A long second report','A long third report']
    assert calls[0][1]['max_len']==512 and calls[1][1]['max_len']==1024
    assert out[2]['top'] == [['yes',.9]]


@pytest.mark.asyncio
async def test_fast_pass_is_not_applied_to_a_different_engine():
    settings=make_settings(); registry=EngineRegistry(settings,load_engine_config(settings.engines_path))
    m=EventModule(ModuleContext(settings,{'engine':'gliner','instructions':'Choose event','labels':{'yes':'event','no':'none'},'fast_pass':{'engines':['laya'],'max_chars':3}},registry,logging.getLogger('test')))
    calls=[]
    async def classify(texts, question, options):
        calls.append(texts);return [Classification('yes',.9,{'yes':.9})]
    m.engine.classify=classify
    job=Job('test','test',pd.DataFrame({'id':['a'],'text':['Full document text']}),['event'])
    await m.process_rows(job,[0])
    assert calls==[['Full document text']]
