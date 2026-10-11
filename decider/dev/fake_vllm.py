"""CPU-only stand-in for the vLLM endpoints the decider uses, for GPU-less dev.

  python -m dev.toy_tokenizer /tmp/toy-tokenizer.json
  TOKENIZER_PATH=/tmp/toy-tokenizer.json uvicorn dev.fake_vllm:app --port 9300

Scores options by keyword overlap with the document, like a very dumb model.
"""
import math
import os
import re

from fastapi import FastAPI, Request
from tokenizers import Tokenizer

app = FastAPI()
TOK = Tokenizer.from_file(os.environ.get("TOKENIZER_PATH", "/tmp/toy-tokenizer.json"))
TOK.encode_special_tokens = True


@app.get("/health")
async def health():
    return {}


@app.get("/v1/models")
async def models():
    return {"data": [{"id": "local/fake-qwen-awq", "max_model_len": 6144}]}


@app.post("/tokenize")
async def tokenize(req: Request):
    b = await req.json()
    ids = TOK.encode(b["prompt"], add_special_tokens=False).ids
    return {"tokens": ids, "count": len(ids), "max_model_len": 6144}


@app.post("/v1/completions")
async def completions(req: Request):
    b = await req.json()
    text = TOK.decode(b["prompt"], skip_special_tokens=False)
    doc = text.split("<document>")[-1].split("</document>")[0].lower()
    keys = re.findall(r"^- (\w+)", text, flags=re.M)
    scores = {}
    for t in b["logprob_token_ids"]:
        piece = TOK.decode([t]).strip().lower()
        hits = [k for k in keys if k.lower().startswith(piece)] or [piece]
        scores[t] = 1.0 + max(sum(doc.count(w) for w in k.lower().split("_") if len(w) > 3) for k in hits)
    z = sum(math.exp(v) for v in scores.values()) / 0.9  # leave 10% junk mass
    tops = {f"token_id:{t}": v - math.log(z) for t, v in scores.items()}
    return {"choices": [{"text": "", "logprobs": {"top_logprobs": [tops]}}],
            "usage": {"prompt_tokens": len(b["prompt"])}}
