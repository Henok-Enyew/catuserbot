# Docker and Render deployment

## 1. Setup your .env file

In the project root, create a `.env` file with your credentials (use the project root `.env.example` as a template):

- Copy `.env.example` to `.env`: `cp .env.example .env`
- Edit `.env` and set at least:
  - `ENV=True`
  - `ALIVE_NAME`, `APP_ID`, `API_HASH`, `STRING_SESSION`, `OWNER_ID`
  - `TG_BOT_TOKEN`, `PRIVATE_GROUP_BOT_API_ID`, `PM_LOGGER_GROUP_ID`
  - `DATABASE_URL` (PostgreSQL, e.g. Supabase Pooler with port **6543**)
  - **`GEMINI_API_KEY`** — required for `.gem` / `.gpt` commands ([get key](https://aistudio.google.com/apikey))

Do not commit `.env` (it is in `.gitignore`).

## 2. Build and run with Docker (local test)

From the project root in your terminal:

```bash
docker build -t catuserbot .
docker run --env-file .env --rm catuserbot
```

Or with Docker Compose (if you use it): ensure your compose file passes the env file, then:

```bash
docker-compose up
```

**Check the logs:** When you see **"Bot Started Successfully"** (or the startup success message), open Telegram **Saved Messages** and try:

```text
.gem hello world
```

If `GEMINI_API_KEY` is set, the bot should reply with a Gemini-generated response.

Optional tests:
- **Universal downloader:** `.dlv <youtube link>` (video) or `.dla <link>` (audio). Requires ffmpeg in the image (included in the Dockerfile).
- **AddAI:** Reply to a user with `.addai` to enable AI replies for them. Requires `KUKI_API_KEY` in `.env` (get from kukiapi.xyz). Without it, the bot will tell the user to set the key.

## 3. Deploy to Render

1. **Commit and push** your code (including `.env.example`; never push `.env`).

2. **Render Dashboard**
   - Open your service → **Environment**.
   - Add environment variables (same as in `.env`). In particular:
     - **`GEMINI_API_KEY`** — your Gemini API key (secret).
     - **`DATABASE_URL`** — keep the **Pooler** URL (port **6543**).
   - Save.

3. **Deploy:** **Manual Deploy** → **Deploy latest commit**.

After deploy, test again in Telegram with `.gem hello world`.
