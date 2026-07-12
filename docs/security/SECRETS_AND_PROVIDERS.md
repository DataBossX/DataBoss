# Secrets and Providers

Do not commit passwords, session tokens, client data, API keys, or runtime databases. Supply bootstrap/login credentials through the documented environment variables rather than command-line history. Keep `.runtime/`, `.env`, output databases, and private project configuration outside publication.

The sample Section 32 configuration uses `${DATABOSS_SECTION32_SOURCE_ROOT}` and disables external model uploads/providers. Enabling a non-local provider requires both explicit provider enablement and `external_model_upload_enabled`; that is a policy gate, not proof that consent, privilege, retention, residency, or vendor terms are acceptable.

Rotate any exposed credential immediately. Provider output is always an untrusted candidate and must be validated against the current local evidence ledger. The repository contains no production secret-management service.
