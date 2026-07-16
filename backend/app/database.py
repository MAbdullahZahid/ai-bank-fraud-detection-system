"""
Database connection setup.
Connects to Postgres via DATABASE_URL from .env.
On startup, checks which tables already exist - creates only the missing
ones, and does nothing if the schema is already fully set up.
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency - yields a DB session per request, closes it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Called once on app startup.
    Checks existing tables in Postgres - if any expected table is missing,
    creates it. If everything already exists, just connects (no-op).
    """
    # Import models here so they register with Base.metadata before create_all runs
    from app.models import user, admin, transaction, fraud_log  # noqa: F401

    expected_tables = ["users", "admins", "transactions", "fraud_logs"]
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    missing = [t for t in expected_tables if t not in existing_tables]

    if missing:
        print(f"[DB INIT] Missing tables detected: {missing}. Creating schema...")
        Base.metadata.create_all(bind=engine)
        print("[DB INIT] Schema created successfully.")
    else:
        print("[DB INIT] Schema already exists. Connected without changes.")

    _seed_demo_accounts()


def _seed_demo_accounts():
    """Create repeatable demo counterparties so each scenario can be tested right away."""
    from app.models.user import User
    from app.services.auth_service import hash_password

    demo_accounts = [
        # ATM / cash withdrawal (used by the Cash Out / ATM scenario)
        {"full_name": "ATM / Cash Point", "email": "atm@gmail.com",
         "phone_number": "03009990001", "balance": 999999999},

        # Deposit agent (used by the Cash In scenario)
        {"full_name": "Deposit Agent", "email": "depositagent@gmail.com",
         "phone_number": "03009990003", "balance": 999999999},

        # Merchants (Payment scenario - customer picks one of these by name)
        {"full_name": "Careem", "email": "careem@gmail.com ",
         "phone_number": "03009991001", "balance": 500000},
        {"full_name": "Foodpanda", "email": "foodpanda@gmail.com",
         "phone_number": "03009991002", "balance": 500000},
        {"full_name": "Daraz", "email": "daraz@gmail.com",
         "phone_number": "03009991003", "balance": 500000},

        # Billers (Auto Debit scenario - customer picks one of these by name)
        {"full_name": "K-Electric", "email": "kelectric@gmail.com",
         "phone_number": "03009992001", "balance": 500000},
        {"full_name": "PTCL Internet", "email": "ptcl@gmail.com",
         "phone_number": "03009992002", "balance": 500000},
        {"full_name": "Sui Gas", "email": "suigas@gmail.com",
         "phone_number": "03009992003", "balance": 500000},
    ]

    db = SessionLocal()
    try:
        changed = False
        for account in demo_accounts:
            exists = (
                db.query(User)
                .filter((User.email == account["email"]) | (User.phone_number == account["phone_number"]))
                .first()
            )
            if exists:
                continue

            db.add(
                User(
                    full_name=account["full_name"],
                    email=account["email"],
                    phone_number=account["phone_number"],
                    password=hash_password("Demo123!"),
                    balance=account["balance"],
                )
            )
            changed = True

        if changed:
            db.commit()
            print("[DB INIT] Demo accounts ensured for scenario testing.")
    finally:
        db.close()