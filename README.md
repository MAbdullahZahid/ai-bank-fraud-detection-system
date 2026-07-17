# AI-Based Bank Fraud Detection System

An AI-powered banking application that detects fraudulent transactions using a Machine Learning model combined with a Rule-Based Fraud Detection Engine. The system provides secure banking operations, real-time fraud detection, an admin dashboard, dispute management, email notifications, and transaction monitoring.

---

# Features

## Customer Features

- User Registration & Login
- JWT Authentication
- Deposit Money
- Cash Withdrawal (ATM Simulation)
- Money Transfer
- Merchant Payments
- Bill Payments
- Transaction History
- Fraud Probability Display
- Fraud Alerts
- Email Notifications
- Raise Transaction Disputes
- Recipient Verification Before Transfer

---

## Admin Features

- Admin Login
- Dashboard
- Manage Users
- View All Transactions
- View Fraud Logs
- Resolve Customer Disputes
- Manage Merchants
- Manage Billers
- Fraud Analytics

---

## AI Fraud Detection

The system uses an XGBoost Machine Learning model trained on the PaySim Fraud Detection Dataset.

### Model Performance

| Metric | Score |
|---------|-------|
| Accuracy | **99.99%** |
| Precision | **94.77%** |
| Recall | **99.88%** |
| F1 Score | **97.26%** |
| ROC-AUC | **99.98%** |

---

# Rule-Based Fraud Detection

The ML model is combined with eight additional security rules:

- Velocity Rule
- New Counterparty Rule
- Balance Drain Rule
- Odd Hour Rule
- Abnormal Transaction Amount Rule
- Repeated Counterparty Rule
- Round Amount Rule
- New Device / New IP Rule

A transaction is blocked if either:

- Machine Learning predicts fraud
- Any security rule is triggered

---

# Tech Stack

## Frontend

- React.js
- CSS
- Axios
- React Router

## Backend

- FastAPI
- SQLAlchemy
- PostgreSQL
- JWT Authentication
- Pydantic

## Machine Learning

- Python
- XGBoost
- Scikit-Learn
- Pandas
- NumPy
- Joblib

---

# Project Structure

```
AI-Bank-Fraud-Detection-System/

│
├── backend/
│   ├── app/
│   │   ├── models/
│   │   ├── routers/
│   │   ├── services/
│   │   ├── schemas/
│   │   ├── utils/
│   │   └── main.py
│   │
│   ├── ml/
│   │   ├── train_model.py
│   │   ├── predict.py
│   │   └── fraud_rules.py
│   │
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   ├── public/
│   └── package.json
│
├── models/
│   ├── fraud_model.joblib
│   └── label_encoder.joblib
│
├── dataset/
│
└── README.md
```

---

# Installation

## Clone Repository

```bash
git clone https://github.com/yourusername/AI-Bank-Fraud-Detection-System.git

cd AI-Bank-Fraud-Detection-System
```

---

# Backend Setup

Create virtual environment

```bash
python -m venv venv
```

Activate

Windows

```bash
venv\Scripts\activate
```

Linux / Mac

```bash
source venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

Configure PostgreSQL database.

Run backend

```bash
uvicorn app.main:app --reload
```

---

# Frontend Setup

```bash
cd frontend

npm install

npm run dev
```

---

# Machine Learning Model

The repository already includes the trained model files.

```
fraud_model.joblib
label_encoder.joblib
```

No retraining is required.

If you want to retrain the model:

```bash
python train_model.py
```

---

# API Endpoints

## Authentication

- Register
- Login

## User

- Profile
- Deposit
- Withdraw
- Transfer
- Merchant Payment
- Bill Payment

## Transactions

- Create Transaction
- Transaction History
- Fraud Detection
- Fraud Logs

## Disputes

- Create Dispute
- View Disputes
- Resolve Disputes

## Admin

- Dashboard
- Users
- Transactions
- Fraud Logs
- Merchants
- Billers

---

# Fraud Detection Flow

```
Customer Request
        │
        ▼
Feature Extraction
        │
        ▼
XGBoost Prediction
        │
        ▼
Rule Engine
        │
        ▼
Final Decision
        │
 ┌──────┴────────┐
 │               │
Fraud        Legitimate
 │               │
 ▼               ▼
Block         Complete
Transaction   Transaction
```

---

# Dataset

Dataset used:

PaySim Mobile Money Fraud Detection Dataset

https://www.kaggle.com/datasets/ealaxi/paysim1

---

# Future Improvements

- OTP Verification
- Face Recognition
- Fingerprint Authentication
- SMS Alerts
- Live Transaction Streaming
- Explainable AI (SHAP)
- Real-Time Fraud Dashboard
- Mobile Application

---



---

# Author

**Abdullah Zahid**

Software Engineer

Backend | AI | Machine Learning

GitHub: https://github.com/MAbdullahZahid


---

# License

This project is developed for educational and research purposes.
