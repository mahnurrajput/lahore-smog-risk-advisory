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

## Reproducibility demo

Every Git commit pins one exact data version: `data/raw.dvc` stores the MD5 hash of `data/raw`, and DVC uses that hash to fetch the matching files from the remote. Checking out an old commit and running `dvc checkout` / `dvc pull` gives back the code **and** the data exactly as they were.

The demo uses a Git tag that names a known code + data pair:

| Tag | Commit | `data/raw` hash (from `data/raw.dvc`) | Contents |
|---|---|---|---|
| `repro-demo-v1` | `b4ee567` | `d67547b3b2cb879f7ae6204eaf3d3178.dir` | 1,225 files, 12.76 MB: OpenAQ + Open-Meteo backfill from 2025-01-01 |

Before you start, set the DagsHub credentials (see [Data versioning](#data-versioning-dvc)) and commit or stash your local changes. `dvc checkout` replaces the current contents of `data/raw`.

**1. Recover the tagged version:**

```bash
git fetch --tags
git checkout repro-demo-v1          # code as it was at the tag (detached HEAD)
dvc pull data/raw.dvc               # data as it was at the tag
```

**2. Check that the data matches the pinned version:**

```bash
dvc status data/raw.dvc             # expected: "Data and pipelines are up to date."
cat data/raw.dvc                    # md5 must be d67547b3b2cb879f7ae6204eaf3d3178.dir
```

PowerShell: `Get-Content data/raw.dvc`. Count the files with `find data/raw -type f | wc -l` (PowerShell: `(Get-ChildItem data/raw -Recurse -File).Count`). The result should be 1225.

**3. See that the tagged data differs from the current version** (once `data/raw` has been updated after the tag):

```bash
git diff repro-demo-v1 main -- data/raw.dvc    # shows the old and new data hashes
```

**4. Return to the latest version:**

```bash
git checkout main
dvc checkout data/raw.dvc           # or dvc pull if the newer data is not in your cache
```

When the `prepare` stage exists, `dvc repro` after step 1 rebuilds `data/processed/features.parquet` from the recovered data. MLflow runs record the Git commit and the DVC hash, so any logged model can be traced back to the same pair.

Save a screenshot of steps 1 and 2 to `docs/evidence/2.3_reproducibility_demo.png`.

## Resolving .dvc merge conflicts

**Why conflicts happen:** `data/raw.dvc` holds a single hash for the whole `data/raw` folder. If two branches both run `dvc add data/raw`, each commits a different hash on the same line. Git then reports a conflict when the branches are merged, even if each branch only added different files:

```
outs:
<<<<<<< HEAD
- md5: 0ab852370bf0346dccd5fbff86074a3a.dir
  size: 12757686
=======
- md5: 05e4e53c3113f6bc019f87269165dbc1.dir
  size: 12757685
>>>>>>> demo/teammate-b
```

Do **not** fix this by hand-editing the hash. Neither hash describes the combined data.

### Option 1: DVC merge driver (normal case)

The repository's `.gitattributes` sends `*.dvc` files to DVC's merge driver. The driver combines the file lists of both versions into one new hash. Each team member runs this once per clone, because Git config is not committed:

```bash
git config merge.dvc.name "DVC merge driver"
git config merge.dvc.driver "dvc git-hook merge-driver --ancestor %O --our %A --their %B"
```

After that, merge as usual and then sync the workspace:

```bash
git merge <branch>        # data/raw.dvc is merged automatically
dvc pull                  # or dvc checkout, if both versions are in your local cache
dvc push                  # upload the merged data version
```

The driver needs both versions in the local DVC cache. If it reports missing files, run `dvc pull` on each branch first (or `dvc fetch --all-branches`) and merge again.

### Option 2: Manual resolution (when the driver cannot merge)

The driver stops if both branches **changed or deleted the same file**. In that case:

1. Keep one side's `.dvc` file:
   ```bash
   git checkout --ours data/raw.dvc      # or --theirs
   dvc checkout data/raw.dvc
   ```
2. Copy the needed files from the other branch into `data/raw`. Alternatively, re-run ingestion so the folder holds the correct combined data.
3. Re-track the folder and finish the merge:
   ```bash
   dvc add data/raw
   git add data/raw.dvc
   git commit
   dvc push
   ```

The same steps apply to `dvc.lock`. After resolving it, run `dvc repro` so the lock file matches the merged inputs.

### Demo

[`docs/evidence/2.4_dvc_merge_conflict_demo.log`](docs/evidence/2.4_dvc_merge_conflict_demo.log) shows the full simulation:

- Two local branches each add a different file to `data/raw`.
- A plain Git merge conflicts on `data/raw.dvc`.
- With the merge driver enabled, the same merge succeeds. The result has 1,227 files, containing both teammates' files.

The demo branches were local only and were deleted afterwards. Nothing from them was pushed.

## Contributing

- `main` is protected and must always be deployable. Develop on `feature/<name>` branches and merge through pull requests.
- Each pull request requires one approval from another contributor. CI checks must also pass once the pipeline is in place.
- Keep commits small and focused, using conventional prefixes: `feat:`, `fix:`, `test:`, `docs:`, `chore:`.

## Contributors

Mahnoor, Fatima and Faryal.

## Data licensing and attribution

Air-quality data is provided by OpenAQ. Weather data is provided by Open-Meteo under the CC BY 4.0 licence. Punjab EPA and PAQI figures are used only for manual cross-checks of the results.
