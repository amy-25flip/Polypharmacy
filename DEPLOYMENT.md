# Hosting PolyGuard

Two ways to run it. Use the cloud option when the app has to be reachable while your PC is off.

## 1. Your PC with a tunnel (what you use today)

```powershell
.\start_polyguard.ps1            # backend + built frontend on 127.0.0.1:8765, plus the ngrok tunnel
.\scripts\selfhost_watchdog.ps1  # optional: keeps the PC awake and restarts either piece if it dies
```

Run `.\start_polyguard.ps1 -Rebuild` after any frontend change. The app is only reachable while the PC is
on, awake and online.

## 2. Always-on cloud hosting (Render)

`render.yaml` already describes both services (API and static frontend). Everything the API needs is
tracked in git (`processed/` models and data, about 15 MB), so nothing has to be uploaded separately.

1. Push this repository to GitHub (already done).
2. In Render choose **New → Blueprint**, pick the repository, and apply `render.yaml`.
3. Open the API service → **Environment** and add `GEMINI_API_KEY` (only needed for prescription photo
   scanning). Leave it out to disable scanning.
4. If Render gives the services different addresses from `polyguard-api` and `polyguard-frontend`, update
   `VITE_API_URL` on the frontend service and `POLYGUARD_ALLOWED_ORIGINS` on the API service to match.
5. Wait for both builds, then open the frontend address.

Notes:
- The free plan sleeps after about 15 minutes without visitors, so the first request afterwards takes about a
  minute. Open the site a few minutes before a demo, or move the API to a paid plan.
- The API holds the models in memory (about 500 MB with PyTorch). If the free plan runs out of memory, use
  the Starter plan.
- Check a deployment with `python scripts/verify_disease_plan.py --base-url https://<your-api-address>`.
