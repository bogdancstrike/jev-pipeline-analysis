#!/usr/bin/env python3
"""Test the event fast-pass candidate on a held-out synthetic sample, same model and prompts."""
import asyncio
import json
import pandas as pd
from app.core.config import Settings
from app.core.engines import load_engine_config
from app.modules.event import EventModule
from benchmark_models import scenario
from benchmark_pipeline import idle

async def main():
 s=Settings(); f=pd.read_csv('/samples/sample-500.csv').fillna('')
 calibration=f.sample(n=100,random_state=20261011).index
 heldout=f.drop(index=calibration).reset_index(drop=True)
 print(json.dumps({'type':'metadata','rows':len(heldout),'excluded_calibration_rows':100,'note':'Synthetic held-out rows, not production ground truth.'}),flush=True)
 for variant in ['standard','adaptive']:
  await idle()
  fast={'engines':['laya'],'max_chars':1500,'engine_options':{'max_len':512},'confidence_threshold':.8} if variant=='adaptive' else {}
  r=await scenario(s,load_engine_config(s.engines_path),EventModule,'laya',(variant,3500,1024),heldout,3,8,{'fast_pass':fast})
  print(json.dumps({'type':'result',**r}),flush=True)

if __name__=='__main__':asyncio.run(main())
