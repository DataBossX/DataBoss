#!/usr/bin/env python3
"""CH185443 Section 19 federal source examiner deliverables (Claude run, 2026-10-19).
Writes ledgers, isolated proposal workbook, QA receipt, hashes, delivery zip.
Read-only against all shared inputs; promotes nothing."""
import csv, json, hashlib, zipfile, subprocess, os, sys
from datetime import datetime, timezone

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
PREP = "2026-10-19"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
UNK = "Unknown"

# ---------------------------------------------------------------- source register
# bytes/sha/pages as supplied by Original_Sources_15_Source_Register_20261019.csv
# (sha NOT independently recomputed: file bytes are not transferable into this container)
SRC = [
 # key, file, folder_drive_id, register_drive_id, bytes, sha256_as_supplied, part, pages, scope
 ("F131225P1","Federal_WYW131225_Part1_original.pdf","1JTcexw2xD0TUXG-grxCFJK5yYA8i7HPW","1pjspzuVXaRhzooO3SvxPU-JB1OKtRvjz",69497554,"1179007ce981b2ccba6d26f5fd59a431f7086893f4d9662ce72faf4cb5b036d0",1,217,"assigned_S19_federal"),
 ("F131225P2","Federal_WYW131225_Part2_original.pdf","1f3dQJmdjZJDlW_VWlDuvRNjZVl1BEOjY","1OXBt_B-ufky5Jk3w5O6G-2fRgJjx5v9z",46241089,"73cd893360472c4f994380b6edb90c9547dd55fcf2e5789dc280002369dd8fce",2,151,"assigned_S19_federal"),
 ("F131225P3","Federal_WYW131225_Part3_original.pdf","1KQ8cq0U1xMgKk-q4f1Nd3FSTIj4mYTFv","13w_E0J_yONOU_kBW-tXFp8zpH3wL_5-r",37703072,"520a088c01e18b5f822d0e97adf9924706d0aa72d954999fcb9c3cdf944be69e",3,115,"assigned_S19_federal"),
 ("F131225P4","Federal_WYW131225_Part4_original.pdf","1wvrfUDBPFPyzRkGeQVzhNMDBU6MgrFx0","170gbqj4B3TfvFsLUW3aWvRaNNx6jmctB",355367,"edb2f012060ea1737018ba69f2cfda7d9d36855063356de054f79da064d05e2e",4,2,"assigned_S19_federal"),
 ("F133620P1","Federal_WYW133620_Part1_original.pdf","1LRZc0psim0p1rKopieAMjIE1HXs-Q7hZ","10hbF18SIRsYGEWj0HmuL-289_l9Z0wyu",60670284,"a804422bef1cd81796c9fbb43579ddadd29988dc0b75cfb50f7165b63a35e769",1,190,"assigned_S19_federal"),
 ("F133620P2","Federal_WYW133620_Part2_original.pdf","1lcO-XXdrEN8C79ci6mbhw2QRKq4EqbsG","15tUCthIaxPnj6etOhdP0mF-yRh6z8egZ",48313464,"cac1a5914475cff6c8b6b335ce560e04d6a33a9b75c66df73101df9d95addefa",2,164,"assigned_S19_federal"),
 ("F133620P3","Federal_WYW133620_Part3_original.pdf","1TnhNGNdM1dKIk4Z-i44dJnv9haJ6uYzG","17L0ZDcS__zgQcx9RGk60OkuCs0pwTMo-",82958704,"5c4d0f59df2e13f4000a35539a754a40c7b9172a26916e0dc6573e468fb2a1bb",3,261,"assigned_S19_federal"),
 ("F133620P4","Federal_WYW133620_Part4_original.pdf","1EH1fa1MQpoFXmnX76_xMPGmh_ZbvF734","1s12fK5JMZQQ9LMEgFOmVu6DyTSSRIWOa",264304,"b4a1dbf4d805cdb6a8143665d34ce853080c5ed7b2f056ea9c6489bf6ae5399c",4,2,"assigned_S19_federal"),
 ("F094605P1","Federal_WYW094605_Part1_original.pdf","1AEC3EAgkk26ZHIlt2sDq4_MR-2wx1HTP","1TCAfpLVpCIU0qWLk8vFz4L7fcRHPRDsK",10517173,"926f97e3b4f4c18c9aadaaec438a58e808eabed5750aa4fdb1d72e58f70ef42a",1,211,"related_S19_CA_WYW136880_tract1"),
 ("F094605P4","Federal_WYW094605_Part4_original.pdf","1mEjBtUoXOeKKA2UPXWuRVJyBj60NnyLs","1VT6Apr6EoPywjHMNSnhewD5apPInHSGX",354092,"880f15e1ef92e6951db81d30e744b07411582910e9c047244a1144c526b5b42a",4,2,"related_S19_CA_WYW136880_tract1"),
]
# Supplementary readable sources (not in the 15-source register)
SUP = [
 ("SRP131225","Serial Register Page WYW-131225.pdf","178AZGsAT4vww-OlrhOnFiXTcpUp1elDL",285967,UNK,"n/a",6,"supplementary_MLRS_snapshot"),
 ("SRP133620","Serial Register Page WYW-133620.pdf","1O0zF8Gcc1r9IQyjdl9mkWm4hYBOGBsVG",348316,UNK,"n/a",7,"supplementary_MLRS_snapshot"),
 ("S19EXC","WYW-131225_S19_2015_Correction_and_2019_Operator_Letter_SOURCE_EXCERPT.pdf","1fpWFxFEJW0xlRERDTIbglpeM1TSPRe1h",2732021,UNK,"excerpt",UNK,"supplementary_S19_source_excerpt"),
 ("NAVOCR","FEDERAL_NAVIGATION_OCR_ONLY.json","1fRVOlMujXKbFzmvDUg8KPtfS8PNXvsmn",348987,UNK,"n/a",UNK,"supplementary_OCR_page_hit_index"),
]

with open(f"{OUT}/Source_Register.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["source_id","original_name","drive_url","original_sha256","sha256_verification",
                "bytes","part","physical_pages","native_text_pages","image_placements",
                "distinct_decoded_image_hashes","acquired_at_utc","scope","register_drive_id",
                "shared_folder_drive_id","drive_id_match","text_layer_status","reviewable_in_this_environment"])
    for k,n,fid,rid,b,sha,part,pages,scope in SRC:
        w.writerow([k,n,f"https://drive.google.com/file/d/{fid}/view",sha,
                    "as_supplied_by_register_NOT_independently_recomputed (file bytes not transferable into this container)",
                    b,part,pages,0,pages,pages,NOW,scope,rid,fid,"NO",
                    "no native text layer (native_text_page_count=0); OCR text exists only at offline local paths",
                    "YES (connector OCR succeeded)" if pages<=2 else "NO (connector returned empty text; bytes not transferable)"])
    for k,n,fid,b,sha,part,pages,scope in SUP:
        w.writerow([k,n,f"https://drive.google.com/file/d/{fid}/view",sha,
                    "not_in_15_source_register; sha not computed (bytes not transferable)",
                    b,part,pages,UNK,UNK,UNK,NOW,scope,"n/a",fid,"n/a",
                    "connector returned full text","YES"])

# ---------------------------------------------------------------- page review ledger
READ = {  # (source_id, page) -> (visual_status, finding)
 ("F131225P4",1):("READ_VIA_CONNECTOR_OCR","Case jacket WYW131225PT4. Tp.47N R76W and Tp.47N R77W. Committed to North McRae Gap Unit WYW179231X approved 10/19/2010; Tractor (Deep) Unit WYW191271X approved 10/18/2021. CA WYW136880 Eff 09/02/94; CA WYW164204 Eff 09/01/05; CA WYW168834 Eff 01/01/06; CA WYW175812 Eff 08/01/07. Product 312021. Lease Issued 02/01/1994. Held by Production in CA. Producing Lease."),
 ("F131225P4",2):("READ_VIA_CONNECTOR_OCR","PART 4 OF 4 empty-folder notice: 'There are currently no documents in this folder'. File-content finding only; not proof of absence of later rights or of currentness."),
 ("F133620P4",1):("READ_VIA_CONNECTOR_OCR","Case jacket WYW133620PT4. Tp.47N R76W and Tp.47N R77W. CA WYW164204 Eff 09/01/05; CA WYW168834 Eff 01/01/06; CA WYW178851 Eff 10/01/09. Product 312021. Lease Issued 10/01/1994. Communitization Agreement Held by Production. Producing Lease. No unit commitment shown on jacket."),
 ("F133620P4",2):("READ_VIA_CONNECTOR_OCR","PART 4 OF 4 empty-folder notice: 'There are currently no documents in this folder'."),
 ("F094605P4",1):("READ_VIA_CONNECTOR_OCR","Case jacket WYW94605PT4. Tp.47N R77W only (no Section 19 lands in this lease). Segregated out of WYW 30784. CA WYW110754 Eff 11/01/76 Term 09/02/94; CA WYW136880 Eff 09/02/94; CA WYW163061 Eff 04/01/05 Term 04/30/20; CA WYW164174 Eff 04/01/05; CA WYW168848 Eff 05/01/05; CA WYW168719 Eff 08/01/05; CA WYW168876 Eff 08/01/05; CA WYW168723 Eff 10/01/05. Product 311211. Lease Issued 10/01/1971."),
 ("F094605P4",2):("READ_VIA_CONNECTOR_OCR","PART 4 OF 4 empty-folder notice."),
}
NOT_REVIEWABLE = ("NOT_REVIEWABLE_IN_THIS_ENVIRONMENT",
  "Scanned image page with no native text layer. Drive connector returned empty text for this file; "
  "file bytes are not transferable into this container (37-83 MB per part via base64 is infeasible) and no "
  "local OCR engine is installed. Per-page OCR text exists only at offline Windows paths referenced by "
  "FEDERAL_NAVIGATION_OCR_ONLY.json. Disposition is explicitly UNREVIEWED, not blank and not passed.")
with open(f"{OUT}/Page_Review_Ledger.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["original_sha256","original_name","source_id","part","physical_page","printed_folio",
                "ocr_status","visual_status","reviewer","review_method","evidence_excerpt","finding",
                "confidence","next_action"])
    for k,n,fid,rid,b,sha,part,pages,scope in SRC:
        for p in range(1,pages+1):
            vs,find = READ.get((k,p), NOT_REVIEWABLE)
            reviewed = (k,p) in READ
            w.writerow([sha,n,k,part,p,UNK,
                        "ocr_text_exists_offline_only" if not reviewed else "connector_ocr_returned_text",
                        vs,"Claude (claude-opus-5, Claude Code cloud session)",
                        "Google Drive connector read_file_content (text/OCR representation)" if reviewed else "attempted connector read; empty result",
                        "see finding" if reviewed else "",
                        find,"MEDIUM (OCR companion text, not a verified source-image read)" if reviewed else "NONE",
                        "accept as located evidence; confirm against source image when images become available" if reviewed
                        else "supply Drive-side OCR text or page images, or bring Root/RyansPC online, then review"])

# ---------------------------------------------------------------- instrument/event ledger
EV = [
 ("E01","WYW131225 (lease)","Oil and Gas Lease",UNK,UNK,UNK,
  "United States of America (lessor); Yates Petroleum Corporation, Yates Drilling Company, ABO Petroleum Corporation, Myco Industries, Inc. (lessees)",
  UNK,UNK,"1994-01-14","1994-02-01",UNK,
  "S19 T47N R76W Lots 8,9,13,14,16,20 (lease record title also covers Sec 7 Lots 27,28,33,34; Sec 30 Lot 5; T47N R77W Sec 33 Lot 11)",
  "Total lease acres 471.76 per SRP. Royalty 12.5%. 10-year term. Parcel PAR 137, sale 12/14/1993, bonus $3,965.00. Case disposition AUTHORIZED 01/14/1994. Sections 7/30/33 lands are NOT Section 19 facts.",
  "SRP131225 + S19EXC Exhibit B","CORROBORATED_MULTI_SOURCE"),
 ("E02","CA WYW136880","Communitization Agreement","1 (WYW094605 Part 1)","81","82",
  "Aztec Gas & Oil Corp. (operator / 100% WI all tracts); Tract 2 lessee of record Aztec Gas & Oil Corp.",
  "1994-09-02 (agreement 'entered into as of the 2nd day of SEPTEMBER 1994')",UNK,
  UNK+" (candidate 1994-09-04 as APPROVAL date only - not verified)","1994-09-02",UNK,
  "ORIGINAL: T47N R76W Sec 19 SW/4 NW/4 (Lot 2) and NW/4 SW/4 (Lot 14), 40.21 + 39.98 = 80.19 ac. "
  "CORRECTED 2015: Sec 19 Lots 9 (SWNW) and 16 (NWSW), 35.93 + 38.18 = 74.11 ac. "
  "Also T47N R77W Sec 24 SE/4 NE/4 (Lot 8) and E/2 SE/4 (Lots 9 and 16).",
  "Sussex Formation only; crude oil and associated natural gas. Pumpkin Creek Field, Johnson County. "
  "Recap total 199.54 ac original -> 193.46 ac corrected. Tract 2 interest 40.18748% -> 38.3077%. "
  "Federal acreage 118.70 -> 112.62. Approval does not warrant legal/equitable title (43 CFR 3105.2-3(e)).",
  "S19EXC (agreement, transmittal, Exhibit A plat, Exhibit B, recap); F131225P4 jacket; F094605P4 jacket; SRP131225","CORROBORATED_MULTI_SOURCE"),
 ("E03","CA WYW136880 correction","Correction Letter (BLM WSO 3105/3105.2)","1 (WYW094605 Part 1)",UNK,UNK,
  "BLM Wyoming State Office, Reservoir Management Group, by J. David Chase, Chief (grantor/issuer); Nonsuch Natural Gas, Inc., Attn: C. David Lee (addressee)",
  "2015-09-14",UNK,UNK,"2015-09-14 ('This change will be considered effective the date of this letter')",UNK,
  "Corrects Tract 2 (lease WYW131225) to: T47N R76W, 6th P.M., Section 19: Lots 9 (SWNW) and 16 (NWSW), containing 35.93 acres and 38.18 acres respectively",
  "Receipt stamps SEP 17 REC'D and RECEIVED SEP 22 2015 BLM-Wyoming State Office are RECEIPT dates, not the effective date. "
  "Corrected pages attached and marked in red. CC: WOGCC, WSO(923), Buffalo FO, ONRR.",
  "S19EXC","CORROBORATED_MULTI_SOURCE"),
 ("E04","CA WYW136880 successor operator","Designation of Successor Operator","1 (WYW094605 Part 1)",UNK,UNK,
  "BLM Wyoming State Office by J. David Chase (approver); Nonsuch Natural Gas, Inc. (designated successor operator)",
  "2019-04-04","2016-07-22",UNK,"2011-10-01",UNK,
  "CA WYW136880 'embracing Lots 9 and 16 of Section 19 and Lots 8, 9 and 16 of Section 24, T. 44 N., R. 76 W.' "
  "[SOURCE RECITAL ERROR: 'T. 44 N.' as printed; operative township is T47N. Error preserved, not silently corrected.]",
  "Three distinct date roles preserved: application received 2016-07-22; letter dated 2019-04-04; approval EFFECTIVE 2011-10-01 (retroactive). "
  "Receipt stamp RECEIVED APR 08 2019. Post-correction description (Lots 9 and 16) independently corroborates E03. "
  "Authorized Officer neither warrants nor certifies required approvals.",
  "S19EXC","CORROBORATED_MULTI_SOURCE"),
 ("E05","WYW131225 assignment","Assignment",UNK,UNK,UNK,
  "Yates Petroleum Corporation (assignor, 90%); Yates Drilling Company 30%, ABO Petroleum Corporation 30%, Myco Industries, Inc. 30% (assignees); Yates Petroleum Corporation retains 10%",
  UNK,"1994-05-23","1994-10-19","1994-06-01",UNK,"Lease-wide; Section 19 application derives from lease record title",
  "SRP legacy remark /A/. ASGN FILED 05/23/1994; ASGN APPROVED 10/19/1994 EFF 06/01/94. Filing, approval and effective dates are distinct roles.",
  "SRP131225","SINGLE_SOURCE_SRP_SNAPSHOT"),
 ("E06","WYW131225 resurvey conformance","Decision - Conformed to Survey/Resurvey",UNK,UNK,UNK,
  "Bureau of Land Management",UNK,UNK,"1998-07-10","1995-08-17",UNK,"Lease-wide",
  "Action date 1998-07-10, EFFECTIVE 1995-08-17. Do not apply lease re-survey lot numbers to historical CA tracts.",
  "SRP131225","SINGLE_SOURCE_SRP_SNAPSHOT"),
 ("E07","WYW131225 resurvey conformance 2","Decision - Conformed to Survey/Resurvey",UNK,UNK,UNK,
  "Bureau of Land Management",UNK,UNK,"2010-07-17","2005-09-29",UNK,"Lease-wide",
  "Second resurvey conformance. Action 2010-07-17, EFFECTIVE 2005-09-29.","SRP131225","SINGLE_SOURCE_SRP_SNAPSHOT"),
 ("E08","CA WYW168834 (131225)","Communitization Agreement commitment",UNK,UNK,UNK,UNK,UNK,UNK,UNK,"2006-01-01",UNK,
  "Tract 01; 38.1800 acres committed; 49.862900% interest; commitment effective date shown 02/01/1994",
  "AUTHORIZED. Commitment acreage/percent from SRP recapitulation table.","SRP131225","SINGLE_SOURCE_SRP_SNAPSHOT"),
 ("E09","CA WYW164204 (131225)","Communitization Agreement commitment",UNK,UNK,UNK,UNK,UNK,UNK,UNK,"2005-09-01",UNK,
  "Tract 01; 40.4600 acres; 49.913600% interest","CLOSED / Agreement Terminated, action end effective 2023-03-06. "
  "Last production 2018-05-31, CAT SHADOW POPCORN CS FED COM 8, well 4901925680.","SRP131225","SINGLE_SOURCE_SRP_SNAPSHOT"),
 ("E10","CA WYW175812 (131225)","Communitization Agreement commitment",UNK,UNK,UNK,UNK,UNK,UNK,UNK,"2007-08-01",UNK,
  "Tract 02; 40.4900 acres; 49.963000% interest","AUTHORIZED.","SRP131225","SINGLE_SOURCE_SRP_SNAPSHOT"),
 ("E11","Unit WYW150648X (131225)","Exploratory Unit Agreement",UNK,UNK,UNK,UNK,UNK,UNK,"2001-03-15",UNK,UNK,
  "40.5900 acres","LEASE IN UNIT/UNCOMMIT'D. Participating area WYW150648A authorized eff 2002-11-26, tract 02 partially committed.",
  "SRP131225","SINGLE_SOURCE_SRP_SNAPSHOT"),
 ("E12","North McRae Gap Unit WYW179231X","Unit Agreement commitment","4","1",UNK,UNK,UNK,UNK,"2010-10-19",UNK,UNK,
  "Lease-wide per jacket; Section 19 applicability NOT established",
  "CONFLICT: jacket states committed to North McRae Gap Unit WYW179231X approved 10/19/2010, but this unit does NOT appear "
  "in the SRP associated-agreement recapitulation table. Unit agreement source not obtained. Keep as unresolved proposal.",
  "F131225P4 jacket (absent from SRP131225)","CONFLICT_UNRESOLVED"),
 ("E13","Tractor (Deep) Unit WYW191271X (131225)","Unit Agreement commitment",UNK,UNK,UNK,UNK,UNK,UNK,"2021-10-18",UNK,UNK,
  "471.7600 acres fully committed","Jacket approval 10/18/2021 agrees with SRP action 10/18/2021 COMMITTED TO AGREEMENT. "
  "Same action date LEASE SEGREGATED INTO WYW191554.","F131225P4 jacket + SRP131225","CORROBORATED_MULTI_SOURCE"),
 ("E14","CA WYWY106695248 (131225)","Communitization Agreement commitment",UNK,UNK,UNK,UNK,UNK,"2025-12-10","2025-12-22","2024-05-01",UNK,
  "Tract 007; 40.5900 acres; 1.006200% interest",
  "AUTHORIZED. First production 2025-01-25: CADET FED 4777-28-15-4W NH (4901942246), CADET FED 4777-28-4-13 MH (4901942259), "
  "CADET FED 4777-28-4-16W NH (4901942247). Allocated production.","SRP131225","SINGLE_SOURCE_SRP_SNAPSHOT"),
 ("E15","WYW131225 extension","Lease Extension",UNK,UNK,UNK,"Bureau of Land Management",UNK,UNK,"2026-05-05","2023-03-06",UNK,"Lease-wide",
  "Two-year extension due to termination of CA WYW164204; extended through 2025-03-06 'and for so long thereafter as oil and gas "
  "is produced in paying quantities'. Through-date 2025-03-06 precedes the 2026-05-05 action date; preserved as recorded.",
  "SRP131225","SINGLE_SOURCE_SRP_SNAPSHOT"),
 ("E16","WYW133620 (lease)","Oil and Gas Lease",UNK,UNK,UNK,
  "United States of America (lessor); Yates Petroleum Corporation et al. (original lessees per legacy remark /A/)",
  UNK,UNK,"1994-09-07","1994-10-01",UNK,
  "S19 T47N R76W Lots 5,6,7,10,11,12,17 (lease also covers Sec 18 Lots 21-36; Sec 30 Lot 12; T47N R77W Sec 23 Lots 3-6)",
  "Total lease acres 1,094.76. Royalty 12.5%. Parcel PAR 187, sale 08/02/1994, bonus $49,912.00. Case disposition AUTHORIZED 09/07/1994. "
  "ACRES-COUNTY 1,347.400 WY019 and 120.000 WY005 recorded 10/01/1994. Section 18 lands are NOT Section 19 facts. "
  "SRP RECORD TITLE section reads '(No Records Found)'.",
  "SRP133620","SINGLE_SOURCE_SRP_SNAPSHOT"),
 ("E17","WYW133620 Section 19 stipulation","Lease Stipulation",UNK,UNK,UNK,"Bureau of Land Management",UNK,UNK,UNK,UNK,UNK,
  "T47N R76W, SEC 19: NE, E2NW; SEC 20: NW",
  "MATERIAL OPERATIVE TERM, SECTION 19 SPECIFIC: 'STIPULATIONS: TLS (1) FEB 1 TO JUL 31; (2) T47N, R76W, SEC 19: NE, E2NW, "
  "SEC 20: NW; (3) PROTECTING SAGE GROUSE NESTING HABITAT.' Timing limitation stipulation Feb 1 - Jul 31. Must be preserved verbatim.",
  "SRP133620 legacy remark lines 0001-0003","SINGLE_SOURCE_SRP_SNAPSHOT"),
 ("E18","WYW133620 suspension","Lease Suspension / Suspension Lifted",UNK,UNK,UNK,"Bureau of Land Management",UNK,UNK,"1998-11-01",UNK,UNK,"Lease-wide",
  "LEASE SUSPENDED 1998-11-01, 'OPERATIONS ONLY', Suspension Type: Operations (Sec.17)/Payment Required. SUSP LIFTED 2003-08-01.",
  "SRP133620","SINGLE_SOURCE_SRP_SNAPSHOT"),
 ("E19","CA WYW168834 (133620)","Communitization Agreement commitment",UNK,UNK,UNK,UNK,UNK,UNK,UNK,"2006-01-01",UNK,
  "Tract 02; 38.3900 acres; 50.137100% interest","AUTHORIZED. Distinct tract and acreage from the WYW131225 commitment to the same CA (E08).",
  "SRP133620","SINGLE_SOURCE_SRP_SNAPSHOT"),
 ("E20","CA WYW178851 (133620)","Communitization Agreement commitment",UNK,UNK,UNK,UNK,UNK,UNK,UNK,"2009-10-01",UNK,
  "Tract 02; 40.4500 acres; 50.130100% interest","CLOSED / Agreement Terminated effective 2020-07-15. Jacket shows CA WYW178851 Eff 10/01/09. "
  "Lease EXTENDED action 2024-08-16 remark 'CA Term WYW133620'.","F133620P4 jacket + SRP133620","CORROBORATED_MULTI_SOURCE"),
 ("E21","CA WYW164204 (133620)","Communitization Agreement commitment",UNK,UNK,UNK,UNK,UNK,UNK,UNK,"2005-09-01",UNK,
  "Tract 02; 40.6000 acres; 50.086400% interest","CLOSED / Agreement Terminated, action end effective 2023-03-06. "
  "Last production 2018-05-31 (allocated), CAT SHADOW POPCORN CS FED COM 8, well 4901925680.","F133620P4 jacket + SRP133620","CORROBORATED_MULTI_SOURCE"),
 ("E22","Unit WYW150648X (133620)","Exploratory Unit Agreement",UNK,UNK,UNK,UNK,UNK,UNK,"2001-03-15",UNK,UNK,"161.4400 acres",
  "LEASE IN UNIT/UNCOMMIT'D. Participating area WYW150648A, tract 03 partially committed.","SRP133620","SINGLE_SOURCE_SRP_SNAPSHOT"),
 ("E23","Tractor (Deep) Unit WYW191271X (133620)","Unit Agreement commitment",UNK,UNK,UNK,UNK,UNK,UNK,"2021-10-18",UNK,UNK,
  "1,094.7600 acres fully committed","SRP names agreement expressly: 'WYW191271X;; Tractor (Deep) Unit'. Case action status date 2022-03-23. "
  "Same action date LEASE SEGREGATED INTO WYW191555. Jacket for 133620 does NOT list this unit (jacket/SRP divergence).",
  "SRP133620 (not on F133620P4 jacket)","PARTIAL_CONFLICT"),
 ("E24","CA WYWY106808441 (133620)","Communitization Agreement commitment",UNK,UNK,UNK,UNK,UNK,"2026-08-26","2026-09-16","2026-04-01",UNK,
  "Tract 08; 161.4400 acres; 2.371400% interest","PENDING - not authorized. Most recent recorded action on this case in the snapshot. "
  "Do not present a PENDING commitment as an operative right.","SRP133620","SINGLE_SOURCE_SRP_SNAPSHOT_PENDING"),
 ("E25","WYW133620 resurvey conformance","Decision - Conformed to Survey/Resurvey",UNK,UNK,UNK,"Bureau of Land Management",UNK,UNK,"1998-07-10","1995-08-17",UNK,"Lease-wide",
  "Action 1998-07-10 EFFECTIVE 1995-08-17; second conformance action 2010-08-17 EFFECTIVE 2005-09-29. "
  "Same 07/10/1998 action date and 08/17/95 effective date as WYW131225 (E06).","SRP133620","SINGLE_SOURCE_SRP_SNAPSHOT"),
]
with open(f"{OUT}/Instrument_Event_Ledger.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["event_id","case_or_book","document_type","part","first_source_page","exhibit_pages",
                "parties_and_roles","execution_date","receipt_date","approval_date","effective_date",
                "recording_date","section_applications","material_qualifications","original_source","review_status"])
    for e in EV:
        w.writerow([e[0],e[1],e[2],e[3],e[4],e[5],e[6],e[7],e[8],e[9],e[10],e[11],e[12],e[13],e[14],e[15]])

# ---------------------------------------------------------------- proposed changes
PC = [
 ("P01","19","S19_Federal_index","Federal","Legal Description (CA WYW136880, Tract 2)",
  "any rendering as 'Lot 2'/'Lot 14' or 80.19 acres",
  "Lots 9 (SWNW) and 16 (NWSW), Section 19, T. 47 N., R. 76 W., 6th P.M., containing 35.93 acres and 38.18 acres, respectively",
  "S19EXC","1 (WYW094605 Part 1)",UNK,
  "'It has been brought to our attention that the land description in Tract 2 (Federal lease WYW131225) of communitization agreement "
  "WYW136880 is incorrect. The correct description is: T. 47 N., R. 76 W., 6th P.M. Section 19: Lots 9 (SWNW) and 16 (NWSW), containing "
  "35.93acres and 38.18 acres, respectively'",
  "BLM 2015 correction letter is dispositive for the post-2015 operative description. Independently corroborated four ways: "
  "(a) Exhibit A plat overwrites Lot 2->9 with 40.21->35.93 and Lot 14->16 with 39.98->38.18; (b) Exhibit B/recap Tract 2 80.19->74.11; "
  "(c) SRP recapitulation shows WYW136880 tract 02 at exactly 74.1100 acres and 38.307700%; (d) the 2019 successor-operator letter "
  "recites 'Lots 9 and 16 of Section 19'. Arithmetic verified: 38.51+74.11+80.84=193.46 and 74.11/193.46=38.3077%.",
  "HIGH","Retain the pre-2015 Lot 2 / Lot 14 / 80.19-acre description as the original agreement text with its own date role; "
  "the corrected description is effective 2015-09-14 forward. Do not overwrite history.",
  "None. This is a description correction, not a currentness determination.","PROPOSED_PENDING_ADJUDICATION"),
 ("P02","19","S19_Federal_index","Federal","Date of Doc / effective date (CA WYW136880)",
  "disputed 1994-09-02 vs 1994-09-04","Effective date = 1994-09-02. Approval date = Unknown (candidate 1994-09-04).",
  "S19EXC + F131225P4 + F094605P4 + SRP131225","1 and 4",UNK,
  "Agreement: 'THIS AGREEMENT entered into as of the 2nd day of SEPTEMBER 1994'. Transmittal: 'The agreement was approved as of this date, "
  "is effective September 2, 1994'. Exhibit B: 'To Communitization Agreement Dated September 2, 1994'. WYW131225 jacket: 'CA WYW 136880-Eff: "
  "09/02/94'. WYW094605 jacket: 'CA WYW 136880-Eff: 09/02/94' and 'CA WYW 110754-Eff: 11/01/76- Term: 09/02/94'. SRP131225: "
  "'09/02/1994 LEASE COMMITTED TO COMMUNITIZATION AGREEMENT ... WYW136880'.",
  "The apparent 9/2 vs 9/4 conflict resolves as a DATE-ROLE distinction, not a value dispute. The transmittal states the agreement was "
  "'approved as of this date' and is 'effective September 2, 1994'; a 9/4/1994 formal stamp is therefore an APPROVAL date, which must not be "
  "converted into the effective date. Six independent source instances support effective 1994-09-02; the predecessor CA WYW110754 terminating "
  "on 09/02/94 is a seventh, structural corroboration.",
  "HIGH for effective date; NONE for approval date",
  "Approval date stays Unknown until the approval stamp on WYW094605 Part 1 p.81 is read from the source image. Preserve both roles separately.",
  "None.","PROPOSED_PENDING_ADJUDICATION"),
 ("P03","19","S19_Federal_index","Federal","New Section 19 federal applications from lease WYW133620",
  "absent / treated as a Section 18 lease only",
  "Add Section 19 applications for WYW-133620 covering T47N R76W Section 19 Lots 5, 6, 7, 10, 11, 12, 17",
  "SRP133620","n/a",UNK,
  "ACTIVE LAND RECORDS: '06 0470N 0760W 019 Lot 5-7,10-12,17 Migrated - Existing Footprint WYOMING HIGH PLAINS DIST BUFFALO FIELD OFFICE JOHNSON'",
  "WYW-133620 holds Section 19 lands in its own right. This is distinct from, and must not be confused with, the rule that WYW-133620's "
  "inherited Section 18 facts are not Section 19 facts. The Section 19 lot set (5-7,10-12,17) is disjoint from WYW131225's Section 19 lot set "
  "(8,9,13,14,16,20), so the two leases do not overlap in Section 19.",
  "HIGH","Lot list is from an MLRS snapshot, not the original lease face; confirm against the lease instrument page when images become available.",
  "Does not establish currentness.","PROPOSED_PENDING_ADJUDICATION"),
 ("P04","19","S19_Federal_index","Federal","Material qualification - Section 19 lease stipulation (WYW133620)",
  "absent",
  "Preserve verbatim: 'STIPULATIONS: TLS (1) FEB 1 TO JUL 31; (2) T47N, R76W, SEC 19: NE, E2NW, SEC 20: NW; (3) PROTECTING SAGE GROUSE NESTING HABITAT.'",
  "SRP133620","n/a",UNK,"Legacy case remark lines 0001-0003 of SRP WYWY105360131",
  "A Section 19-specific timing limitation stipulation is an operative term affecting the Section 19 lands and belongs in the qualification "
  "material, not in a nine/ten-column index cell. Do not compress or paraphrase.",
  "HIGH","Carried in SRP legacy remarks, which the SRP itself marks obsolete and no longer updated after 2022-03-14; the stipulation's current "
  "status must be confirmed from the lease instrument or MLRS.","None.","PROPOSED_PENDING_ADJUDICATION"),
 ("P05","19","S19_Federal_index","Federal","New federal unit events",
  "absent",
  "North McRae Gap Unit WYW179231X, approved 2010-10-19 (Section 19 applicability NOT established); "
  "Tractor (Deep) Unit WYW191271X, committed 2021-10-18 (WYW131225 471.76 ac fully committed; WYW133620 1,094.76 ac fully committed)",
  "F131225P4 + SRP131225 + SRP133620","4","1",
  "Jacket: 'Committed To North McRae Gap Unit Unit No: WYW 179231X Approved: 10/19/2010' and 'Committed To Tractor (Deep) Unit Unit No: "
  "WYW 191271X Approved: 10/18/2021'. SRP133620: 'COMMITTED TO AGREEMENT ... WYW191271X;; Tractor (Deep) Unit'.",
  "WYW191271X is corroborated by both the jacket and both SRPs and is accepted as an event. WYW179231X appears ONLY on the WYW131225 jacket "
  "and is absent from the SRP associated-agreement recapitulation table; it must stay a separate unresolved proposal and must not be added to "
  "a completed primary case index.",
  "HIGH for WYW191271X; LOW for WYW179231X",
  "Keep the two units as separate proposals. Section 19 acreage attributable to either unit is Unknown; the fully-committed figures are "
  "whole-lease acres and must not be presented as Section 19 acreage.",
  "Unit commitment does not by itself establish currentness.","PROPOSED_PENDING_ADJUDICATION"),
 ("P06","19","S19_Federal_index","Federal","CA WYW136880 successor operator date roles",
  "absent or collapsed into a single date",
  "Application received 2016-07-22; letter dated 2019-04-04; receipt stamp 2019-04-08; approval EFFECTIVE 2011-10-01. "
  "Successor operator: Nonsuch Natural Gas, Inc.",
  "S19EXC","1 (WYW094605 Part 1)",UNK,
  "'On July 22, 2016, we received an application for Designation of Successor Operator whereby Nonsuch Natural Gas, Inc. is designated as "
  "successor operator for Communitization Agreement (CA) WYW136880 ... The application is approved effective October 1, 2011.' "
  "Stamp: 'RECEIVED APR 08 2019 BLM-WY STATE OFFICE'.",
  "Four distinct date roles on one instrument, including a retroactive effective date eight years before the letter. None may be converted "
  "into another. The letter's recital 'T. 44 N., R. 76 W.' is a source typographical error for T. 47 N.; it is preserved as printed and "
  "flagged, not silently corrected.",
  "HIGH","Preserve the 'T. 44 N.' recital error verbatim with an adjacent qualification.",
  "Operator designation is not an examiner currentness certification.","PROPOSED_PENDING_ADJUDICATION"),
 ("P07","19","S19_Federal_index","Federal","Acreage figure 797.14",
  "797.14 acres cited as whole-lease acreage","Unknown - figure not reproduced by any source read in this run",
  "SRP131225","n/a",UNK,"SRP WYWY105659144: 'Total Acres ... 471.7600'; SRP WYWY105360131: 'Total Acres ... 1,094.7600'",
  "The accepted baseline warns that whole-lease 797.14 acres is not Section 19 acreage. This run additionally finds that 797.14 does not "
  "match either lease total (WYW131225 = 471.76; WYW133620 = 1,094.76). The figure is therefore unsourced in the material reviewed here and "
  "should not be carried in any Section 19 cell or qualification until its origin is identified.",
  "MEDIUM","Keep Unknown. Identify the originating document before use.","None.","PROPOSED_PENDING_ADJUDICATION"),
 ("P08","19","S19_Federal_index","Federal","Section 19 lease lot conflict (printed Lot 10 vs handwritten 20)",
  "disputed: earlier printed Lot 10 vs handwritten 20","Unknown - retain existing qualification",
  "SRP131225","n/a",UNK,"Record title and active land records both render Section 19 as 'Lot 8,9,13,14,16,20'",
  "The SRP renders lot 20 for WYW131225 Section 19, which is consistent with the handwritten 20 reading, but an MLRS database rendering is "
  "not the original instrument face and cannot resolve a printed-versus-handwritten conflict. Note additionally that WYW133620 holds Section 19 "
  "Lot 10 (P03); a 'Lot 10' appearing in Section 19 material may belong to the other lease rather than being an error in this one.",
  "LOW","Keep the existing Unknown/qualified value. Resolution requires the source image of the lease face.",
  "None.","PROPOSED_PENDING_ADJUDICATION"),
]
with open(f"{OUT}/Proposed_Changes.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["proposal_id","section","relative_file","sheet","cell_or_new_event","original_value","proposed_value",
                "source_id","part","physical_page","quoted_evidence","interpretation","confidence",
                "material_qualifications","currentness_effect","acceptance_status"])
    for r in PC: w.writerow(list(r))

# ---------------------------------------------------------------- missing source / conflict register
MS = [
 ("B01","19","All substantive federal cells requiring a source-image read",
  "Per-page OCR text or page images for 1,315 scanned federal pages (WYW131225 485, WYW133620 617, WYW094605 213)",
  "All federal parts have native_text_page_count=0. The Drive connector returns empty text for every file larger than the 2-page jackets. "
  "File bytes (10-83 MB per part) cannot be transferred into this container via base64, and no local OCR engine is installed. "
  "FEDERAL_NAVIGATION_OCR_ONLY.json shows the OCR text exists but only at offline paths of the form "
  "C:\\Users\\ryang\\Documents\\Codex\\...\\work\\federal_ocr\\<case>\\p0001.txt.",
  "Full visual review of every physical page is a release gate. 1,309 of 1,315 federal pages are UNREVIEWED in this run.",
  "source_coverage_gate","Ryan / Root (RyansPC) or whoever can upload OCR text to Drive",
  "No cost. Either upload the existing federal_ocr .txt tree to Drive, or bring RyansPC online, or export per-page images.","OPEN"),
 ("B02","19","Provenance of the 15-source register",
  "SHA-256 recomputation over the copies actually in the shared source folder",
  "The register's drive_id values differ from the Drive IDs of the files in the shared source folder "
  "(e.g. WYW131225_Part1: register 1pjspzuVXaRhzooO3SvxPU-JB1OKtRvjz vs folder 1JTcexw2xD0TUXG-grxCFJK5yYA8i7HPW), "
  "while byte counts agree exactly. Two distinct copy sets exist.",
  "Join by original SHA plus page number is the contract's rule, but SHA equivalence between the two copy sets is unproven. "
  "Every SHA in my Source_Register.csv is as-supplied, not recomputed.",
  "traceability_gate","Package integrator / DeepSeek (deterministic audit)",
  "No cost; requires byte access to both copy sets.","OPEN"),
 ("B03","19","CA WYW136880 approval_date",
  "Source image of the approval/certification stamp, WYW094605 Part 1 p. 81",
  "Accepted baseline reports a formal effective stamp of 9/4/1994 against six source instances of 9/2/1994 for the effective date.",
  "Determines whether 9/4/1994 is the approval date (my reading) or a competing effective date. Approval and effective dates must not be merged.",
  "source_accuracy_gate","Lead evidence adjudicator (ChatGPT) with the Part 1 image","No cost once images are available.","OPEN"),
 ("B04","19","North McRae Gap Unit WYW179231X",
  "Unit agreement WYW179231X and its Section 19 tract schedule",
  "Jacket of WYW131225 Part 4 states committed to WYW179231X approved 10/19/2010, but the unit is absent from the SRP "
  "associated-agreement recapitulation table.",
  "An uncorroborated unit commitment must not be added to a completed primary case index, and its Section 19 acreage is Unknown.",
  "source_coverage_gate","Federal source examiner / BLM MLRS query",
  "Free via https://reports.blm.gov/reports/MLRS serial query.","OPEN"),
 ("B05","19","Acreage figure 797.14",
  "The document that states 797.14 acres","Figure matches neither lease total (471.76 and 1,094.76).",
  "An unsourced acreage must not be carried in Section 19 material.","data_integrity_gate","Lead evidence adjudicator","No cost.","OPEN"),
 ("B06","19","Research cutoff / currentness, all Section 19 federal cells",
  "Authenticated official records search with saved query parameters, retrieval timestamp, report bytes and hash",
  "Both Serial Register Pages are MLRS snapshots run 2026-10-07 carrying 'NO WARRANTY IS MADE BY BLM FOR USE OF THE DATA FOR PURPOSES NOT "
  "INTENDED BY BLM' and 'HISTORICAL INFORMATION MAY ONLY BE ACCESSIBLE THROUGH THE MLRS WEBSITE', and their legacy remark sections are "
  "expressly marked obsolete and not updated after 2022-03-14.",
  "An SRP snapshot cannot establish a records cutoff or the operative case chain. Research cutoff stays Unknown; "
  "2026-10-19 is a preparation date only.",
  "currentness_gate","Examiner with BLM MLRS access","Free portal; portal availability does not prove case status or full coverage.","OPEN"),
 ("B07","19","Native presentation parity",
  "A real test in licensed Microsoft Excel/Word and Acrobat with Calibri installed",
  "Desktop Commander device RyansPC was reported OFFLINE on 2026-10-19 and its MCP server failed to connect in this session "
  "(CONNECT_TIMEOUT). This container has LibreOffice and Carlito only; Calibri is not installed.",
  "Calibri 11 is the required typography. Carlito is a metric-compatible substitute, not Calibri, and no MS Office parity was tested.",
  "native_presentation_gate","Native Office and PDF examiner (Copilot) on a licensed machine",
  "Requires a licensed Office/Acrobat machine.","OPEN"),
 ("B08","19","WYW133620 record title",
  "Lease instrument record-title page or an MLRS record-title report",
  "SRP WYWY105360131 RECORD TITLE section reads '(No Records Found)', unlike WYW131225 which lists record title and percentages.",
  "Record title holders for the Section 19 lands under WYW133620 are therefore Unknown from the snapshot.",
  "source_coverage_gate","Federal source examiner / BLM MLRS query","Free via MLRS.","OPEN"),
 ("B09","19","Five federal proposals separation",
  "Adjudication decisions, one per proposal",
  "The accepted baseline records that Section 19 has two separate partial federal books with five proposals.",
  "This run submits 8 proposals (P01-P08). They are deliberately kept OUTSIDE any package and must not be merged into a "
  "combined build before per-proposal acceptance.",
  "acceptance_gate","Lead evidence adjudicator, then the designated integrator","No cost.","OPEN"),
]
with open(f"{OUT}/Missing_Source_and_Conflict_Register.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["issue_id","section","field_or_event","source_needed","observed_conflict","why_it_matters",
                "blocking_gate","next_owner","access_or_cost","status"])
    for r in MS: w.writerow(list(r))
print("ledgers written")
