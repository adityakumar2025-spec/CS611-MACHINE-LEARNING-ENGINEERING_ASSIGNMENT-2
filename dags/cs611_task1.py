"""No data work at DAG parse time; only small metadata is logged, no big XComs."""
from datetime import timedelta
import pendulum
from airflow import DAG
from airflow.models.param import Param
from airflow.operators.python import PythonOperator
from src import pipeline


def execute_stage(stage_name, **context):
    conf=context['dag_run'].conf or {}
    cohort=conf.get('cohort') or context['params'].get('cohort')
    # Airflow CLI backfill runs have explicit historical logical dates.
    if not cohort and str(context['run_id']).startswith('backfill__'):
        cohort=context['logical_date'].strftime('%Y-%m-01')
    result=getattr(pipeline,stage_name)(run_id=context['run_id'],cohort=cohort)
    print(f'{stage_name}: {result}')


with DAG(
    dag_id='cs611_task1',
    description='Temporal model bank, monthly loan scoring and mature-outcome monitoring',
    start_date=pendulum.datetime(2024,5,1,tz='UTC'),
    schedule='0 0 1 * *',
    catchup=False,
    is_paused_upon_creation=True,
    max_active_runs=1,
    max_active_tasks=1,
    default_args={'owner':'cs611','retries':1,'retry_delay':timedelta(seconds=15)},
    params={'cohort':Param(None,type=['null','string'],description='Optional month-start e.g. 2024-09-01; null replays all cohorts')},
    tags=['CS611','Task1','historical-replay'],
) as dag:
    previous=None
    for stage in pipeline.STAGES:
        task=PythonOperator(task_id=stage.__name__,python_callable=execute_stage,
            op_kwargs={'stage_name':stage.__name__},do_xcom_push=False,
            execution_timeout=timedelta(minutes=15))
        if previous:
            previous >> task
        previous=task
