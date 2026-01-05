# Mental Health Mentor

This repository contains a FastAPI backend and a Streamlit front-end for a Mental Health Guidance Mentor that returns three short responses: `technical`, `realistic`, and `emotional`.

Quick setup

1. Create a GitHub repo and push your code (example):

```bash
git init
git add .
git commit -m "Initial commit"
# Add remote (replace with your repo)
git remote add origin git@github.com:<you>/<repo>.git
git branch -M main
git push -u origin main
```

2. Add secrets to Streamlit (if using Streamlit Cloud):
   - `GROQ_API_KEY` — your Groq API key
   - `GROQ_MODEL` — optional, e.g. `llama-3.3-70b-versatile`

3. Deploy to Streamlit Cloud:
   - Go to https://share.streamlit.io → New app → Connect your GitHub repo and select `streamlit_app.py`.
   - Streamlit will install dependencies from `requirements.txt`.

Notes

- If you prefer hosting FastAPI elsewhere and using Streamlit as a front-end, change `streamlit_app.py` to POST to your FastAPI URL (store it in `st.secrets` as `API_URL`).
- Do not commit your real keys to the repo — use Streamlit Secrets or GitHub Secrets.

