FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9

RUN mkdir -p /root/.aws
COPY . /app

RUN mkdir -p /app/media && pip install --no-cache-dir -r /app/requirements.pip
