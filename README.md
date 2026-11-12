# Lahore Smog Risk Index & Safe-Activity Advisory System

MLOps course project. For each Lahore monitoring station, predicts smog risk for the **next 15 hours**, split into **three 5-hour windows**. Each window gets one of four categories (Safe / Caution / Unhealthy / Hazardous), and the API returns a plain-language advisory. Not medical advice.

## Team

- **Mahnoor**
- **Fatima**
- **Faryal**

## Project Plan
The single source of truth is the team project plan (v2, Nov 12, 2026): `Project_Plan_Lahore_Smog_Risk_Advisory_updated.md`. It has the module breakdown, owners, commit conventions and technical rules.

## Setup
[TODO]

## Environment Variables

This repo includes a file called `.env.example`. It lists the environment variable names you need, but **not** the real values.

| Name | Used for |
|---|---|
| `OPENAQ_API_KEY` | OpenAQ API |
| `MLFLOW_TRACKING_URI` | DagsHub MLflow URL |
| `MLFLOW_TRACKING_USERNAME` | DagsHub username |
| `MLFLOW_TRACKING_PASSWORD` | DagsHub token (also used for DVC) |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` | AWS access |
| `APP_ENV` | `dev` or `prod` (Docker Compose sets `dev`; ECS sets `prod`) |

What to do:

1. Copy `.env.example` into a new file called `.env`:
   ```bash
   cp .env.example .env
   ```
   (PowerShell: `Copy-Item .env.example .env`)
2. Open `.env` and fill in the real values (ask the team if you don't have them).
3. **Never put real keys/secrets in `.env.example`.** It only lists the names and is committed to Git on purpose, so anyone cloning the repo knows which variables to set.
4. **Never commit `.env`.** It holds your real secrets and is already excluded in `.gitignore`. If `git status` ever shows `.env` as a file to be committed, stop and check your `.gitignore` before proceeding.

## How to Run
[TODO]

## How to Reproduce a Specific Data/Code Version
[TODO]

## API Examples
[TODO]

## Deployment
[TODO]

## Teardown
[TODO]
