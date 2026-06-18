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

To make checkout write to CRM on production:

1. Deploy `app.py` to a public backend host (Render/Railway/VPS).
2. Edit `index.html` and set:

```html
window.DOZENKO_CRM_API_BASE = 'https://your-public-crm-domain';
```

3. Re-deploy website to GitHub Pages.

### Fast deploy checklist (what to click)

1. Push current code to GitHub.
2. On Render: New + > Blueprint > connect this repository.
3. Render reads `render.yaml` and creates service `dozenko-crm`.
4. After deploy, verify:

```text
https://dozenko-crm.onrender.com/api/health
```

5. Keep `window.DOZENKO_CRM_API_BASE = ''` in `index.html` to use default for `dozenko.io.vn`,
   or set it explicitly to your backend URL.
6. Re-deploy GitHub Pages and test one checkout order.

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
