FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir Flask==3.1.2 fhir.resources==6.1.0 pydantic==1.10.26
COPY python/hemoflow /app/hemoflow
COPY simulators/center.py /app/center.py
COPY simulators/inventory-availability.json /app/inventory-availability.json
RUN useradd --create-home center && mkdir /data && chown center /data
USER center
CMD ["python","/app/center.py"]
