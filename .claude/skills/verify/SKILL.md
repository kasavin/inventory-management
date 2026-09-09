---
name: verify
description: Launch the inventory app (FastAPI backend + Vue frontend) and drive it end-to-end in Playwright to verify a change.
---

# Verify: Factory Inventory Management

## Launch

Backend on port 8001. It has no auto-reload, so restart it after every server change:

```bash
lsof -ti:8001 | xargs kill 2>/dev/null
cd server && uv run python main.py
```

If `uv sync` cannot reach its package index, any Python >= 3.11 environment with `fastapi`, `uvicorn` and `pydantic` installed can run `python main.py` directly.

Frontend on port 3000 (Vite, hot reload):

```bash
cd client && npm install && npm run dev
```

Gotcha: on machines that block unsigned native binaries, esbuild gets killed (SIGKILL, exit 137) during `npm install` or when Vite starts. A local-only workaround is `"overrides": { "esbuild": "npm:esbuild-wasm@0.21.5" }` in `client/package.json`, then a clean reinstall. Do not commit it.

Wait for both before driving:

```bash
curl -s -o /dev/null --retry 15 --retry-delay 1 --retry-connrefused http://localhost:8001/docs
curl -s -o /dev/null --retry 30 --retry-delay 1 --retry-connrefused http://localhost:3000/
```

## Drive (Playwright MCP, http://localhost:3000)

- Every page logs `GET /api/tasks 404` in the console. That is pre-existing (no tasks backend), not a regression.
- **Restocking** (`/restocking`): focus the "Budget" slider, press Home (zero budget: empty state, Place Order disabled) and End (maximum: all 9 forecast items, about $67,844). The default budget is half the maximum. Place Order opens the "Confirm Restock Order" dialog; Confirm submits and shows a success message linking to Orders.
- **Orders** (`/orders`): the "Submitted Orders" card at the top lists restock orders with lead time and expected delivery. It ignores the global filters.
- **Japanese**: switch language from the header language button; amounts convert to yen at 150 per USD.
- **API probes**: `curl -X POST http://localhost:8001/api/restock-orders -H 'Content-Type: application/json' -d '{"lines":[{"item_sku":"WDG-001","quantity":450}]}'` returns 201. Bad bodies return 422, unknown or duplicate SKUs 400.

## State

Restock orders live in memory only. Restart the backend to clear test orders before handing the app back.
