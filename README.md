# Dozenko — Artisan Flower Rugs

Website bán thảm trải sàn hình hoa nghệ thuật.

## Local CRM + Admin Run

Project now includes a local CRM backend and admin panel:

- API base: `/api/*`
- Admin page: `/admin`
- Database: `brain.db`

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

### 2) Run API + website

```bash
python app.py
```

Open:

- `http://127.0.0.1:5000/`
- `http://127.0.0.1:5000/admin`

### Production note (GitHub Pages)

`https://dozenko.io.vn` is static hosting, so `/api/*` does not exist there.
The site talks to a separate CRM backend deployed on Render.

`index.html` already sets:

```html
window.DOZENKO_CRM_API_BASE = 'https://dozenko-crm.onrender.com';
```

If you deploy the backend to a different host, update this line and
re-deploy GitHub Pages. **Never leave this empty in production** — an
empty value silently breaks the waitlist form, chatbot order flow, and
checkout (this happened once; see `test_log.md`).

### Fast deploy checklist (what to click)

1. Push current code to GitHub (`main` and `master` — Render currently
   tracks `master`; keep both in sync until that's consolidated).
2. On Render: New + > Blueprint > connect this repository (or use the
   existing `dozenko-crm` service + Manual Deploy).
3. Render reads `render.yaml` and creates/updates service `dozenko-crm`.
4. Set required Environment Variables on Render (see below).
5. After deploy, verify:

```text
https://dozenko-crm.onrender.com/api/health
https://dozenko-crm.onrender.com/api/resend/status
```

6. Re-deploy GitHub Pages and test one checkout order end-to-end.

### Environment variables (set in Render → Environment)

| Variable | Required | Purpose |
|---|---|---|
| `RESEND_API_KEY` | Yes (for emails) | Resend API key. Get from resend.com dashboard. Never commit this — see `.gitignore`. |
| `FROM_EMAIL` | Yes (for emails) | Sender address on a verified domain, e.g. `hi@dozenko.io.vn`. |
| `PAYMENT_LINK` | No | Defaults to `https://dozenko.io.vn/thanh-toan`. |
| `GITHUB_TOKEN` | Yes (free-tier persistence) | Fine-grained PAT with Contents: Read & write on this repo. Lets `brain.db` survive Render's free-tier restarts by backing up to the `db-backup` branch. Without this, all data resets on every restart. |
| `GITHUB_REPO` | Yes (with above) | `dtn-yoko/dozenko-store`. |
| `GITHUB_BACKUP_BRANCH` | No | Defaults to `db-backup`. |

### Data persistence (free tier)

Render's free plan has no persistent disk, so `brain.db` lives on
ephemeral storage that resets on every restart/spin-down. This app
works around that for free by treating a GitHub branch as storage:
it restores the latest `brain.db` backup from `db-backup` on boot,
and pushes a fresh backup after every customer/order write plus every
3 minutes. If you outgrow this, the proper fix is a Render persistent
disk or a managed Postgres database (requires a paid plan).

### 3) Quick smoke test

```bash
python smoke_test.py
```

The smoke test checks API health and a simple create/update order flow.

## Deploy to GitHub Pages

1. Push toàn bộ thư mục này lên GitHub repository
2. Vào Settings > Pages > Source: Deploy from branch (main)
3. Trỏ domain `dozenko.io.vn` về GitHub Pages

## Structure

```
dozenko-store/
├── index.html      # Main website
├── style.css       # All styles
├── script.js       # Interactions
├── _config.yml     # GitHub Pages config
└── images/
    ├── rug-blue.jpg
    ├── rug-green.jpg
    ├── rug-orange.jpg
    └── rug-brown.jpg
```
