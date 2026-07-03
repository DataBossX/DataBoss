# Source endpoints & auth notes

## okcountyrecords.com
- Base: `https://okcountyrecords.com/api/v1`
- Image by document number: `GET /images?county=<County>&number=<doc>&action=view`
- Image by book/page: `GET /images?county=<County>&book=<bk>&page=<pg>&action=view`
- Section search / recent-filing sweep: `GET /search?county=&township=&range=&section=&filed_after=YYYY-MM-DD`
- Auth: API key sent as `Authorization: Bearer <key>` **and** `apikey=<key>` query param
  (client sends both; keep whichever the account requires). Set `OKCR_API_KEY` in `.env`.
- If you get HTTP 403/407, the host is being blocked by a network egress policy (or the key
  lacks scope). Run TitleFinisher from a machine/network where the host is reachable.

## OCC (Oklahoma Corporation Commission)
- RBDMS well attributes (ArcGIS FeatureServer, public JSON): query by `API`/`API_NUMBER`.
- Form 1002A completion report: scanned in OCC Well Records Imaging
  (`https://imaging.occ.ok.gov/OG/Well Records/<docid>.pdf`); the docid is discovered via
  well-browse. `occ.form_1002a()` is a hook — wire the imaging-id lookup for the account.
- Well Records search UI: `https://public.occ.ok.gov/OGCDWellRecords/Search.aspx`

## OTC (Oklahoma Tax Commission)
- Gross production by PUN/API drives HBP. The public portal is form/session based; wire a
  stable endpoint in `otc.production()` for the account. `OTC.is_hbp()` turns rows into a
  hold-by-production decision (configurable allowed gap).

## Honesty contract
Fetch modules never invent data. If a document cannot be retrieved or its granting language
cannot be parsed unambiguously, the corresponding cell stays flagged and the item appears in
the punch list with the exact document to pull. Nothing is written to a title cell without a
saved source in `data/proof/`.
