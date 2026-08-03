# TaskEnvelope and WriterACK Contract

FOR REVIEW - HOLD NO EXTERNAL RELEASE

A live transition requires an activated mutation TaskEnvelope binding actor, operation, scope, non-empty input hashes, non-empty control hashes, non-empty output allowlist, and expiry. The receipts folder must be allowed.

WriterACK binds ACK ID, exact canonical envelope digest, actor, operation, scope, and expiry. ACK consumption is atomic with retirement validation, claim uniqueness, and lease/fence issuance. It is single-use and frozen to one claim. Terminal authority must match the envelope digest and ACK ID frozen at START.

Chat text, filename text, and an older envelope never imply authority. Offline synthetic tests may omit live authority only because they have no external mutation capability.
