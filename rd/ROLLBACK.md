# Rollback

This slice is additive. Production modules do not import it. A clean rollback
is to remove or disable the new probes and benchmark scaffolding.

## Disable without deleting

Stop invoking:

```text
python -m databossx_rd
```

Leave the files in place. No production path reads them.

## Remove the scaffolding

Delete these paths and nothing else:

```text
src/databossx_rd/
rd/
tests/test_rd_safe_slice.py
tests/test_rd_isolation.py
```

Revert the `rd/BENCH/out/` ignore rule in `.gitignore` if it is no longer
wanted. Do not delete `runtime/` itself; only the isolated `runtime/rd/`
outputs created by this slice.

Do not revert unrelated production files. This slice must not have changed
client, Drive, report, package, website, backend, frontend, or grocery
pipeline bytes.

## Do not

- Merge, deploy, or promote this slice as a controller.
- Uninstall Ollama, n8n, or system packages as part of rollback.
- Accept MinerU or install Docling as part of rollback.
