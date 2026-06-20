# Who Has Time?

When2meet-style availability scheduling — no accounts, just shareable links.

Participants paint their free time on a grid; the heatmap shows when everyone overlaps.

## Features

- Availability grid with click/drag selection (touch-friendly on mobile)
- Two capability URLs per poll: admin (manage) and participant (submit availability)
- SQLite backend, Docker-ready for Caddy reverse proxy
- Mobile-first UI with Pico CSS, scales to desktop

## Local development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
mkdir -p data
export WHT_ALLOW_DEV_SECRET=1
export APP_BASE_URL=http://127.0.0.1:5000
export BEHIND_PROXY=0
uv run flask --app wsgi run --debug
```

Or with Docker:

```bash
docker compose -f docker-compose.local.yml up --build
```

Open http://localhost:8080

## Production deployment (Caddy)

This app is designed to run behind the [caddy_reverse](https://github.com/) stack on the external Docker network `caddy_net`.

### 1. Deploy the app stack

On your server:

```bash
sudo deploy-app who-has-time   # or copy docker-compose.yml to /opt/stacks/who-has-time/
cd /opt/stacks/who-has-time
cp .env.example .env           # set SECRET_KEY and APP_BASE_URL
docker compose up -d --build
```

Ensure `.env` contains:

```env
SECRET_KEY=<long-random-string>
APP_BASE_URL=https://who-has-time.<your-apps-domain>
```

### 2. Add Caddy site block

Add to `stacks/caddy/Caddyfile.example` in your caddy_reverse repo:

```caddyfile
who-has-time.${APPS_DOMAIN} {
    reverse_proxy who-has-time:8080
}
```

**No basic auth** — participants must reach share links without a gate password. Security relies on unguessable poll URLs (~256-bit tokens).

Then redeploy Caddy:

```bash
sudo update-stacks
cd /opt/stacks/caddy && docker compose restart
```

### 3. DNS

Ensure `who-has-time` is covered by your wildcard `*.${APPS_DOMAIN}` record.

## URL model

| Link | Path | Purpose |
|------|------|---------|
| Admin | `/poll/admin/{admin_token}` | Manage poll, copy share link, view results |
| Participant | `/poll/{participant_token}` | Submit availability, view heatmap |

Keep both links private — they are the only access control.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | (required in prod) | Flask secret for sessions/CSRF |
| `APP_BASE_URL` | request root | Public base URL for share links |
| `DATABASE_URL` | `./data/who_has_time.db` | SQLite connection string |
| `MAX_POLL_DAYS` | `14` | Maximum date range for a poll |
| `BEHIND_PROXY` | `1` | Enable ProxyFix for Caddy |
| `WHT_ALLOW_DEV_SECRET` | unset | Set to `1` for local dev with a placeholder `SECRET_KEY` |

Production requires a strong `SECRET_KEY`. The app refuses to start with a known dev default unless `WHT_ALLOW_DEV_SECRET=1`.

## License

MIT
