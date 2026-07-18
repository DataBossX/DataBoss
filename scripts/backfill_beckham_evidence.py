#!/usr/bin/env python3
"""Backfill the OK-BECKHAM-32-11N-25W evidence ledger and issue register from
the verified evidence register (Diversified_Title_Evidence_Register_32-11N-25W
_2026-07-09.xlsx, Google Drive ID 1nZ46S1CSRk0CvREwHeJUuq8_OiStxerG).

Data below is transcribed from that register — it is evidence *about* the
record, not new conclusions. Rerunnable: outputs are rebuilt from scratch.

Usage:  python scripts/backfill_beckham_evidence.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from core.land_title_os.evidence import Conclusion, EvidenceEntry, EvidenceLedger  # noqa: E402
from core.land_title_os.issues import IssueRegister, OpenItem  # noqa: E402

PROJECT = REPO / "projects" / "OK-BECKHAM-32-11N-25W"

# authority ranks: 1 recorded_instrument_image, 2 official_index,
# 4 client_controlling_data, 6 tax_record, 7 ai_extraction

EVIDENCE = [
    # -- inception patents / receipts (direct images) -----------------------
    ("P-001", 1, "Patent Bk 3/P469", "", "Img 0003",
     "U.S. patent to Cornelius B. Cornelius; NE/4; dated 1907-03-22, recorded 1907-06-08. "
     "No mineral reservation apparent on the reviewed image.",
     "NE/4 (160 ac) Sec 32-11N-25W", "1907-03-22", {"extraction": 0.98}),
    ("P-002", 1, "", "", "Img 0004",
     "Final receiver's receipt to Velmore Biggs (1906-06-28); earliest supplied land-office "
     "evidence for SE/4; patent copy not supplied — OPEN.",
     "SE/4 (160 ac)", "1906-06-28", {"extraction": 0.90, "legal_description": 0.90}),
    ("P-003", 1, "", "", "Img 0005",
     "Final receiver's receipt No. 3894 to Herman Stevens; patent copy not supplied — OPEN.",
     "NW/4 (160 ac)", "1905-05-04", {"extraction": 0.90, "legal_description": 0.90}),
    ("P-004", 1, "", "", "Img 0006",
     "Final receiver's receipt No. 3895 to Augustus P. Stevens; patent copy not supplied — OPEN.",
     "SW/4 (160 ac)", "1905-05-04", {"extraction": 0.90, "legal_description": 0.90}),
    # -- pre-1988 chain (direct images) -------------------------------------
    ("L-001", 1, "502/267", "", "Imgs 1940-1943",
     "Union Oil of California -> Leede Exploration correction assignment (supersedes 471/330); "
     "Crook #1-32 wellbore only, Morrow-Springer 16,210-20,451 ft; Union retained 7/64 "
     "gas/condensate/distillate ORRI and 1/16 oil/casinghead-gas ORRI; no warranty; subject to "
     "unrecorded 1979 agreement.", "Crook wellbore interval", "1981-05-28", {"extraction": 0.98}),
    ("L-002", 1, "509/220", "", "Imgs 1949-1952",
     "Leede -> participant group correction assignment (Mesa 64%, American Petrofina 25%, ENI 5%, "
     "McCall 4%, Midland National Bank Trustee 1%, Sterling Petroleum-1978-A 1% = 100%). Leede "
     "reserved ORRI so aggregate participant NRI = 75%, plus 1/4 after-payout reversion.",
     "Crook wellbore/depth", "1981-09-17", {"extraction": 0.98, "calculation": 0.98}),
    ("L-003", 1, "509/176", "", "Imgs 1946-1948",
     "Leede -> Campbell et al. corrected ORRI assignment; aggregate 2.25% ORRI, cost-free except "
     "taxes; pooling/free-fuel provisions.", "Crook wellbore/depth", "1981-09-17",
     {"extraction": 0.99, "calculation": 0.99}),
    ("L-004", 1, "502/265", "", "Imgs 1938-1939",
     "Leede -> named royalty/ORRI owners (Leede 21.053%, Midland National Bank Trustee 52.632%, "
     "five individuals 5.263% each = 100.000%); expressly excludes Leede's after-payout Crook WI.",
     "All Leede royalty/ORRI in Sec 32", "1981-09-17", {"extraction": 0.99, "calculation": 0.99}),
    ("L-005", 1, "839/188", "", "Img 4103",
     "First City National Bank of Midland, Trustee -> Consolidation of Leede Trusts; transfers "
     "ONLY royalty/ORRI acquired under 502/265; does not transfer the Bank's separate 1% Crook "
     "participant WI.", "Royalty/ORRI under 502/265", "1985-09-12", {"extraction": 0.99}),
    ("L-006", 1, "845/47", "", "Imgs 4120-4121",
     "Cities Service -> Leede borehole rights; Pearl #1-32 wellbore, E/2 SE/4, 11,100-19,480 ft; "
     "reserves 1/8 of 8/8 ORRI; five-year renewal/extension reach.", "E/2 SE/4 Pearl wellbore",
     "1985-07-29", {"extraction": 0.98}),
    ("L-007", 1, "872/279", "", "Imgs 4386-4393",
     "Union -> Leede deep assignment; listed Sec 32 leases top Morrow to 19,480 ft; E/2 SE/4 "
     "limited to 11,100-19,480 ft; excludes prior Crook rights; reserves 1/8 gas/condensate/"
     "distillate + 1/16 oil/casinghead-gas ORRI.", "Top Morrow to 19,480 ft", "1985-10-29",
     {"extraction": 0.98}),
    ("L-008", 1, "903/50", "", "Imgs 4438-4463",
     "PRF Agreement; McCall #1-29 Hunton spacing (S/2 29 + N/2 32) and Pearl #1-32 Lower Morrow "
     "spacing (all 32). Before package payout each PRF .526300% / Leede 98.421100% of defined "
     "LGWI; after payout each PRF 1.315750% / Leede 96.052750%. Percentages of LGWI, not 8/8 WI.",
     "Defined spacing units", "1986-02-19", {"extraction": 0.98, "calculation": 0.98}),
    ("L-009", 1, "987/159", "", "Imgs 4840-4857",
     "TCW/Grantham/Carlson -> Leede assignment and reservation; reserves ORRI equal to .5% of "
     "Leede NRI: McCall .043146%, Pearl .052310%, Crook 0%; no title warranty.",
     "McCall/Pearl/Crook table", "1987-12-02", {"extraction": 0.99, "calculation": 0.99}),
    ("L-010", 1, "995/52", "", "Imgs 4868-4870",
     "First City National Bank release of enumerated 1984/1987 TCW, Vinson and First City liens; "
     "does not prove release of any unlisted lien.", "Enumerated Pearl/Crook/McCall mortgages",
     "1988-01-13", {"extraction": 0.97}),
    ("L-011", 1, "1014/75", "", "Img 4893",
     "Consolidation of Leede Trusts -> Leede Exploration; N/2 Sec 32 all depths below top Hunton "
     "+ S/2 Sec 29. Purports to assign all OGLs and working interests without warranty, but "
     "source into Consolidation proves only royalty/ORRI — SOURCE-TITLE DEFECT. Last supplied "
     "record image (direct-image cutoff).", "N/2 below top Hunton", "1988-02-18",
     {"extraction": 0.99, "calculation": 0.20}),
    # -- modern Diversified chain (official county index / public metadata) --
    ("C-001", 2, "2371/470-494", "I-2022-000152", "okcountyrecords.com/detail/beckham/2022-000152",
     "KL CHK SPV LLC -> Diversified Production LLC and OCM Denali Holdings LLC assignment; all 16 "
     "Q-Q ticks; long description; fractions/schedules absent.", "All Sec 32 Q-Q boxes",
     "2021-12-02", {"extraction": 0.99, "calculation": 0.0}),
    ("C-002", 2, "2395/415-464", "I-2022-004838", "okcountyrecords.com/detail/beckham/2022-004838",
     "DP Legacy Tapstone LLC -> Diversified ABS VI Upstream LLC and DP Sooner HoldCo LLC "
     "conveyance; all 16 Q-Q ticks; estates/fractions/schedules absent.", "All Sec 32 Q-Q boxes",
     "2022-11-18", {"extraction": 0.99, "calculation": 0.0}),
    ("C-003", 2, "2395/967-972", "I-2022-004938", "okcountyrecords.com/detail/beckham/2022-004938",
     "KeyBank financing-statement TERMINATION (not a title conveyance) re Tapstone/Diversified; "
     "distinguishes 2395/967 from the ABS conveyance at 2395/415.", "", "2022-11-18",
     {"extraction": 0.99}),
    ("C-004", 2, "2400/551-567", "I-2023-000796", "okcountyrecords.com/detail/beckham/2023-000796",
     "DP Sooner HoldCo LLC -> Diversified Production LLC conveyance; long description; relation "
     "to prior branch and subject asset fraction open.", "Long-description package", "2023-03-02",
     {"extraction": 0.99, "calculation": 0.25}),
    ("C-005", 2, "2451/4-23", "I-2025-001808", "okcountyrecords.com/detail/beckham/2025-001808",
     "Diversified Energy Company PLC merger metadata; merged/surviving entities and title effect "
     "absent.", "", "2025-05-13", {"extraction": 0.99, "calculation": 0.20}),
    ("C-006", 2, "2476/121-130", "I-2026-000215", "okcountyrecords.com/detail/beckham/2026-000215",
     "Agreement among Diversified Production LLC and five DP affiliates; not facially a "
     "conveyance; long description and effect absent.", "", "2026-01-23",
     {"extraction": 0.99, "calculation": 0.10}),
    # -- controlling local sources ------------------------------------------
    ("S-001", 4, "", "", r"D:\Desktop\Horizon\32-11N-25W, Beckham County\source_canonical\Section Notes\Section Notes.xlsx",
     "Section Notes: inception Patent-1988; last book/page 2490/471 (WD); index certified "
     "through 2026-07-01.", "", "", {"extraction": 0.95}),
    ("S-002", 2, "", "", r"D:\Desktop\Horizon\32-11N-25W, Beckham County\source_canonical\Index\Protocoled Index.pdf",
     "Protocoled county index, 62 scanned pages; post-1988 entries are index-only because record "
     "images stop April 1988.", "", "", {"extraction": 0.90}),
    ("S-003", 1, "", "", r"D:\Desktop\Horizon\32-11N-25W, Beckham County\source_canonical\Images",
     "Record-image archive: 4,893 JPGs, continuous 0001-4893; exact cutoff Bk 1014/P75.",
     "", "", {"extraction": 0.98}),
    ("S-004", 6, "", "", r"D:\Desktop\Horizon\32-11N-25W, Beckham County\source_canonical\Plat Map\Plat Map.pdf",
     "Assessor parcel map/account listing printed 2026-07-02; ten surface parcels totaling "
     "exactly 640.00 acres; not a mineral-title source.", "Sec 32 surface parcels", "2026-07-02",
     {"extraction": 0.95, "calculation": 1.0}),
    ("S-005", 8, "", "", r"D:\Desktop\Horizon\32-11N-25W, Beckham County\source_canonical\Tax Roll\Tax Roll.pdf",
     "DEFECTIVE: byte-for-byte duplicate of the plat map; no actual tax roll supplied.",
     "", "", {"extraction": 0.99}),
    ("O-001", 3, "", "", "OCC RBDMS well-status CSV (rbdms-wells.csv)",
     "Official OCC well-status dataset; section well/status/operator context, not title.",
     "", "", {"extraction": 0.95}),
]

CONCLUSIONS = [
    ("C1", "Diversified-affiliated entities acquired a material interest indexed against all of "
           "Section 32 through the 2021/2022 KL CHK/Tapstone transaction structure. QUALIFIED.",
     ["C-001", "C-002", "S-002"], "ownership"),
    ("C2", "Principal index-supported chain: Chesapeake affiliates -> KL CHK SPV LLC -> "
           "Diversified Production LLC/OCM Denali -> DP Legacy Tapstone LLC -> Diversified ABS VI "
           "Upstream LLC and DP Sooner HoldCo LLC. Current vesting OPEN.",
     ["C-001", "C-002", "C-004", "S-002"], "ownership"),
    ("C3", "DP Sooner HoldCo LLC conveyed a long-description asset package to Diversified "
           "Production LLC at Bk 2400/P551-567; missing exhibit prevents tying the subject asset "
           "and fraction to the prior branch. OPEN.", ["C-004"], "ownership"),
    ("C4", "No exact present WI, NRI, leasehold decimal, ORRI decimal, mineral interest, royalty "
           "interest, or net acres can be calculated for Diversified from the delivered evidence "
           "(operative post-1988 instruments and schedules absent). OPEN ITEM.",
     ["C-001", "C-002", "C-004", "S-002", "S-003"], "working_interest"),
    ("C5", "No direct record evidence reviewed establishes a Diversified mineral-fee, "
           "lessor-royalty, NPRI, or surface ownership interest; absence of evidence is not a "
           "negative title opinion. NOT ESTABLISHED.", ["S-003", "S-004"], "ownership"),
    ("C6", "Book 2395/P967 is a KeyBank financing-statement termination, not a title conveyance; "
           "the Diversified ABS conveyance is Book 2395/P415. RESOLVED.",
     ["C-002", "C-003"], "other"),
    ("C7", "Historical interests are subject to material ORRIs, payout/reversion provisions, "
           "unrecorded development agreements, wellbore/depth limits, and potentially unreleased "
           "blanket liens; present survival unresolved. OPEN.",
     ["L-001", "L-002", "L-003", "L-006", "L-007", "L-008", "L-009", "L-010"], "other"),
    ("C8", "Section-level well activity does not establish that any particular lease in "
           "Diversified's chain is held by production (no lease-to-well schedule, allocation, "
           "cessation history, or savings-clause analysis supplied). OPEN ITEM.",
     ["O-001"], "lease"),
]

# The register's 12-row Open_Requirements table.
REQUIREMENTS = [
    ("critical", "Obtain certified, complete copies of the 2020-2026 operative instruments and "
     "every exhibit/schedule: at minimum 2340/403, 2340/490, 2371/470, 2371/495, 2371/514, "
     "2371/533, 2389/500, 2389/581, 2395/415, 2400/551, 2451/4, 2476/121.",
     "Required for estate, decimal, exclusions, depth, effective date, warranty, "
     "after-acquired-title and current vesting."),
    ("critical", "Pull the post-April-1988 predecessor chain, starting 1014/76, 1014/228, "
     "1016/38, then the Leede/TCW/NICOR/Exxon/Leede Operating/St. Mary/Sanguine/Kabala/"
     "Chesapeake links.", "Closes the 1988-2020 record gap and reconciles parallel branches."),
    ("critical", "Obtain and abstract every underlying OGL: 63/33, 264/345, 307/31, 340/302, "
     "340/304, 340/323, 342/564, 342/566, 352/719, 352/721, 376/369, plus later-scheduled "
     "leases.", "Needed for primary term, royalty, pooling, Pugh/depth, continuous drilling, "
     "extension and termination analysis."),
    ("critical", "Resolve payout/reversion and unrecorded agreements (7/9/1979, 11/20/1979, "
     "1/7/1980, 2/7/1984, 3/20/1985, Exxon/NICOR/Vinson/White/TCW); secure payout statements "
     "and required reassignments.", "Determines Crook/PRF/Leede WI and ORRI burdens."),
    ("critical", "Cure the Midland Bank/Consolidation source-title defects: prove transfer of "
     "the Bank's separate 1% participant WI; identify the WI source for Bk 1014/P75; confirm "
     "disposition of Consolidation's 52.632% share of Leede royalty/ORRI.",
     "Avoids nemo-dat and stranded-ORRI issues."),
    ("high", "Reconcile the FourPoint/Unbridled/MNR branch with Tapstone/KL CHK/Diversified "
     "(2015 wellbore sale, 2015/2016 FourPoint instruments, 2020 assignments, 2023 MNR "
     "conveyance schedules).", "Determines whether branches are separate wells/leases/depths, "
     "retained interests, or overlapping title."),
    ("high", "Establish HBP and current producing formations lease-by-lease: match leases to "
     "wells/units; obtain OCC orders, completions, production histories, shut-in/cessation "
     "data, savings-clause facts.", "Section-level production alone is not proof of lease "
     "perpetuation."),
    ("high", "Close financing/lien status: compare mortgage and UCC collateral schedules to the "
     "final lease schedule; obtain missing releases, subordinations, or payoff evidence.",
     "Blanket lien filings and releases are indexed but applicability cannot be determined."),
    ("high", "Obtain merger/name-change authority and current entity evidence for 2389/500, "
     "2389/581, 2451/4, 2476/121 (certificates, plans, good standing, complete grantee lists).",
     "Required to establish the current vested record entity and execution authority."),
    ("high", "Complete fee/mineral chain and patent inception if required by assignment scope "
     "(SE/NW/SW patents; quarter-by-quarter mineral/royalty chain incl. probate/trust/corporate "
     "succession).", "Present review does not support a negative mineral/royalty opinion."),
    ("critical", "Run courthouse continuation from 2026-07-01 through the final effective date, "
     "including records without legal descriptions and UCC central filings.",
     "Supplied section index is certified only through 2026-07-01."),
    ("medium", "Replace the defective tax-roll item: obtain the actual current tax roll and "
     "confirm ad valorem/production-tax status.", "Supplied Tax Roll PDF duplicates the "
     "assessor parcel map (S-005)."),
]


def main() -> None:
    ledger_path = PROJECT / "evidence.jsonl"
    issues_path = PROJECT / "issues.json"
    for p in (ledger_path, issues_path):
        if p.exists():
            p.unlink()

    ledger = EvidenceLedger(ledger_path)
    id_map: dict[str, str] = {}
    for reg_id, rank, book_page, instrument, image_ref, text, legal, eff, conf in EVIDENCE:
        eid = ledger.add_evidence(EvidenceEntry(
            source_document=f"register:{reg_id}", authority_rank=rank,
            extracted_text=text, book_page=book_page, instrument_number=instrument,
            image_reference=image_ref, legal_description=legal, effective_date=eff,
            confidence=conf, verification_status="human_verified",
            explanation="Transcribed from Diversified_Title_Evidence_Register_32-11N-25W_"
                        "2026-07-09.xlsx (Drive 1nZ46S1CSRk0CvREwHeJUuq8_OiStxerG)."))
        id_map[reg_id] = eid

    for cid, statement, refs, kind in CONCLUSIONS:
        ledger.add_conclusion(Conclusion(
            statement=statement, evidence_ids=[id_map[r] for r in refs], kind=kind,
            verification_status="human_verified",
            explanation=f"Register conclusion {cid}."))

    register = IssueRegister(issues_path)
    for severity, description, reason in REQUIREMENTS:
        register.open_item(OpenItem(
            description=description, severity=severity, required_research=reason,
            affected_conclusion="", assigned_agent=""))

    print(f"evidence entries: {len(ledger.entries)}")
    print(f"conclusions:      {len(ledger.conclusions)}")
    print(f"open items:       {len(register.open_items())}")
    print(f"wrote {ledger_path}\nwrote {issues_path}")


if __name__ == "__main__":
    main()
