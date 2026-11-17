# Lahore Smog Risk Index & Safe-Activity Advisory System

An end-to-end MLOps system that addresses smog in Lahore. For each air-quality monitoring station in the city, it forecasts smog risk over the next 15 hours, divided into three 5-hour windows. Each window is classified as Safe, Caution, Unhealthy or Hazardous, and the API returns a plain-language advisory rather than a raw concentration value.

> "3–7 PM: Unhealthy — limit outdoor activity. 8 PM–5 AM: Hazardous — stay indoors. This is not medical advice."

The system is an air-quality information tool, not a medical device. Its advisories are not medical advice.

## Architecture

```
OpenAQ + Open-Meteo → validation → feature store (Feast) → training + quality gate (MLflow) → serving API → monitoring + retraining
```

| Layer | Implementation |
|---|---|
| Data | Hourly PM1, PM2.5, particle count, temperature and humidity from 18 Lahore stations ([OpenAQ](https://openaq.org)), combined with city weather from [Open-Meteo](https://open-meteo.com) (CC BY 4.0) |
| Model | A scikit-learn `MultiOutputClassifier` with 3 outputs (one per window) and 4 classes each. A Logistic Regression baseline is compared against XGBoost, and a model is promoted only if it passes a quality gate |
| Orchestration | Apache Airflow for hourly ingestion and the daily retraining decision; Kubeflow Pipelines on Minikube for training and evaluation |
| Serving | Flask with gunicorn in Docker on AWS ECS Fargate, plus a BentoML service |
| Observability | Prometheus and Grafana for API metrics, Evidently for drift detection, CloudWatch for logs |
| Delivery | GitHub Actions for CI/CD, Trivy for security scanning |
| Versioning | Git, DVC (DagsHub and S3 remotes), MLflow tracking and model registry on DagsHub |

## Project status

| Component | Status |
|---|---|
| Repository, configuration, DagsHub and MLflow setup | Complete |
| Data ingestion (OpenAQ, Open-Meteo) | Complete |
| Data validation | Complete |
| Labelling and feature engineering | In development |
| Feature store, training, evaluation | In development |
| Serving, orchestration, CI/CD, monitoring | In development |

## Getting started

Requires Python 3.11. On Windows, use WSL2 or Docker for Airflow and gunicorn.

```bash
python -m venv .venv
source .venv/bin/activate          # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env               # PowerShell: Copy-Item .env.example .env
```

Set the values in `.env`. This file is excluded from version control and must never be committed.

| Variable | Purpose |
|---|---|
| `OPENAQ_API_KEY` | OpenAQ API access |
| `MLFLOW_TRACKING_URI`, `MLFLOW_TRACKING_USERNAME`, `MLFLOW_TRACKING_PASSWORD` | DagsHub MLflow tracking (the token is also used for DVC) |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` | AWS access |
| `APP_ENV` | Runtime environment: `dev` or `prod` |

## Usage

Run from the repository root with the virtual environment active.

```bash
python -m src.data.ingest_openaq --backfill     # station data from OpenAQ
python -m src.data.ingest_weather --backfill    # weather data from Open-Meteo
python -m src.data.merge_data                   # writes data/interim/merged.parquet
python -m src.data.validate                     # validates the merged dataset
python -m pytest tests/                         # runs the test suite
```

## Data versioning (DVC)

Data is versioned with DVC. Git stores only small pointer files (`data/raw.dvc`, `dvc.lock`); the data itself lives in two remotes: `origin` (DagsHub, default) and `s3` (AWS S3).

`data/raw` is tracked with `dvc add`. `dvc.yaml` has one stage, `prepare`, which turns `data/raw` into `data/processed/features.parquet`.

Set the DagsHub credentials once (stored in `.dvc/config.local`, which is never committed):

```bash
dvc remote modify --local origin auth basic
dvc remote modify --local origin user <dagshub-username>
dvc remote modify --local origin password <dagshub-token>
```

Get the data for the current commit:

```bash
git pull
dvc pull                 # downloads data/raw (and outputs) from DagsHub
dvc repro                # rebuilds data/processed/features.parquet if inputs changed
```

Reproduce an older code + data version:

```bash
git checkout <commit-or-tag>
dvc checkout             # or: dvc pull  (if the data is not in your local cache)
dvc repro
```

After changing the raw data:

```bash
dvc add data/raw
dvc repro
git add data/raw.dvc dvc.lock data/.gitignore data/processed/.gitignore
git commit -m "chore(data): update raw data version"
dvc push                 # DagsHub
dvc push -r s3           # S3 (once the s3 remote exists)
```

## Contributing

- `main` is protected and must always be deployable. Develop on `feature/<name>` branches and merge through pull requests.
- Each pull request requires one approval from another contributor. CI checks must also pass once the pipeline is in place.
- Keep commits small and focused, using conventional prefixes: `feat:`, `fix:`, `test:`, `docs:`, `chore:`.

## Contributors

Mahnoor, Fatima and Faryal.

## Data licensing and attribution

Air-quality data is provided by OpenAQ. Weather data is provided by Open-Meteo under the CC BY 4.0 licence. Punjab EPA and PAQI figures are used only for manual cross-checks of the results.
