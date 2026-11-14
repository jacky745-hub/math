FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
ENV CM_DATA_DIR=/data PORT=5001
VOLUME /data
CMD gunicorn -w 1 --threads 8 --timeout 600 -b 0.0.0.0:$PORT src.main:app
