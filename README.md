# Lahore Smog Risk Index & Safe-Activity Advisory System

MLOps course project. Predicts Lahore smog risk (Safe/Caution/Unhealthy/Hazardous) 6-24 hours ahead and outputs a plain-language safety advisory.

## Team

- **Mahnoor**
- **Fatima**
- **Faryal**

Full submodule-level breakdown with commit conventions: see `Project_Plan_Lahore_Smog_Risk_Advisory.md`.

## Project Plan
See `Project_Plan_Lahore_Smog_Risk_Advisory.md` for full module breakdown, ownership, and commit conventions.

## Setup
[TODO ]

## Environment Variables

This repo includes a file called .env.example - it lists the environment variable names you need, but **not** the real values.

If you're not familiar with this pattern, here's what to do:

1. Copy .env.example into a new file called .env:
   `powershell
   Copy-Item .env.example .env
   `
2. Open .env and replace the placeholder with the real API key (ask Mahnoor if you don't have it).
3. **Never edit .env.example with real keys/secrets** - it should only ever contain placeholders like OPENAQ_API_KEY=your_key_here. It's committed to Git on purpose, so anyone cloning the repo knows which variables to set.
4. **Never commit .env** - it holds your real secret and is already excluded in .gitignore. If git status ever shows .env as a file to be committed, stop and check your .gitignore before proceeding.

## How to Run
[TODO]

## How to Reproduce a Specific Data/Code Version
[TODO]

## API Examples
[TODO]

## Deployment
[TODO]

