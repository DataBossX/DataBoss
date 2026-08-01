# LICENCE AND DATA-SOURCE REGISTER

- Register ID: `DBX-LICENCE-REGISTER-2026-08-01`
- Status: **BASELINE ENTRIES ONLY.** No external data source has been contacted,
  fetched, cached, or ingested by the tournament. Nothing below is a claim that
  a connector exists.

---

## Rule

A source is usable only when its terms are **verified and recorded here**. A
source whose terms are unverified is `UNUSABLE` — not "probably fine", not
"public record so it must be free". Public-record origin does not by itself
grant redistribution rights over a compiled work product; `SECURITY.md` already
makes this point about client metadata.

Using an unlicensed scrape as a *core* strategy is a hard disqualifier
(`FROZEN_BRIEF.md` §6).

## Register

| ID | Source | Type | Status | Permitted use | Storage | Redistribution | Verified by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `L-1` | Tournament synthetic seed package (`tournament/seed/`) | Fabricated | **USABLE** | Any tournament use | Unlimited | Unlimited | Director — authored it |
| `L-2` | `DataBossX/DataBoss` repository content at `582d951` | Own work | **USABLE** | Design and prototype reference | Unlimited | Public repo already | Director |
| `L-3` | Oklahoma Corporation Commission (OCC) records | Official state regulatory | **UNVERIFIED — UNUSABLE** | — | — | — | *nobody yet* |
| `L-4` | Federal records (BLM / BIA, where applicable) | Official federal | **UNVERIFIED — UNUSABLE** | — | — | — | *nobody yet* |
| `L-5` | County clerk recorded instruments and images | Official county | **UNVERIFIED — UNUSABLE** | — | — | — | *nobody yet* |
| `L-6` | Enverus | Commercial | **UNVERIFIED — UNUSABLE** | — | — | — | *nobody yet* |
| `L-7` | Rextag | Commercial | **UNVERIFIED — UNUSABLE** | — | — | — | *nobody yet* |
| `L-8` | Seed item `CF-4` — synthetic licence-restricted dataset | Fabricated test fixture | **USABLE AS A TEST ONLY** | Exercising `RT-25` | Cache-only per fixture terms | Forbidden per fixture terms | Director |

Rows `L-3` … `L-7` are named because the commissioning brief names them as
*potential* sources. Listing a source here is **not** authorisation. None of
their terms have been read in this session, so none may be designed against as
though the rights were settled. Every entry must treat them as candidates
requiring counsel-reviewed terms before a single byte is ingested.

## Required fields before any source moves to USABLE

1. Exact licence or terms-of-use document, with its retrieval date and a hash.
2. Permitted uses, explicitly including or excluding derivative client work
   product.
3. Storage terms — may it be cached, for how long, in what form.
4. Redistribution terms — may any part reach a client deliverable.
5. Seat/user binding and any per-seat restriction.
6. Attribution requirements.
7. Termination behaviour — what must be deleted when the licence ends.
8. Named human who verified it, and the date.

An entry that designs ingestion of `L-3` … `L-7` without a stated
licence-gate mechanism loses points in band G and, if it presents redistribution
rights it does not have, is disqualified.

## Amendments

*(none)*
