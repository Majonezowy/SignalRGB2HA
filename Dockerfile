FROM python:3.12-slim

WORKDIR /app
COPY emulator.py .
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables (optional defaults)
ENV WLED_NAME=HomeAssistantBridge
ENV ENTITY_NAMES=
ENV ENTITY_COUNT=
ENV HA_IP=
ENV HA_TOKEN=

EXPOSE 80
EXPOSE 21324

CMD ["python", "emulator.py"]