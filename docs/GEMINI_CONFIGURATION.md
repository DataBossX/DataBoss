# Gemini configuration and health

The Gemini text-analysis lane requires a locally supplied `GEMINI_API_KEY` and explicit `GEMINI_MODEL`. No replacement model, credentials, runtime dependency or paid workflow is enabled by this change. Existing configuration files are preserved.

A key without a qualified model no longer invokes the hard-coded `gemini-pro` choice. Missing/invalid models, legacy Gemini 1.x identifiers, Omni video models and Deep Research agents are refused before the existing text SDK transport. Configuration errors retain HTTP 503 instead of being disguised as a generic HTTP 500. Successful Gemini analysis records the exact requested `model_identifier` alongside the existing output fields.

The health response and dashboard distinguish `unavailable` (no key), `paused` (invalid or missing model), and `configured_unverified`. Configuration does not prove live API availability. `provider_configuration.gemini.live_api_verification` remains `NOT_RUN`; no provider health ping is introduced. A dashboard without that configuration metadata shows Unknown rather than treating key presence as Online. Other provider displays are unchanged.

These guards check explicit selection and text-workflow compatibility; they do not certify that an arbitrary model name is supported, account-enabled or free. The incumbent owner must qualify actual model behavior and cost through the existing controls before choosing a setting. Omni and Deep Research replacements use the Interactions API and cannot be blindly substituted into `generate_content`.

## Verification

`python -m unittest discover -s backend/tests -p "test_gemini_configuration.py"` exercises the actual parsed route-function bodies with synthetic SDK transport. It does not start FastAPI, import provider SDKs or prove deployed HTTP behavior.

`node --test frontend/tests/serviceStatusPresentation.test.mjs` verifies the status presentation mapping without a network call. Full frontend build/render, deployed FastAPI/SDK integration and native Windows behavior remain separate acceptance checks.

The read-only host collector in the companion DataBossX change can inspect the actual PC roots without starting services or revealing credentials. Bind its evidence to the existing Helper owner and source/configuration hashes; it cannot establish another process's effective configuration by itself.

## Adoption and recovery

Review and adopt this candidate through the existing owner and project controls. No shared application, configuration, database, queue, client source or abstract package was changed by preparation. Preserve prior code/configuration/dependency identities and authoritative sources. Verify source links, critical fields, cancellation, bounded attempts/costs and failure isolation using the owner's accepted workflow before activation.

After adoption, a missing explicit model leaves Gemini paused. Restoring code/settings is not a recovery path to an endpoint that Google has shut down. Keep that lane paused until a supported replacement passes workflow acceptance; never silently choose another provider or paid model.

Primary references: [retirement schedule](https://ai.google.dev/gemini-api/docs/deprecations), [release notes](https://ai.google.dev/gemini-api/docs/changelog), [Omni guide](https://ai.google.dev/gemini-api/docs/omni), [Deep Research guide](https://ai.google.dev/gemini-api/docs/deep-research).
