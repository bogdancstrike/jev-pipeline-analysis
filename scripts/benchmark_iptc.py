#!/usr/bin/env python3
"""Measure official IPTC branch depth and model tradeoffs, without creating stored runs."""
import asyncio
import json
from pathlib import Path
import pandas as pd
from app.core.config import Settings
from app.core.engines import load_engine_config
from app.modules.iptc import IptcModule
from benchmark_models import scenario
from benchmark_pipeline import idle

CASES = [
 ('arts', 'A painter opened her exhibition of oil paintings at an art gallery.', 'medtop:01000000'),
 ('war', 'The army launched artillery strikes as the armed conflict intensified.', 'medtop:16000000'),
 ('crime', 'Police arrested a suspect for armed robbery. A criminal trial starts next week.', 'medtop:02000000'),
 ('disaster', 'An earthquake destroyed homes and emergency crews rescued survivors.', 'medtop:03000000'),
 ('economy', 'Annual inflation rose to 7 percent as economic growth slowed and GDP fell.', 'medtop:04000000'),
 ('education', 'The university announced new degree courses for undergraduate students.', 'medtop:05000000'),
 ('environment', 'Scientists warned that global warming and greenhouse gas emissions threaten ecosystems.', 'medtop:06000000'),
 ('health', 'Doctors began a clinical trial of a new medical treatment for cancer.', 'medtop:07000000'),
 ('human', 'A rescued dog reunited with its owner after a remarkable cross-country journey.', 'medtop:08000000'),
 ('labor', 'Workers went on strike over wages and union contract negotiations.', 'medtop:09000000'),
 ('travel', 'Visitors can book guided holiday tours of the island and its beaches.', 'medtop:10000000'),
 ('politics', 'Voters elected a new president after a closely contested national election.', 'medtop:11000000'),
 ('religion', 'Church members attended an Easter service celebrating the resurrection of Jesus.', 'medtop:12000000'),
 ('tech', 'A software company released an artificial intelligence system for computer programming.', 'medtop:13000000'),
 ('social', 'A charity launched a programme to reduce poverty and homelessness.', 'medtop:14000000'),
 ('sport', 'The football team won the championship match with a goal in extra time.', 'medtop:15000000'),
 ('weather', 'The weather forecast predicts heavy rain and strong winds tomorrow.', 'medtop:17000000'),
 ('ro-election', 'Alegătorii au votat la alegerile prezidențiale. Rezultatele arată un nou președinte.', 'medtop:11000000'),
 ('ro-health', 'Medicii din spital au început un nou tratament pentru pacienții bolnavi de cancer.', 'medtop:07000000'),
 ('ro-sport', 'Echipa de fotbal a câștigat finala campionatului cu un gol în prelungiri.', 'medtop:15000000'),
]

async def main():
 s=Settings();configs=load_engine_config(s.engines_path)
 frame=pd.DataFrame({'id':[c[0] for c in CASES], 'text':[c[1] for c in CASES]})
 for engine in ['laya','gliner']:
  for depth in [1,2,3,5]:
   for head in ([384] if engine=='laya' else [None]):
    try:
     await idle()
     variant=('iptc',1500,1024 if engine=='laya' else None)
     result=await scenario(s,configs,IptcModule,engine,variant,frame,2,4,{'max_depth':depth,'engine_options':{'head_max_len':head} if head else {'label_descriptions':True}})
     # The generic benchmark reports leaf IDs. Reconstruct root from official hierarchy.
     from app.modules.iptc import taxonomy,flatten
     roots={node['id']:root['id'] for root in taxonomy()['tree'] for node in flatten([root])}
     checks=[{'id':c[0],'leaf':p,'root':roots.get(p),'correct':roots.get(p)==c[2]} for c,p in zip(CASES,result['predictions'])]
     print(json.dumps({'type':'result','max_depth':depth,'root_correct':sum(c['correct'] for c in checks),'cases':len(checks),'checks':checks,**result}),flush=True)
    except Exception as error:print(json.dumps({'type':'error','engine':engine,'depth':depth,'error':str(error)}),flush=True)

if __name__=='__main__':asyncio.run(main())
