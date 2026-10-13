# Gemini configuration and health

The Gemini text-analysis lane requires a locally supplied `GEMINI_API_KEY` and explicit `GEMINI_MODEL`. No replacement model, credentials, runtime dependency or paid workflow is enabled by this change. Existing configuration files are preserved.

A key without a qualified model no longer invokes the hard-coded `gemini-pro` choice. Missing/invalid models, legacy Gemini 1.x identifiers, Omni video models and Deep Research agents are refused before the existing text SDK transport. Configuration errors retain HTTP 503 instead of being disguised as a generic HTTP 500. Successful Gemini analysis records the exact requested `model_identifier` alongside the existing output fields.

The health response and dashboard distinguish `unavailable` (no key), `paused` (invalid or missing model), and `configured_unverified`. Configuration does not prove live API availability. `provider_configuration.gemini.live_api_verification` remains `NOT_RUN`; no provider health ping is introduced. A dashboard without that configuration metadata shows Unknown rather than treating key presence as Online. Other provider displays are unchanged.

These guards check explicit selection and text-workflow compatibility; they do not certify that an arbitrary model name is supported, account-enabled or free. The incumbent owner must qualify actual model behavior and cost through the existing controls before choosing a setting. Omni and Deep Research replacements use the Interactions API and cannot be blindly substituted into `generate_content`.

## Verification

`python -m unittest discover -s backend/tests -p "test_gemini_configuration.py"` exercises the actual parsed route-function bodies with synthetic SDK transport. It does not start FastAPI, import provider SDKs or prove deployed HTTP behavior.

`python -m pytest backend/tests/test_gemini_http.py` qualifies the real FastAPI HTTP/SQLite upload path with imported provider SDKs, synthetic credentials/documents and mocked Gemini construction/results. It checks paused/legacy/retiring configurations, source hashes, duplicate suppression, persisted requested-model identity and health metadata. It uses temporary storage, disables dotenv loading and forbids Python socket connections; native SDK egress is not an OS-level firewall. Provider transport is mocked and no paid request is made. Missing test dependencies produce an explicit skip rather than claiming HTTP qualification.

An isolated Python 3.12 qualification used `fastapi==0.110.1`, `python-dotenv==1.0.1`, `openai==1.54.0`, `anthropic==0.40.0`, `google-generativeai==0.8.0`, `Pillow==10.4.0`, `loguru==0.7.2`, `aiosqlite==0.20.0`, `python-multipart==0.0.9`, `httpx==0.27.2` and `pytest==8.0.0`. These versions satisfy the backend manifest; they are test-environment versions, not a deployment pin change. The manifest now documents `sqlite3` as a Python standard-library module instead of trying to install an unavailable pip distribution. Full corrected-manifest resolution was also checked with pip's dry-run; resolution alone does not prove every optional dependency's runtime behavior.

`node --test frontend/tests/serviceStatusPresentation.test.mjs` verifies the status mapping. `npm test -- --watchAll=false --runInBand --detectOpenHandles` also exercises the actual App rendering in jsdom with synthetic HTTP health metadata and mocked fetch. Run `npm run build` after a frozen Yarn install. The incumbent CRA preset's missing direct Babel proposal-plugin dependency is now explicitly pinned to `7.21.11`; its previous accidental placeholder produced a warning timer during the render tests. The lock retains every existing selector's version, resolution, integrity and dependency payload and adds only the required plugin plus two selectors for existing compatible helpers. This is a build qualification fix within the existing toolchain, not a framework migration.

Native Windows, current PC/proxy settings, deployed application behavior and live model/account acceptance remain separate checks; offline test model strings are fixtures, not recommended configuration. The existing CRA/legacy SDK and database lifecycle still carry deprecation notices; this candidate does not certify their future support or a complete toolchain modernization.

The read-only host collector in the companion DataBossX change can inspect the actual PC roots without starting services or revealing credentials. Bind its evidence to the existing Helper owner and source/configuration hashes; it cannot establish another process's effective configuration by itself.

## Adoption and recovery

Review and adopt this candidate through the existing owner and project controls. No shared application, configuration, database, queue, client source or abstract package was changed by preparation. Preserve prior code/configuration/dependency identities and authoritative sources. Verify source links, critical fields, cancellation, bounded attempts/costs and failure isolation using the owner's accepted workflow before activation.

After adoption, a missing explicit model leaves Gemini paused. Restoring code/settings is not a recovery path to an endpoint that Google has shut down. Keep that lane paused until a supported replacement passes workflow acceptance; never silently choose another provider or paid model.

Primary references: [retirement schedule](https://ai.google.dev/gemini-api/docs/deprecations), [release notes](https://ai.google.dev/gemini-api/docs/changelog), [Omni guide](https://ai.google.dev/gemini-api/docs/omni), [Deep Research guide](https://ai.google.dev/gemini-api/docs/deep-research).
