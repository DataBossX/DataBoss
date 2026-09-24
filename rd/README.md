# DataBossX AI R&D safe slice

Isolated, reversible, read-only scaffolding. This directory is not a second
controller, agent runtime, or production parser.

## What it does

- Probes an existing loopback Ollama instance at `127.0.0.1:11434`.
- Records the installed n8n version and already-observable agent settings.
- Holds a document-parser benchmark specification for the current DataBossX
  pipeline, Docling 2.130.0, and optional MinerU 4.0.7.

## What it does not do

- Merge, deploy, promote, or write client/package/Drive/report bytes.
- Download models or Python packages.
- Call cloud Ollama, n8n Cloud, or other paid APIs.
- Edit n8n configuration or workflows.
- Enable MinerU (`LICENSE_ACCEPTED=false`, candidate disabled).
- Grant any AI write authority.

## Commands

```bash
python -m databossx_rd observe --output-root runtime/rd
python -m databossx_rd bench --mode spec_only --output-root runtime/rd
python -m databossx_rd bench --mode current_only --output-root runtime/rd
```

Outputs are written only under the isolated root (`runtime/rd` by default).
One writer may hold a given target at a time.

## Rollback

See `rd/ROLLBACK.md`. Removing this scaffolding restores the previous
production path because no production module imports it.
