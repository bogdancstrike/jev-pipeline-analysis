#!/usr/bin/env python3
"""Compare complete pipelines against previous settings, without creating stored runs."""
import argparse,asyncio,copy,json,logging,statistics,time
from pathlib import Path
import pandas as pd,yaml,httpx
from app.core.config import Settings
from app.core.engines import EngineRegistry,load_engine_config
from app.core.modules import ModuleContext
from app.core.pipeline import Job,JobRunner
from app.modules import CATALOG
from benchmark_models import quality

ORIGINAL={'language','category','relevance','routing','risk','ner','entity_resolution','relations','fields','event','event_coreference','sentiment','intent','toxicity','propaganda'}

async def idle():
    async with httpx.AsyncClient() as client:
        while True:
            response=await client.get('http://backend:8000/api/jobs')
            response.raise_for_status()
            if not any(j['status'] in ('queued','running') for j in response.json()):return
            await asyncio.sleep(2)

async def main(args):
    s=Settings();configs=load_engine_config(s.engines_path);base=json.loads(Path(args.baseline).read_text());prompts=json.loads(Path(args.prompts).read_text());frame=pd.read_csv('/samples/sample-500.csv').fillna('').sample(n=args.rows,random_state=20261011).sort_index().reset_index(drop=True)
    outputs={}
    for profile in args.profiles.split(','):
        await idle();reg=EngineRegistry(s,configs);modules=[]
        for cls in CATALOG:
            if cls.name not in ORIGINAL and profile!='extended':continue
            cfg=yaml.safe_load(base[cls.name]) if profile=='baseline' else yaml.safe_load((Path(s.modules_dir)/f'{cls.name}.yaml').read_text())
            if profile=='baseline' and cls.name=='ner':cfg.update(exclude_code=False,money_requires_currency=False)
            if profile!='baseline':
                if cls.name=='category':cfg.update(engine='laya',max_chars=1500,engine_options={'max_len':512})
                if cls.name in ('routing','sentiment','propaganda'):cfg.update(max_chars=3500,engine_options={**cfg.get('engine_options',{}),'max_len':1024})
                if cls.name=='propaganda':
                    cfg['instructions']=prompts['propaganda']['instructions'];cfg['labels']={**cfg['labels'],**prompts['propaganda']['labels']}
                if profile=='speed' and cfg.get('engine')=='laya' and cls.name!='event_coreference':cfg.update(max_chars=1500,engine_options={'max_len':512})
            modules.append(cls(ModuleContext(s,cfg,reg,logging.getLogger(cls.name))))
        await asyncio.gather(*(e.wait_ready() for e in reg.used));await asyncio.gather(*(m.start() for m in modules))
        warm=Job('warm','warm',frame.iloc[:4].copy(),[m.name for m in modules]);await JobRunner(warm,modules).run()
        trials=[]
        for n in range(args.repeats):
            await idle();job=Job('bench','bench',frame.copy(),[m.name for m in modules]);t=time.perf_counter();await JobRunner(job,modules).run();seconds=time.perf_counter()-t
            trials.append({'seconds':seconds,'rows_per_s':len(frame)/seconds,'failed_rows':len(job.failed_rows())})
        outputs[profile]=job.results;predictions={name:[r.get('label') if r else None for r in values] for name,values in job.results.items() if name in ('category','event','relevance','routing','risk','sentiment','intent','toxicity','propaganda')}
        median=statistics.median(t['seconds'] for t in trials)
        print(json.dumps({'type':'result','profile':profile,'rows':len(frame),'repeats':args.repeats,'median_s':median,'rows_per_s':len(frame)/median,'trials':trials,'quality':{name:quality(name,job.results[name],frame) for name in ('category','event')},'predictions':predictions,'modules':{m.name:job.metrics[m.name].snapshot(job.started_at,time.time()) for m in modules},'settings':{m.name:m.cfg for m in modules}}),flush=True)
        await reg.aclose()
    if 'baseline' in outputs:
        for profile in outputs:
            if profile=='baseline':continue
            agreement={}
            for task,original in outputs['baseline'].items():
                if task in ('category','event','relevance','routing','risk','sentiment','intent','toxicity','propaganda'):
                    changed=outputs[profile][task];agreement[task]=sum(bool(a and b) and a['label']==b['label'] for a,b in zip(original,changed))/len(frame)
            print(json.dumps({'type':'agreement','profile':profile,'labels':agreement,'note':'Agreement with previous settings, not accuracy.'}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--rows',type=int,default=100);p.add_argument('--repeats',type=int,default=3);p.add_argument('--profiles',default='baseline,balanced,speed,extended');p.add_argument('--baseline',default='/benchmarks/baseline-configs.json');p.add_argument('--prompts',default='/benchmarks/tuning-overrides.json');logging.basicConfig(level=logging.WARNING);asyncio.run(main(p.parse_args()))
