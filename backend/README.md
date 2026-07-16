# Fraud Detection Backend

## Folder structure
```
backend/
├── app/
│   ├── main.py                  <- FastAPI entrypoint (run this)
│   ├── database.py              <- DB connection + auto schema creation
│   ├── models/                  <- SQLAlchemy table definitions
│   │   ├── user.py
│   │   ├── admin.py
│   │   ├── transaction.py
│   │   └── fraud_log.py
│   ├── schemas/                 <- Pydantic request/response validation
│   │   ├── user.py
│   │   ├── admin.py
│   │   └── transaction.py
│   ├── routers/                 <- API endpoints, grouped by feature
│   │   ├── auth.py              <- admin login
│   │   ├── users.py             <- admin creates users / public dropdown
│   │   ├── transactions.py      <- core fraud-check flow
│   │   └── deps.py              <- shared JWT auth dependency
│   └── services/
│       ├── auth_service.py      <- password hashing + JWT
│       └── ml_service.py        <- loads model, builds features, predicts
├── create_admin.py              <- run once to create your first admin login
├── .env
└── requirements.txt
```

## Setup steps

1. Create the Postgres database (matching your DATABASE_URL in .env):
   ```sql
   CREATE DATABASE fraud_detection;
   ```

2. Update `.env` with your real Postgres password.

3. Install dependencies (from inside `backend/`):
   ```
   pip install -r requirements.txt
   ```

4. Make sure your ml/models/ folder (from the ML phase) is placed correctly
   relative to this backend folder, matching MODEL_PATH in .env:
   ```
   project-root/
   ├── backend/     <- you run uvicorn from here
   └── ml/
       └── models/
           ├── xgboost_model.joblib
           ├── label_encoder.joblib
           └── scaler.joblib
   ```

5. Run the backend (this auto-creates the schema on first run):
   ```
   uvicorn app.main:app --reload
   ```
   Watch the terminal - you'll see either "Creating missing tables..." (first run)
   or "Schema already exists. Connected without changes." (every run after).

6. Create your first admin login (only needed once):
   ```
   python create_admin.py
   ```

7. Open http://127.0.0.1:8000/docs - FastAPI's interactive Swagger UI.
   From here you can:
   - POST /api/auth/login (as your admin) - copy the returned access_token
   - Click "Authorize" (top right) and paste the token to unlock admin routes
   - POST /api/admin/users - add users with a starting balance
   - GET /api/users - see the public list (for the frontend's transaction dropdown)
   - POST /api/transactions - submit a transaction and see the fraud decision live
   - GET /api/admin/transactions and /api/admin/fraud-logs - the admin portal data

## How the fraud decision works
- If the model's fraud probability >= THRESHOLD (currently 0.7, from .env) ->
  transaction is marked "fraud", balances are NOT updated, and an entry is
  written to fraud_logs for the admin portal to display.
- Otherwise -> marked "legit", balances update normally.
