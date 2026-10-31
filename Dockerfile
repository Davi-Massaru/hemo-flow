ARG IRIS_IMAGE=iris-community:2026.3.0AI.154.0
FROM ${IRIS_IMAGE}
USER root
COPY requirements.txt /tmp/hemoflow-requirements.txt
RUN python3 -m pip install --break-system-packages --ignore-installed --no-cache-dir -r /tmp/hemoflow-requirements.txt
RUN python3 -m pip install --target /opt/hemoflow-deps fhir.resources==6.1.0 pydantic==1.10.26
RUN python3 -m pip install --index-url https://registry.intersystems.com/pypi/simple --target /usr/irissys/mgr/python intersystems-iris-automl==1.0.3
COPY --chown=irisowner:irisowner . /opt/hemoflow
RUN sh /opt/hemoflow/java/pex/build.sh && mkdir -p /durable/embeddings && chown irisowner:irisowner /durable /durable/embeddings
ENV PYTHONPATH=/opt/hemoflow/python
USER irisowner
RUN sh /opt/hemoflow/tools/build-eap154.sh
