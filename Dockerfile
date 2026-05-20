# syntax=docker/dockerfile:1.7

# ---------- Stage 1: builder (build a wheel for the package) ----------
FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip build \
 && python -m build --wheel --outdir /wheels

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim

RUN useradd --create-home --uid 10001 ovh \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl \
 && rm -rf /wheels

USER ovh
WORKDIR /home/ovh

# Sensible defaults that K8s can override
ENV OVH_ENDPOINT=ovh-eu \
    RATE_LIMIT_MS=1000 \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "ovh_spam_filter"]
CMD ["sync"]
