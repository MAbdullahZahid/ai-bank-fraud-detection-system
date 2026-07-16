# AI Bank Fraud Detection — Frontend

## What's new in this version
- Rebranded to "AI Bank Fraud Detection"
- Real customer login (phone number + password) - customers no longer pick
  from a public list, they sign in and see only their own account
- Transfers now target a **destination phone number** (like a mobile
  wallet account number) - no directory of other users' numbers is exposed
- Beautiful landing page with a hero + feature cards
- Fully redesigned admin dashboard: stat cards, a legit-vs-fraud chart,
  and full user management (add / edit / delete), all with validation

## Install
```
npm install
```

## Configure
`.env`:
```
VITE_API_URL=http://127.0.0.1:8000
```

## Run
Backend must already be running, then:
```
npm run dev
```

## Pages
| Route | Who | What |
|---|---|---|
| `/` | Public | Landing page |
| `/login` | Public | Customer login (phone + password) |
| `/transfer` | Customer | Send money by phone number, view own history |
| `/admin/login` | Public | Admin login (username + password) |
| `/admin/dashboard` | Admin | Stats, chart, users (add/edit/delete), transactions, fraud logs |

## Test flow
1. `/admin/login` → sign in as admin
2. Admin portal → Users tab → add 2-3 users (now with phone numbers)
3. Open a private/incognito window (or log out of admin) → `/login` →
   sign in as one of those users (their phone + password)
4. `/transfer` → enter another user's phone number, an amount, submit
5. Back in the admin portal → see the transaction and (if flagged) the
   fraud log, plus the updated stat cards and chart
6. Try editing a user's balance or phone number from the admin table,
   and try deleting a user with no transactions (should succeed) vs. one
   with transactions (should show a clear error)
