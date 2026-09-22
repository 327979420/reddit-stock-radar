FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir ".[postgres]"
RUN mkdir -p /app/data
CMD ["radar", "run"]
