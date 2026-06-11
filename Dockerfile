FROM python:3.14-slim

# newsbeat-digest processor image. The native SwiftUI app is built separately
# from app/Newsbeat and is not copied into this image.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    MALLOC_ARENA_MAX=2

WORKDIR /app

RUN addgroup --system digest \
    && adduser --system --ingroup digest --home /app digest

COPY pyproject.toml README.md ./
COPY newsbeat_digest ./newsbeat_digest
RUN python -m pip install .

COPY sources.yaml profile.md ./
RUN mkdir -p /data /app/feed /app/digests \
    && chown -R digest:digest /data /app/feed /app/digests

USER digest

ENTRYPOINT ["newsbeat-digest"]
CMD ["run"]
