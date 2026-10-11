#!/usr/bin/env python3
"""Actual news-length IPTC workload with complete official definitions."""
import asyncio,json
import pandas as pd
from app.core.config import Settings
from app.core.engines import load_engine_config
from app.modules.iptc import IptcModule
from benchmark_models import scenario
from benchmark_pipeline import idle
async def main():
 s=Settings();f=pd.read_csv('/samples/sample-500.csv').fillna('').sample(n=100,random_state=20261011).sort_index().reset_index(drop=True)
 await idle()
 r=await scenario(s,load_engine_config(s.engines_path),IptcModule,'gliner',('official-depth5',1500,None),f,3,8,{'max_depth':5,'engine_options':{'label_descriptions':True,'threshold':0.0,'batch_size':8}})
 print(json.dumps(r),flush=True)
if __name__=='__main__':asyncio.run(main())
