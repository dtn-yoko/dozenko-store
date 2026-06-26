# Deploy notes — Dozenko CRM (Flask)

## Stack
Python Flask app (`app.py`) serves the static site, `/admin` panel, and all
`/api/*` CRM endpoints from one process. SQLite database `brain.db`. No
Node/Express involved.

## Required environment variables (set on VPS, e.g. in a systemd unit or
`.env` loaded by your process manager — see `.env.example`)

| Variable | Required | Purpose |
|---|---|---|
| `RESEND_API_KEY` | Yes (emails) | Resend API key |
| `FROM_EMAIL` | Yes (emails) | Verified sender address |
| `GITHUB_TOKEN` | Only if no persistent disk | Backs up `brain.db` to a GitHub branch |
| `GITHUB_REPO` | With above | `dtn-yoko/dozenko-store` |
| `GITHUB_BACKUP_BRANCH` | No | Defaults to `db-backup` |
| `PAYMENT_LINK` | No | Defaults to `https://dozenko.io.vn/thanh-toan` |
| `PORT` | No | Defaults to 5000 (dev) / set via gunicorn `--bind` in prod |

On a VPS with a real persistent disk, `GITHUB_TOKEN`/backup workaround is
no longer necessary — `brain.db` just lives on disk.

## Run commands

Install deps:

```bash
pip install -r requirements.txt
```

Dev (debug, single process):

```bash
python app.py
```

Production (gunicorn, matches `Procfile`):

```bash
gunicorn app:app --bind 0.0.0.0:$PORT
```

## Port

Listens on `$PORT` (default `5000` for direct `python app.py`; gunicorn
binds explicitly via the `--bind 0.0.0.0:$PORT` flag in `Procfile`). Put
nginx in front as a reverse proxy on 80/443 → `127.0.0.1:$PORT`.
