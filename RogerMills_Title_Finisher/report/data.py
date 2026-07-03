# -*- coding: utf-8 -*-
"""Structured data for the Section 31-12N-24W ownership report.
All figures traced to the 7-3-2026 NHE working workbook, the OGL register,
the OCR'd 519-instrument county index, and the examiner ownership report.
Nothing here is fabricated; open balances and unconfirmed items are marked."""

META = dict(
    section="31", township="12N", range="24W", county="Roger Mills", state="Oklahoma",
    prospect="25-004", gross="637.42", tracts=10,
    report_date="July 3, 2026", examiner="RG",
    last_entry="Instr. 2026-003315 · Bk 2704/142 (filed 6/5/2026)",
    well="Alexander 1-31", api="35-129-22925", formation="Cherokee",
    base_leases=63, top_leases=6, instruments=519,
)

# Section plat: 16 quarter-quarters (4x4), north up. Tract assignment per corrected PLAT.
# row 0 = north tier. Each cell: (label, tract, note)
PLAT = [
    [("NW/4 NW/4","5","Gov Lots"),("NE/4 NW/4","4",""),("NW/4 NE/4","1",""),("NE/4 NE/4","1","")],
    [("SW/4 NW/4","5","Gov Lots"),("SE/4 NW/4","4",""),("SW/4 NE/4","2",""),("SE/4 NE/4","3","")],
    [("NW/4 SW/4","6","M&B strip"),("NE/4 SW/4","7",""),("NW/4 SE/4","2",""),("NE/4 SE/4","10","")],
    [("SW/4 SW/4","6","M&B strip"),("SE/4 SW/4","5",""),("SW/4 SE/4","2",""),("SE/4 SE/4","2","")],
]

# Tract roster
TRACTS = [
    dict(n=1, legal="N/2 NE/4", gross=80.00, status="reconciled"),
    dict(n=2, legal="SW/4 NE/4 + NW/4 SE/4 + S/2 SE/4", gross=160.00, status="reconciled"),
    dict(n=3, legal="SE/4 NE/4", gross=40.00, status="partial"),
    dict(n=4, legal="E/2 NW/4", gross=80.00, status="partial"),
    dict(n=5, legal="SE/4 SW/4 + residual in Gov Lots 1 & 2", gross=38.28, status="partial"),
    dict(n=6, legal="S 51 ac of the W. 18.20-chain metes-and-bounds strip (W/2 NW/4 & N/2 NW/4 SW/4)", gross=51.00, status="estate"),
    dict(n=7, legal="NE/4 SW/4", gross=40.00, status="partial"),
    dict(n=8, legal="S 32.80 ac of the W. 18.20-chain metes-and-bounds strip", gross=32.80, status="estate"),
    dict(n=9, legal="Gov Lot 4 + S/2 Gov Lot 3", gross=75.34, status="succession"),
    dict(n=10, legal="NE/4 SE/4", gross=40.00, status="partial"),
]

# Examiner-distilled current mineral ownership by tract (identified record owners;
# open balances shown explicitly, never distributed). Source: 7-3 ownership report,
# cross-checked to reconciled tract grids. base = base OGL #, top = Silver Oak top OGL #.
OWNERS = {
 1:[("Gena W. Moore (a/k/a Gena Mitchell Williams)",40.00,"4","66","3/16"),
    ("Mitchell-Buonaccorsi Living Trust",20.00,"1","64","3/16"),
    ("Ronald Paul Dold",10.00,"2","65","3/16"),
    ("Kevin Warner Johnson Trust",10.00,"24","69","3/16")],
 3:[("Mark Ashley Daigle Trust",7.69,"24","68","3/16"),
    ("Gena W. Moore",5.39,"4","66","3/16"),
    ("Mitchell-Buonaccorsi Living Trust",5.39,"1","64","3/16"),
    ("Keri Lee Daigle Tucker Trust",5.39,"24","67","3/16"),
    ("Ronald Paul Dold",5.38,"2","65","3/16"),
    ("Kevin Warner Johnson Trust",5.38,"24","69","3/16"),
    ("Carrie Leeann Mitchell",5.38,"1, 2","—","3/16")],
 8:[("Ella Pearl Kirk (estate / heirship to verify)",32.80,"62","—","3/16")],
 9:[("Ronald Paul Dold (Nancy Susan Mitchell successor chain; AoH 2026-002509, Bk 2697/517)",75.34,"2","65","3/16")],
 2:[("Paul M. Bain GST Tax-Exempt Trust",5.41,"HBP","—","3/16"),
    ("Anna T. Bain Gibson",4.44,"56/57","—","3/16"),
    ("Michael L. / William C. / Paul M. Bain GST Trusts (aggregate)",16.23,"HBP","—","3/16"),
    ("Hans W. & Tim E. Jensen (aggregate)",16.53,"51/52","—","3/16"),
    ("Dow C. & Edris O. Bain, Trustees",9.74,"6","—","3/16"),
    ("Cardinal Land Company, LLC",1.50,"HBP","—","3/16"),
    ("Royfin Natural Gas, LLC",1.29,"HBP","—","3/16"),
    ("Del Monte Royalty Partners, LLC",0.75,"HBP","—","3/16"),
    ("OKKI Industries, LLC",0.75,"HBP","—","3/16"),
    ("William A. & Isa May Smith Family Rev. Trust",0.75,"14","—","1/4"),
    ("Longreach Energy 2, LLC",0.55,"HBP","—","3/16"),
    ("Eric Jansen",0.40,"HBP","—","3/16"),
    ("Brian Herman Kortright",0.20,"HBP","—","3/16")],
 4:[("Dustin Deal, LLC",2.10,"HBP","—","3/16"),
    ("Calvin Wayne Kirk",2.10,"HBP","—","3/16"),
    ("William / Kathy Bryant",2.10,"HBP","—","3/16"),
    ("Ronald Paul Dold → Silver Oak",2.10,"2","65","3/16")],
 5:[("William / Kathy Bryant",0.74,"HBP","—","3/16")],
 6:[("Calvin Wayne Kirk (MD 2017-000951, Bk 2365/338)",2.20,"HBP","—","3/16")],
 7:[("Pine Tree Energy Partners, LLC (Clint Roy Kirk → J&A Minerals → Pine Tree)",1.14,"—","—","—"),
    ("Gene G. Williams",1.14,"HBP","—","3/16"),
    ("Williams heirs",0.87,"HBP","64–69","3/16")],
 10:[("Keri Lee Daigle Tucker Trust",0.33,"24","67","3/16"),
    ("Mark Ashley Daigle Trust",0.33,"24","68","3/16"),
    ("Kevin Warner Johnson Trust",0.33,"24","69","3/16")],
}

# Descriptive label for each tract's computed open/unreconciled remainder
# (= gross - sum of identified owners above). Never hand-typed; always footed.
OPEN_NOTES = {
 2:"Open / unreconciled balance — needs source images",
 4:"Open / unreconciled balance — candidate MD 2022-000185, Psi Lke → Cummins/Eagle Owl",
 5:"Open / unreconciled balance — gov-lot / exception allocation",
 6:"Ella Pearl Kirk estate / heirs — retained balance (probate needed)",
 7:"Open / unreconciled balance",
 10:"Open / unreconciled balance",
}

# Silver Oak 2026 top-lease sweep — highest-confidence current-owner signal
TOP = [
 ("64","James Gerard Buonaccorsi — Mitchell-Buonaccorsi Living Trust (Carrie Leeann Mitchell, Trustee)","2693/337","2-23-2026","2-22-2029","3 yr"),
 ("65","Ronald Paul Dold","2697/524","3-31-2026","3-30-2029","3 yr"),
 ("66","Gena W. Moore, a/k/a Gena Mitchell Williams","2702/505","2-11-2026","2-10-2031","5 yr"),
 ("67","Keri Lee Daigle Tucker Trust","2697/520","2-17-2026","2-17-2031","5 yr"),
 ("68","Mark Ashley Daigle Trust","2693/349","2-23-2026","2-23-2031","5 yr"),
 ("69","Kevin Warner Johnson Trust","2693/345","2-27-2026","2-27-2031","5 yr"),
]

# Wellbore / working-interest chain (title-derived, through 5-4-2026)
WI_CHAIN = ["R. Michael Lortz","Lariat Petroleum","Ocean Energy","Devon Energy",
    "Chesapeake / EOG era","FourPoint / Unbridled","Presidio / MidCon",
    "Martin's Empire, LLC","Stride Bank, N.A., Trustee (Umbrella Trust)"]

# Source-in gaps still highlighted — pull each grantor's vesting instrument (pre-2000 roots)
GAPS = [
 ("H. L. & Myrtie Rowley","Deed 1916-000332, Bk D22/248","1916 root of title"),
 ("Lawrence E. & Ethel Shotwell","QCD 1931-000994, Bk D43/608","1931 root"),
 ("Thomas O. & Flora E. Hambrook","Deed 1931-000573, Bk D41/447","1931 root"),
 ("Elvin J. & Dorothy Jean Ridling","WD 1953-000493, Bk D67/154","1953 root"),
 ("L. E. & Veronica Thurman","MD 1974-001639, Bk 163/565","1974 root (2014 same-surname trust ≠ back-fill)"),
 ("Elmo W. & Freeda Kirk","WD 1976-003251, Bk 197/116","1976 root"),
 ("Billy N. Bein","MD 1987-005625, Bk 913/261","pre-index"),
 ("Alfred William Standiford","MD 1989-001220, Bk 1038/219","1989 conveyance predates 1994 decree"),
 ("Federal Deposit Insurance Corporation","Mineral QCD 1990-001925, Bk 1126/98","FDIC receivership"),
 ("Charles O. Burckhalter","QCD 1990-004213, Bk 1151/107","pre-index"),
 ("Eula G. Cross","QCD 1997-006370, Bk 1510/566","pre-index"),
 ("Oleta Florene Flanagan (f/k/a Stewart)","MD 2002-003563, Bk 1688/374","name-change link"),
 ("Sandra Lorraine York","OGL 2004-000880, Bk 1737/580","2005 decree postdates 2004 lease"),
 ("Estate of Barbara Fasken","Blanket Deed 2005-000347, Bk 1775/296","estate"),
 ("Molly Devenas","Ratification 2005-003939, Bk 1793/501","ratification only"),
 ("John William Bain","MD 2005-001909, Bk 1783/306","Bain family"),
 ("Leona I. De Grande","OGL 2005-004938, Bk 1798/573","lessor vesting"),
 ("Joseph A. & Doris Bain","MD 2012-002930, Bk 2131/599","Bain family"),
 ("Mary Ellen Silverberg (a/k/a Sitzmann)","MD 2013-006502, Bk 2223/307","a/k/a link"),
 ("Jon N. Wilkerson","MD 2017-001880, Bk 2376/100","modern buyer"),
 ("Payday Holdings, LLC","MD & Assignment 2020-001708, Bk 2453/452","entity vesting"),
 ("Onigbe Consulting, LLC","Conveyance 2024-007198, Bk 2599/463","entity vesting"),
 ("Jesse Joe Newell (a/k/a Jesse J. Newell)","WD 2025-003963, Bk 2638/58","recent"),
]

# Source-in gaps resolved this engagement (documented from index + Runsheet cross-ref)
RESOLVED = [
 ("Hazel A. Hamilton","MD 1978-002576, Bk 237/367"),
 ("Billy W. Bain","MD 1978-002585 Bk 237/376; Trust Agmt 1983-001668"),
 ("Gregory J. Winneke","MD 1982-011143, Bk 480/71 (conf. 2012/2019)"),
 ("Bary Ellen Sitzman","MD 1987-005625, Bk 913/261"),
 ("Cimarron Mineral Corporation","Assignment 1987-003826, Bk 897/244"),
 ("Koala Production Company","MD 2004-005738/739, Bk 1764/344-345"),
 ("Glenn D. Mitchel","MD 1949-001867 Bk D63/97; Order 1990-006747"),
 ("Lola F. Richards","MD 1999-003363, Bk 1583/391 (Opal Fuchs estate)"),
 ("Keri Lee Daigle Trust","MD 2011-005695 Bk 2092/134 & 2011-008366"),
 ("Mitchell-Buonaccorsi Living Trust","MD 2024-007338, Bk 2600/472"),
 ("Michael Best et al / Crouse Family Trust","Order 2001-000618, Bk 1634/353"),
]

# Instrument columns still needing the conveyed fraction (pull image to read granting language)
FRACTION_GAPS = {
 "Tract 2":"2005-007117, -007116, -007119, -007120 (MD, confirm); 2013-006585, 2025-002463 (empty); 2025-002464 (confirm)",
 "Tract 3":"1993-000918 (Probate, empty); 2002-004595 (MD, empty)",
 "Tract 4":"1982-007158; 2002-004595; 2004-005738; 2004-005739; 2008-006536 (all empty)",
 "Tract 5":"1982-007158; 1992-003373; 1993-000918; 2004-005738/739; 2008-006536; 2005-004793; 2005-005251; 2006-000153; 2006-000870; 2013-001724; 2013-006585; 2025-003963 (all empty)",
 "Tract 7":"1992-003373 (confirm); 1993-000918 (empty); 2002-004595 (confirm); 2013-006585 (confirm)",
 "Tract 10":"2002-004595; 2011-005695; 2011-005926; 2013-001272; 2015-003022; 2015-003023; 2017-000951; 2021-001486 (all empty)",
}

# Depth severances / non-standard royalty leases pulled from the OGL register
DEPTH = [
 ("13","Jesse W. Fuchs → N/G Discovery","1/4","All formations 100 ft below deepest depth drilled released at end of primary term"),
 ("14","Isa May Smith → N/G Discovery","1/4","Same 100-ft-below-deepest depth limitation"),
 ("15","Raymond M. Fuchs → N/G Discovery","3/16","Same 100-ft-below-deepest depth limitation"),
 ("16","Mark J. Fuchs → N/G Discovery","1/4","Same 100-ft-below-deepest depth limitation"),
 ("25","Linda / Roger Klopfenstein → Chesapeake","3/16","Terminates below 100 ft under deepest formation after primary term"),
 ("29","Leona I. De Grande → EOG","3/16","Limited from surface to stratigraphic equivalent of 20,000 ft"),
 ("30–34","Bain family (Donald, Charlotte, Melvin, Marilyn) → EOG","3/16","Limited to stratigraphic equivalent of 20,000 ft"),
 ("37","Peggy J. Brawner → EOG","3/16","Limited to 20,000 ft; 2-yr term"),
 ("46","Eddie Tom Lakey → Jess Harris III","3/16","M&B strip; 100-ft-below-deepest release on extension"),
 ("47","Shawn S. Walters → Jess Harris III","3/16","100-ft-below-deepest release; 2-yr term"),
]
