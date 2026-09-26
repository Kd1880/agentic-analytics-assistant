# AskDB frontend

React UI for the Agentic Analytics Assistant. Three database "worlds", each with its own
palette, display font, background texture and selection animation.

## Stack

Vite · React 19 · TypeScript · Tailwind v4 · shadcn/ui conventions · lucide-react ·
framer-motion · Recharts

## Run

```bash
npm install
npm run dev          # http://localhost:5173
```

## Point it at the backend

Config lives in `.env.local` (gitignored — copy from `.env.example`):

```ini
VITE_API_URL=http://localhost:8000
VITE_USE_MOCK=false     # true = offline sample answers, no backend needed
```

Start the Python backend from the repo root first:

```bash
uvicorn backend.app:app --port 8000
```

**Vite only reads env vars at startup** — restart `npm run dev` after editing `.env.local`.

## Security

The browser holds **no API key** and never calls an LLM provider. It only calls this
project's own FastAPI backend at `VITE_API_URL`; the backend holds the key server-side.

## Structure

```
src/lib/databases.ts   per-database design tokens (light + dark), fonts, textures, chips
src/lib/api.ts         the ONLY backend integration point: getDatabases(), ask()
src/lib/mockData.ts    offline sample answers (real gold values from the study)
src/components/askdb/
  Landing.tsx          database picker, one themed card per world
  ThemeIntro.tsx       selection animation: film countdown / parcel scan / ball-into-net
  Workspace.tsx        question input, example chips, agent stepper, session history
  AgentStepper.tsx     the live pipeline + SQL typed as it arrives
  ResultPanel.tsx      Answer / Chart / SQL tabs, badges, insight
  EmptyState.tsx       idle illustration per world
src/App.tsx            shell: theme tokens, light/dark toggle, landing -> intro -> workspace
```

## Theming

There is no Tailwind theme config for the worlds. `themeStyle()` writes CSS custom
properties (`--primary`, `--surface`, `--display`, …) onto the app wrapper, and every
component reads those. Selecting a database re-skins the whole app in one step, and
light/dark is a second token set per world (remembered in `localStorage`, defaulting to the
system preference).
