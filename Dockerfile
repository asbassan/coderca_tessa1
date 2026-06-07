FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
COPY data ./data

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -e .

RUN mkdir -p /app/artifacts /app/runlogs

ENTRYPOINT ["coderca_tessa1"]
CMD ["init"]
