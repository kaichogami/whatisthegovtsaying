# whatisthegovtsaying.com

Daily AI-generated digests of government press releases from 30+ countries. A static site that answers one question: **what is the government saying?**

Live at [whatisthegovtsaying.com](https://whatisthegovtsaying.com)

## How it works

1. **Fetch** — A Python script pulls government press releases from the [World News API](https://govtintelbot.com) (self-hosted, covers 30+ countries)
2. **Summarize** — Each release is summarized via LLM (OpenRouter API, defaults to `gemini-2.5-flash-lite`), then rolled up into country and global digests
3. **Build** — Astro generates a static site from the SQLite digest database
4. **Deploy** — The static output is pushed to Cloudflare Pages via `wrangler`

This runs daily in a Docker container on Dokploy. No servers to manage for the frontend — just static HTML on the edge.

## Data source

Press releases are sourced from the **World News API** at [govtintelbot.com](https://govtintelbot.com). It scrapes official government websites from 30+ countries multiple times daily and exposes them via a REST API. See [govtintelbot.com/llms.txt](https://govtintelbot.com/llms.txt) for full API documentation.

Countries covered: Argentina, Australia, Brazil, Canada, China, European Union, France, Germany, India, Indonesia, Ireland, Italy, Japan, Netherlands, New Zealand, Nigeria, Qatar, Russia, Singapore, South Africa, South Korea, Switzerland, Taiwan, Thailand, UAE, United Kingdom, United Nations, United States, Vietnam, WHO.

## Tech stack

- **Frontend**: [Astro](https://astro.build) (static site generator), Tailwind CSS, TypeScript
- **Data**: SQLite via [better-sqlite3](https://github.com/WiseLibs/better-sqlite3), with daily + weekly digest tables
- **Summarization**: [OpenRouter](https://openrouter.ai) (LLM gateway)
- **Hosting**: [Cloudflare Pages](https://pages.cloudflare.com) (static site), [Dokploy](https://dokploy.com) (build container)
- **OG images**: Generated at build time with [Satori](https://github.com/vercel/satori) + [Sharp](https://sharp.pixelplumbing.com)

## Project structure

```
├── scripts/
│   ├── generate_digest.py      # Fetch + summarize → SQLite
│   ├── build_and_deploy.sh     # Full pipeline: generate → build → deploy
│   ├── entrypoint.sh           # Docker entrypoint with daily loop
│   └── requirements.txt        # Python deps (requests, openai)
├── src/
│   ├── pages/                  # Astro pages (index, archive, weekly, OG)
│   ├── components/             # Astro components
│   ├── layouts/                # Base layout
│   ├── lib/                    # DB queries, constants, markdown, OG generation
│   └── styles/                 # Global CSS
├── data/                       # SQLite database (gitignored, Docker volume)
├── Dockerfile                  # Node 22 + Python 3 build container
├── docker-compose.prod.yml     # Production compose for Dokploy
└── wrangler.toml               # Cloudflare Pages config
```

## Local development

```bash
# Install dependencies
npm install
pip install -r scripts/requirements.txt

# Copy env template and fill in your keys
cp .env.example .env

# Generate digests (requires API keys)
python scripts/generate_digest.py --backfill 3

# Dev server
npm run dev

# Build + preview
npm run build && npm run preview
```

## Environment variables

| Variable | Description |
|---|---|
| `WORLD_NEWS_API_URL` | World News API base URL |
| `WORLD_NEWS_API_KEY` | World News API key |
| `OPENROUTER_API_KEY` | OpenRouter API key for LLM summarization |
| `OPENROUTER_MODEL` | LLM model (default: `google/gemini-2.5-flash-lite`) |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API token (Pages deploy permission) |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account ID |
| `BACKFILL_DAYS` | Days to backfill (default: 30, skips existing) |

See `.env.example` for the template.

## Docker deployment

The container runs `generate_digest.py` → `npm run build` → `wrangler pages deploy` on startup, then repeats daily at 07:00 UTC.

```bash
# Build and run
docker compose -f docker-compose.prod.yml up -d

# Check logs
docker compose -f docker-compose.prod.yml logs -f builder
```

## License

MIT
