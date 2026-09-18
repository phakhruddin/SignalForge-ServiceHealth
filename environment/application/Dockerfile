FROM mirror.gcr.io/library/python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7 AS base
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY common.py /app/common.py

FROM base AS api
COPY api.py /app/api.py
CMD ["python", "-u", "/app/api.py"]

FROM base AS worker
COPY worker.py /app/worker.py
CMD ["python", "-u", "/app/worker.py"]

FROM base AS canary
COPY canary.py /app/canary.py
CMD ["python", "-u", "/app/canary.py"]
