# GLiNER2 extraction service (Fastino, Apache-2.0): entities, relations, classification and
# structured fields from one encoder family, on the GPU. Checkpoints are baked at BUILD time.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/models/hf
# alias -> Hugging Face repo. Requests (and the routing rules in config/engines.yaml) use
# the aliases, so swapping a checkpoint is a build arg, not a code change.
ARG EXTRACTOR_MODELS='{"decide":"fastino/GLiNER2.5-Decide","decide-multi":"fastino/GLiNER2.5-multi-Decide","extract-multi":"fastino/gliner2.5-multi-v1"}'
ENV EXTRACTOR_MODELS=${EXTRACTOR_MODELS}
WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY download_model*.py ./
# Network is needed ONLY here. Air-gapped sites build once outside and `docker save | load`.
RUN python download_models.py && rm download_models.py
COPY app ./app
RUN useradd -r -u 10001 app && chown -R 10001 /models
USER 10001
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
