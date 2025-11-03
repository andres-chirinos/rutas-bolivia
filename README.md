Datamesh Client - minimal scaffold

This repository contains a minimal hexagonal-architecture scaffold for a
decentralized knowledge protocol client. It includes:

- `src/core` - domain models, ports, and services (plugin manager).
- `src/adapters` - base adapters for formatting and compute.
- `plugins` - external plugin location.
- `dm_cli_tool.py` - tiny demo CLI entrypoint.

How to run the demo:

python3 dm_cli_tool.py

Run tests (if pytest is available):

pytest -q
