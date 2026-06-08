# NexusAI — Deployment Guide

Complete step-by-step instructions for deploying NexusAI to Render (backend) and
GitHub Pages (frontend).

---

## Part 1 — Deploy Backend to Render

### Step 1: Push your code to GitHub

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/kawin13/nexusai.git
git push -u origin main
```

### Step 2: Create a Render Web Service

1. Go to https://render.com and sign in
2. Click **New → Web Service**
3. Connect your GitHub account and select the `nexusai` repository
4. Fill in:
   - **Name**: `nexusai-backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn backend.app:app --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT`
   - **Instance Type**: Free

> Alternatively, the included `render.yaml` will auto-populate these settings if you use **New → Blueprint**.

### Step 3: Set environment variables in Render

In your service dashboard → **Environment** tab, add:

| Key | Value |
|---|---|
| `CONFIDENCE_THRESHOLD` | `40` |
| `CORS_ORIGINS` | `https://kawin13.github.io,http://localhost:5000` |
| `GEMINI_API_KEY` | *(your key, optional)* |
| `OPENAI_API_KEY` | *(your key, optional)* |

> Never put real API keys in `render.yaml` or commit them to git.

### Step 4: Verify the deployment

Once deployed, test these URLs in your browser:

```
https://nexusai-1-pm2x.onrender.com/health
https://nexusai-1-pm2x.onrender.com/topics
```

You should see JSON responses. If you get a 502, wait 30 seconds — Render's free tier
spins down after 15 minutes of inactivity and takes ~20 s to cold-start.

---

## Part 2 — Deploy Frontend to GitHub Pages

### Step 1: Verify script.js uses the correct Render URL

In `frontend/script.js`, line 13 should be:

```js
const PROD_API_URL = 'https://nexusai-1-pm2x.onrender.com';
```

### Step 2: Enable GitHub Pages

1. Go to your GitHub repo → **Settings → Pages**
2. Under **Source**, select:
   - Branch: `main`
   - Folder: `/frontend` (or `/root` if your HTML is at the root)
3. Click **Save**
4. GitHub will publish to: `https://kawin13.github.io/nexusai/`

> It can take 1–2 minutes for the first deploy to go live.

### Step 3: Verify

Open `https://kawin13.github.io/nexusai/` in your browser.
The status indicator in the top right should turn green (Online) within a few seconds.

---

## Part 3 — Fix CORS Issues

CORS errors happen when the browser blocks a request because the backend didn't include
the right `Access-Control-Allow-Origin` header.

### Symptoms

You'll see in the browser console:
```
Access to fetch at 'https://nexusai-1-pm2x.onrender.com/chat' from origin
'https://kawin13.github.io' has been blocked by CORS policy
```

### Fix A: Make sure CORS_ORIGINS includes your frontend URL

In Render's environment variables:
```
CORS_ORIGINS=https://kawin13.github.io,http://localhost:5000
```

Redeploy the backend after changing environment variables.

### Fix B: Verify the backend is returning CORS headers

```bash
curl -I -X OPTIONS https://nexusai-1-pm2x.onrender.com/chat \
  -H "Origin: https://kawin13.github.io" \
  -H "Access-Control-Request-Method: POST"
```

You should see `Access-Control-Allow-Origin: https://kawin13.github.io` in the response.

### Fix C: Hard-reset if you added a new origin

If you added a new origin to `CORS_ORIGINS` but still see errors:
1. In Render dashboard, click **Manual Deploy → Deploy latest commit**
2. Wait for the deploy to complete (watch the logs)
3. Hard-refresh your browser with Ctrl+Shift+R (clears cached preflight)

---

## Part 4 — Troubleshooting

### Backend shows "Service Unavailable" on Render

Render free tier sleeps after 15 minutes of inactivity. The first request after sleep
takes ~20 seconds. This is normal. Solutions:
- Use UptimeRobot (free) to ping `/health` every 10 minutes
- Upgrade to Render's paid tier ($7/month) for no sleep

### Chat says "Could not connect to server"

1. Open browser DevTools → Network tab
2. Find the failing `/chat` request
3. Check the error:
   - `net::ERR_CONNECTION_REFUSED` → backend not running locally
   - `CORS error` → fix CORS_ORIGINS (see Part 3)
   - `502 Bad Gateway` → Render is cold-starting, wait 20 s
   - `Timeout` → same as above

### Topics not loading in sidebar

The sidebar makes a GET request to `/topics` on page load. If it fails silently:
- Check DevTools → Network → look for the `/topics` request
- Confirm the backend `/health` endpoint works first

### Frontend shows wrong API URL

Open DevTools → Console and run:
```js
console.log(API_BASE);
```
It should print either `http://localhost:5000` (local) or
`https://nexusai-1-pm2x.onrender.com` (production).

If it's wrong, check `PROD_API_URL` in `script.js` line 13.

---

## Quick Reference

```bash
# Run backend locally
cd nexusai
pip install -r requirements.txt
python backend/app.py

# Test backend
curl http://localhost:5000/health
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"what is python"}'

# Open frontend locally
open frontend/index.html
# or
cd frontend && python -m http.server 8080
```
