"""
FastAPI entrypoint.
On startup: connects to Postgres, creates schema only if tables are missing.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import auth, users, transactions

app = FastAPI(title="AI-Based Bank Fraud Detection System")

# Allow the React frontend (running on a different port) to call this API.
# Tighten allow_origins to your actual frontend URL before deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(transactions.router)


@app.get("/")
def root():
    return {"message": "Fraud Detection API is running"}
