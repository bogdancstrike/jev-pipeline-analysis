# Reuse the local CUDA/PyTorch runtime; pin Kev's serving code and checkpoint.
FROM decision-csv-poc/laya:latest
USER root
# Triton compiles its CUDA launcher at runtime, even with pre-downloaded weights.
RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev && rm -rf /var/lib/apt/lists/*
ARG KEV_REVISION=2ecafc49fe1e8945cd600443e6c04c1cf0b3a78f
ARG KEV_MODEL=jaredpalmer/kev-0.8b@v1.0
ENV HF_HOME=/models/kev HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0
RUN pip install "kev[serve] @ https://github.com/jaredpalmer/kev/archive/${KEV_REVISION}.tar.gz" "flash-linear-attention==0.5.2"
RUN KEV_RUN="${KEV_MODEL}" python -c "import os; from kev.checkpoint import Checkpoint; from huggingface_hub import snapshot_download; c = Checkpoint(os.environ['KEV_RUN']); snapshot_download(c.meta.base, revision=c.meta.base_revision, allow_patterns=['*.json','*.safetensors','*.txt','*.jinja'])" \
    && chown -R app /models/kev
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 KEV_RUN=${KEV_MODEL} \
    KEV_DTYPE=bf16 KEV_PREFIX_CACHE=0 KEV_CUDA_GRAPHS=1 TRITON_CACHE_DIR=/tmp/triton
USER app
EXPOSE 8009
CMD ["sh", "-c", "export KEV_API_KEY=\"$(cat /run/secrets/kev_api_key)\"; exec python -m kev.serve --run \"$KEV_RUN\" --host 0.0.0.0 --port 8009 --device cuda"]
