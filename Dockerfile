FROM apache/airflow:2.10.5-python3.12
USER root
RUN mkdir -p /opt/project && chown airflow:0 /opt/project
USER airflow
COPY --chown=airflow:0 requirements.txt /opt/project/requirements.txt
RUN pip install --no-cache-dir "apache-airflow==2.10.5" -r /opt/project/requirements.txt && pip check
COPY --chown=airflow:0 src /opt/project/src
COPY --chown=airflow:0 dags /opt/project/dags
COPY --chown=airflow:0 scripts/start-airflow.sh /opt/project/scripts/start-airflow.sh
COPY --chown=airflow:0 data /opt/project/data
COPY --chown=airflow:0 scripts/bootstrap_data.py /opt/project/scripts/bootstrap_data.py
RUN python /opt/project/scripts/bootstrap_data.py
RUN mkdir -p /opt/project/work /opt/project/model_bank /opt/project/datamart /opt/project/evidence \
    && chmod +x /opt/project/scripts/start-airflow.sh
ENV PROJECT_ROOT=/opt/project PYTHONPATH=/opt/project \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLBACKEND=Agg
WORKDIR /opt/project
