# Ruse Documents Pipeline

A data pipeline that scrapes public municipal documents from the Ruse Municipal Council website, cleans and structures the data, loads it into a PostgreSQL warehouse, and serves it through a searchable dashboard.

![Dashboard screenshot](screenshots/dashboard.png)

## What This Project Is

Ruse municipality publishes regulations, council decisions, and meeting minutes on its website, but the site has no unified search, inconsistent file formats, and documents scattered across multiple content types. This project builds a small, scheduled pipeline that pulls this data automatically, cleans it, and makes it searchable in one place.

This is a Data Engineering portfolio project. The focus is the pipeline itself, extraction, transformation, orchestration, and storage, not the dashboard, which is intentionally simple.

## Architecture

```
Ruse Council Site (obs.ruse-bg.eu)
        |
   Extract: Python scraper (requests + BeautifulSoup)
        |
        v
Raw storage: local JSON files, one per scrape run
        |
   Orchestration: Airflow DAG, scheduled weekly
        |
   Transform: clean titles, parse dates, detect status, deduplicate
        |
        v
   Load: PostgreSQL, star schema
        |
   API: FastAPI backend reading from Postgres
        |
        v
   Frontend: static dashboard, live search and filters
```

## Why No Kafka or Spark

New documents appear a handful of times per week, not continuously. This is a batch problem, and a scheduled Airflow DAG handles it correctly. Kafka is built for continuous, real time event streams, using it here would be forcing a tool where it does not belong.

The dataset is small, hundreds of documents, not millions of rows. Plain Python and Postgres handle this comfortably. Spark exists to distribute processing across many machines when data does not fit on one, that is not the situation here.

Knowing when a tool does not apply is as important as knowing how to use it.

## Data Source Handling

The site is a WordPress installation, but different document categories use different underlying structures. Regulations and meeting minutes use a custom document post type with consistent HTML classes. Council decisions use a separate WordPress category with no matching HTML structure, instead exposing clean JSON-LD structured data embedded in the page, which the scraper parses directly.

Real inconsistencies handled by the pipeline:

- Two different date formats across categories, one plain text day and month and year format, one ISO format
- File attachments in doc, docx, and pdf formats, and some documents with no attachment at all
- Regulation titles that embed their repeal status as free text rather than structured data, for example a title containing "Отменена с Решение № 1017"
- Duplicate entries caused by the site rendering the same document in both a main list and a sidebar widget

## Database Schema

Star schema. One fact table, two dimension tables.

**documents** (fact table)
id, title, category_id, status_id, publish_date, file_url, file_type, file_size_kb, source_url, scraped_at

**categories** (dimension table)
Наредби, Решения, Протоколи, Предложения, Приватизация

**statuses** (dimension table)
active, repealed, unknown

## Tech Stack

- Python, requests and BeautifulSoup for extraction
- PostgreSQL for storage
- Apache Airflow for scheduling and orchestration
- FastAPI for the backend API
- Plain HTML, CSS, and JavaScript for the dashboard, no framework

## Running This Locally

Requirements: Python 3.12, PostgreSQL, WSL or a Linux environment.

Clone the repository and set up the environment.

```bash
git clone https://github.com/YourGothDaddy/ruse-documents-pipeline.git
cd ruse-documents-pipeline
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file with your database credentials.

```
DB_HOST=localhost
DB_NAME=ruse_documents
DB_USER=ruse_pipeline
DB_PASSWORD=your_password
```

Create the database and run the schema.

```bash
psql -U ruse_pipeline -d ruse_documents -h localhost -f sql/schema.sql
```

Run the pipeline manually, or through Airflow.

Manual run, one step at a time:

```bash
python3 src/extract/scraper.py
python3 src/transform/clean.py
python3 src/load/load.py
```

Through Airflow, scheduled weekly:

```bash
export AIRFLOW_HOME=~/projects/ruse-documents/airflow_home
airflow standalone
```

Then trigger `ruse_documents_pipeline` from the Airflow UI at localhost:8080.

Run the API:

```bash
cd src/api
uvicorn main:app --reload --port 8000
```

Open `frontend/index.html` in a browser while the API is running.

## Planned: V2

The current version scrapes a limited slice of each document category to prove the pipeline end to end. Planned next steps:

- Full historical scraping across all categories, not a limited sample
- Full text extraction from document files, including OCR for scanned documents
- Public deployment, frontend on Vercel, database on Neon, API on Render
- Full text search across document contents, not just titles

## Project Structure

```
src/extract/     scraper
src/transform/   cleaning and validation logic
src/load/        database loading logic
src/api/         FastAPI backend
dags/            Airflow DAG
sql/             schema definition
frontend/        static dashboard
data/            local raw and processed data, gitignored
```
