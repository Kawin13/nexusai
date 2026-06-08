# NexusAI — Technical FAQ Chatbot

A lightweight, production-ready chatbot with 537 FAQ answers across 15 topics:
AI/ML, Python, Web Dev, Cloud, Databases, DevOps, Cybersecurity, Git, Networking, and more.

**Stack**
- **Frontend** — Vanilla HTML/CSS/JS, deployed on GitHub Pages
- **Backend** — Python / Flask, deployed on Render (free tier)
- **Search** — TF-IDF + cosine similarity (scikit-learn) — no GPU, no model downloads
- **Optional AI fallback** — Gemini or OpenAI when FAQ confidence is low

---

## Live URLs

| Service | URL |
|---|---|
| Frontend (GitHub Pages) | https://kawin13.github.io/nexusai/ |
| Backend (Render) | https://nexusai-1-pm2x.onrender.com |
| Health check | https://nexusai-1-pm2x.onrender.com/health |
| Topics | https://nexusai-1-pm2x.onrender.com/topics |

---

## Project Structure

```
nexusai/
├── backend/
│   ├── app.py          ← Flask app — all routes, CORS, error handlers
│   ├── chatbot.py      ← FAQ engine (TF-IDF search, caching)
│   ├── utils.py        ← Text preprocessing, synonym expansion
│   └── data.json       ← 537 FAQ entries
├── frontend/
│   ├── index.html      ← Single-page app shell
│   ├── style.css       ← Dark/light theme, responsive layout
│   └── script.js       ← All frontend logic
├── requirements.txt    ← Python dependencies (no torch/CUDA)
├── render.yaml         ← Render deployment config
├── .env.example        ← Environment variable template
├── README.md           ← This file
└── deploy-guide.md     ← Step-by-step deployment instructions
```

---

## Run Locally

### 1. Clone the repo

```bash
git clone https://github.com/kawin13/nexusai.git
cd nexusai
```

### 2. Set up the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r ../requirements.txt
cp ../.env.example ../.env
python app.py
# → http://localhost:5000
```

### 3. Open the frontend

```bash
# Option A: open directly
open frontend/index.html

# Option B: serve with Python (avoids file:// quirks)
cd frontend
python -m http.server 8080
# → http://localhost:8080
```

The frontend auto-detects `localhost` and points to `http://localhost:5000`.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Status check — returns `{"status":"ok"}` |
| GET | `/topics` | List of all FAQ topics with counts |
| POST | `/chat` | Chat — body: `{"message": "your question"}` |
| POST | `/search` | Search FAQs — body: `{"query": "...", "top_k": 5}` |
| GET | `/faqs` | Paginated FAQ list (`?topic=&page=&per_page=`) |
| GET | `/stats` | Engine statistics |

### Example

```bash
curl -X POST https://nexusai-1-pm2x.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "what is machine learning"}'
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `5000` | Server port |
| `DEBUG` | `false` | Flask debug mode |
| `CONFIDENCE_THRESHOLD` | `40` | Min FAQ match score (0-100) |
| `CORS_ORIGINS` | GitHub Pages + localhost | Comma-separated allowed origins |
| `GEMINI_API_KEY` | — | Optional Gemini AI fallback |
| `OPENAI_API_KEY` | — | Optional OpenAI fallback |

---

## Performance

| Metric | Value |
|---|---|
| Startup time | ~2 s |
| RAM usage | ~120 MB |
| Query latency | ~2 ms (cached: 0 ms) |
| Dependencies | 7 packages |
| Model downloads | None |
# nexusai
NexusAI is an intelligent technical assistant built with Flask and Sentence Transformers, leveraging hybrid search techniques to provide precise answers from a knowledge base of 500+ FAQs covering AI, Cloud, DevOps, Databases, Cybersecurity, and Software Engineering.
