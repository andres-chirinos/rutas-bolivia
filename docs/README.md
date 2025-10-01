Dashboard and API

- Start the API server:

```bash
uvicorn src.adapters.api.app:app --reload --host 127.0.0.1 --port 8000
```

- Build or preview the Quarto dashboard (requires Quarto installed):

```bash
quarto preview docs/museos_dashboard.qmd
```

Notes:
- The API adapts existing plugins; if plugin function names/signatures differ, edit `src/adapters/api/app.py` to call the correct functions.
- This is a minimal adapter: production deployments should secure endpoints and validate inputs.
