# Stage 1: fetch ONLY the tokenizer of the served model (a few MB), pinned to the same
# repo + revision as the vLLM image, so decider and vLLM tokenize identically.
FROM python:3.12-slim AS tokenizer
ARG LLM_MODEL_REPO=cyankiwi/Qwen3-4B-Instruct-2507-AWQ-4bit
ARG LLM_MODEL_REVISION=main
RUN pip install --no-cache-dir "huggingface_hub>=0.30" \
 && python -c "from huggingface_hub import hf_hub_download as d; \
d('${LLM_MODEL_REPO}', 'tokenizer.json', revision='${LLM_MODEL_REVISION}', local_dir='/opt/tokenizer')"

# Stage 2: runtime. No hub client, no network needed.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 TOKENIZER_PATH=/opt/tokenizer/tokenizer.json
WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY --from=tokenizer /opt/tokenizer/tokenizer.json /opt/tokenizer/tokenizer.json
COPY app ./app
RUN useradd -r -u 10001 app
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=300s --retries=3 \
  CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/readyz',timeout=2).status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
