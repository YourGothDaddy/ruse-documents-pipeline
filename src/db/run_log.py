from datetime import datetime


def start_run(conn):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO pipeline_runs (started_at, status) VALUES (%s, 'running') RETURNING id",
            (datetime.now(),)
        )
        run_id = cur.fetchone()["id"]
    conn.commit()
    return run_id


def finish_run(conn, run_id, documents_processed, documents_new):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE pipeline_runs
            SET finished_at = %s, status = 'success',
                documents_processed = %s, documents_new = %s
            WHERE id = %s
            """,
            (datetime.now(), documents_processed, documents_new, run_id)
        )
    conn.commit()


def fail_run(conn, run_id, error_message):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE pipeline_runs
            SET finished_at = %s, status = 'failed', error_message = %s
            WHERE id = %s
            """,
            (datetime.now(), str(error_message)[:2000], run_id)
        )
    conn.commit()
