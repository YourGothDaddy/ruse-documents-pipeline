import sys
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

PROJECT_ROOT = "/home/alexander/projects/ruse-documents"
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from extract.scraper import main as extract_main
from transform.clean import main as transform_main
from load.load import main as load_main


def run_extract(**context):
    output_path = extract_main()
    context["ti"].xcom_push(key="raw_path", value=output_path)


def run_transform(**context):
    raw_path = context["ti"].xcom_pull(key="raw_path", task_ids="extract")
    output_path = transform_main(input_path=raw_path)
    context["ti"].xcom_push(key="processed_path", value=output_path)


def run_load(**context):
    processed_path = context["ti"].xcom_pull(key="processed_path", task_ids="transform")
    load_main(input_path=processed_path)


def notify_failure(context):
    task_id = context["task_instance"].task_id
    print(f"ALERT: Task {task_id} failed after all retries.")


default_args = {
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "on_failure_callback": notify_failure,
}

with DAG(
    dag_id="ruse_documents_pipeline",
    start_date=datetime(2026, 1, 1),
    schedule="@weekly",
    catchup=False,
    default_args=default_args,
) as dag:

    extract_task = PythonOperator(
        task_id="extract",
        python_callable=run_extract,
    )

    transform_task = PythonOperator(
        task_id="transform",
        python_callable=run_transform,
    )

    load_task = PythonOperator(
        task_id="load",
        python_callable=run_load,
    )

    extract_task >> transform_task >> load_task