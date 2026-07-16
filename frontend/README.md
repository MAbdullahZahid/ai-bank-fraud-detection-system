# Ledger — Fraud Detection Frontend

A React (Vite) frontend with two experiences:
- **Home** — anyone can pick a sender/receiver, amount, and type, and submit
  a live transaction. The result renders as a stamp: Approved or Flagged,
  with the model's confidence score.
- **Admin portal** (`/admin/login`) — sign in, add users with a starting
  balance, and review every transaction and every fraud-flagged case.

## What to install

```
npm install
```
This pulls in React, React Router, and Axios (already listed in package.json).

## Configure the API URL

`.env` already points to your local backend:
```
VITE_API_URL=http://127.0.0.1:8000
```
Change this if your backend runs elsewhere.

## Run it

Make sure the backend (FastAPI) is already running first, then:
```
npm run dev
```
Open the printed URL (usually http://localhost:5173).

## Pages

| Route | What it does |
|---|---|
| `/` | Public transaction form — no login needed |
| `/admin/login` | Admin sign-in (uses the admin you created with `create_admin.py`) |
| `/admin/dashboard` | Add users, view all transactions, view fraud logs |

## First-time flow to test everything

1. Go to `/admin/login`, sign in with your admin credentials
2. In the Admin portal, add 2-3 users with starting balances
3. Go to `/` (home page), pick a sender/receiver, try a normal amount (e.g. 5,000) — should stamp "Approved"
4. Try a very large TRANSFER amount (e.g. 5,000,000) — should stamp "Flagged"
5. Go back to the admin portal → Transactions and Fraud logs tabs to see both logged
