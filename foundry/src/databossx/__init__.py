"""DataBossX Foundry: the thin, verifiable bootstrap layer.

The Foundry is a general automation platform core. It knows nothing about any
business domain; domain logic (Wyoming Abstracts, Oklahoma Title, OCR, CRM)
installs later as plugins under ``/plugins`` with a ``plugin.json`` manifest.
Core code never imports plugins.
"""

__version__ = "0.1.0"
