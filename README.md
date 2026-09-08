# Aarzu — Personal AI Companion

RAG-based personal AI companion with long-term memory. FastAPI + Supabase (pgvector) + Gemini (free tier). Frontend is an installable PWA.

## What's inside

```
aarzu/
├── backend/          FastAPI app (Gemini + Supabase RAG)
├── database/          schema.sql (run once in Supabase)
├── frontend/           installable web app (PWA)
└── render.yaml         one-click backend deploy config
```

## Step 1 — Supabase (database)

1. Go to https://supabase.com → New project (free tier).
2. Open the SQL Editor → paste the contents of `database/schema.sql` → Run.
3. The last line returns a `profile id` (a UUID). **Copy it** — this is your `DEFAULT_USER_ID`.
4. Go to Project Settings → API → copy `Project URL` and `service_role` key (NOT anon key).

## Step 2 — Gemini API key (free)

1. Go to https://aistudio.google.com/apikey
2. Sign in with Google → Create API key. No card required.

## Step 3 — Run backend locally first (recommended)

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` with the Supabase URL/key, Gemini key, and the `DEFAULT_USER_ID` from Step 1.

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs → try the `/api/chat` endpoint with a message. If you get a reply, memory + RAG + Gemini are all wired correctly.

## Step 4 — Deploy backend to Render (free)

1. Push this whole project to a GitHub repo.
2. Go to https://render.com → New → Blueprint → connect your repo. Render will read `render.yaml` automatically.
3. When prompted, fill in the env vars marked `sync: false` (Supabase URL/key, Gemini key, DEFAULT_USER_ID). Set `FRONTEND_URL` after Step 5.
4. Deploy. You'll get a URL like `https://aarzu-api.onrender.com`.
5. Visit `https://aarzu-api.onrender.com/health` — should return `{"status": "ok"}`.

**Note:** Render's free tier sleeps after 15 min of no traffic and takes 30–60s to wake up on the next request. Normal for a personal project — not a bug.

## Step 5 — Deploy frontend to Vercel (free)

1. Open `frontend/app.js` and replace `API_BASE` with your real Render URL from Step 4.
2. Go to https://vercel.com → New Project → import the same GitHub repo → set **Root Directory** to `frontend`.
3. Deploy (no build command needed, it's static). You'll get a URL like `https://aarzu.vercel.app`.
4. Go back to Render → set the `FRONTEND_URL` env var to this Vercel URL → redeploy the backend (locks CORS to just your frontend).

## Step 6 — Install on your phone

1. Open your Vercel URL in Chrome (Android) or Safari (iOS) on your phone.
2. Tap the browser menu → **Add to Home Screen**.
3. You'll get an "Aarzu" icon on your home screen that opens full-screen, like a real app.

## Step 7 — Talk to her, teach her about you

Send a few messages like "I'm a software engineer working on Django and FastAPI projects" or "My goal this year is to freelance alongside my job." Aarzu automatically decides what's worth remembering (via `memory_extractor.py`) and will recall it in later conversations.

Check what she's remembered anytime: `GET /api/memories` on your backend URL.

## What's next (not included yet)

- Voice input/output (Speech-to-Text / Text-to-Speech)
- A proper memory-management screen in the UI (view/edit/delete — the API already supports it, just needs UI)
- Auth (right now it's single-user with a fixed `DEFAULT_USER_ID`, fine for personal use, not for multiple users)

Ask if you want any of these built next.
