# Fraud Detection Backend

## IMPORTANT - if you already ran an earlier version of this backend
The `users` table now has a new `phone_number` column, and auth has changed
(admin vs. user are now separate logins with separate tokens). Your existing
database was created before this column existed, and `create_all()` does
NOT alter existing tables - it only creates missing ones.

**You need to drop and let it recreate fresh.** Easiest way, in pgAdmin:
1. Right-click your `fraud_detection` database's tables (`users`, `admins`,
   `transactions`, `fraud_logs`) → Delete/Drop each one (or drop and
   recreate the whole database)
2. Run the backend again - it will detect the tables are missing and
   recreate the full schema, including `phone_number`
3. Run `create_admin.py` again to make a fresh admin login

## What changed in this version
- Users now have a `phone_number` (used like a mobile wallet account number)
- Users can log in themselves (`POST /api/auth/user-login` with phone+password)
  and send money to another user by typing in *their* phone number - no
  directory of other users' phone numbers is ever exposed
- Admin can now **edit** and **delete** users, not just create/list
- New `GET /api/admin/stats` endpoint for dashboard summary numbers
- Admin transaction/fraud-log views are enriched with names + phone numbers

## Folder structure
```
backend/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── models/            (users now include phone_number)
│   ├── schemas/            (validation: phone format, password length, etc.)
│   ├── routers/
│   │   ├── auth.py         admin login + user login (two separate JWT flows)
│   │   ├── users.py        admin CRUD (create/list/edit/delete) + /api/me
│   │   ├── transactions.py user transfers by phone + admin views + stats
│   │   └── deps.py         role-aware JWT dependencies (admin vs. user)
│   └── services/
│       ├── auth_service.py
│       └── ml_service.py
├── create_admin.py
├── .env
└── requirements.txt
```

## Setup steps
1. Create/confirm the Postgres database exists (`fraud_detection`)
2. Update `.env` with your real Postgres password
3. `pip install -r requirements.txt`
4. Confirm `ml/models/` has the 3 `.joblib` files, matching `MODEL_PATH` in `.env`
5. Run: `uvicorn app.main:app --reload`
6. Run once: `python create_admin.py`
7. Test in Swagger: `http://127.0.0.1:8000/docs`
   - `POST /api/auth/login` (admin) or `POST /api/auth/user-login` (a user
     created by the admin) - each returns a different token
   - Admin routes need the admin token; `/api/transactions` and `/api/me`
     need a user token

## Key endpoints
| Method | Path | Who | What |
|---|---|---|---|
| POST | /api/auth/login | Public | Admin login (form data) |
| POST | /api/auth/user-login | Public | User login (JSON: phone_number, password) |
| POST | /api/admin/users | Admin | Create a user |
| GET | /api/admin/users | Admin | List all users |
| PUT | /api/admin/users/{id} | Admin | Edit a user |
| DELETE | /api/admin/users/{id} | Admin | Delete a user |
| GET | /api/me | User | Own profile + balance |
| POST | /api/transactions | User | Send money by destination phone number |
| GET | /api/transactions/me | User | Own transaction history |
| GET | /api/admin/transactions | Admin | All transactions (enriched) |
| GET | /api/admin/fraud-logs | Admin | All fraud flags (enriched) |
| GET | /api/admin/stats | Admin | Summary numbers for the dashboard |

## Email notifications on user creation
When an admin creates a user, they now receive a welcome email with their
phone number (account number), password, and starting balance.

**Setup (Gmail example):**
1. Enable 2-Step Verification on the Gmail account you'll send from
2. Generate an App Password: https://myaccount.google.com/apppasswords
3. In `.env`, set:
   ```
   SMTP_USER=your_email@gmail.com
   SMTP_PASSWORD=the_16_char_app_password   <- NOT your normal Gmail password
   ```
4. Restart the backend

If SMTP isn't configured, user creation still works - the email is just
skipped, and the admin dashboard will tell you to share the details manually.
