FROM node:22-alpine AS frontend-build

WORKDIR /workspace/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /workspace

COPY backend/requirements.txt /workspace/backend/requirements.txt
RUN grep -v '^pytest' /workspace/backend/requirements.txt > /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --timeout 300 --retries 10 -r /tmp/requirements.txt

COPY backend/ /workspace/backend/
COPY SOUL.md /workspace/backend/SOUL.md
COPY data/ /workspace/data/
COPY --from=frontend-build /workspace/frontend/dist/ /workspace/backend/app/static/

WORKDIR /workspace/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]