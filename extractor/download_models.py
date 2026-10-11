"""Build-time only: bake the configured GLiNER2 checkpoints into the image (runtime is offline)."""
import json
import os

from huggingface_hub import snapshot_download

for alias, repo in json.loads(os.environ["EXTRACTOR_MODELS"]).items():
    path = snapshot_download(repo)
    print(f"cached {alias} = {repo} -> {path}")
