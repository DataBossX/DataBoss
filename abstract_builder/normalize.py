"""Field normalizers for the operator's standing formatting notes.

Every normalizer returns (value, notes) where notes is a list of audit strings. A normalizer NEVER invents
a value: when the input cannot be proved into the house format the value is blanked (or kept verbatim where
the notes say to preserve) and a hold note is emitted so the QA register can carry it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

UNKNOWN_TOKENS = {"unknown", "unk", "n/a", "na", "none", "null", "?", "--", "-", "tbd", "not stated", "not shown",
                  "no grantee named", "no grantor named", "unknown (qualified)"}


def is_blank(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    return False


def is_unknown(v: Any) -> bool:
    return isinstance(v, str) and v.strip().strip(".").lower() in UNKNOWN_TOKENS


# ----------------------------------------------------------------------------- Doc No
def norm_doc_no(v: Any) -> tuple[Any, list[str]]:
    """Doc No stored as a real integer; source leading zeros dropped. Non-numeric identifiers are kept
    verbatim (never coerced) and logged; Unknown/blank -> blank + log."""
    if is_blank(v):
        return None, ["DOC_NO_BLANK"]
    if is_unknown(v):
        return None, [f"DOC_NO_UNKNOWN_BLANKED:{v!r}"]
    if isinstance(v, bool):
        return None, [f"DOC_NO_BAD_TYPE:{v!r}"]
    if isinstance(v, (int,)):
        return int(v), []
    if isinstance(v, float):
        if v.is_integer():
            return int(v), []
        return None, [f"DOC_NO_NON_INTEGER_FLOAT_BLANKED:{v!r}"]
    s = str(v).strip().replace(",", "")
    s = re.sub(r"^#", "", s)
    if re.fullmatch(r"\d+", s):
        notes = []
        if s.startswith("0") and len(s) > 1:
            notes.append(f"DOC_NO_LEADING_ZEROS_DROPPED:{s}")
        return int(s), notes
    return s, [f"DOC_NO_NON_NUMERIC_KEPT_TEXT:{s!r}"]


# ----------------------------------------------------------------------------- Book-Page
_BP_SPLIT = re.compile(r"\s*(?:-|–|—|/|\bthrough\b|\bthru\b|\bto\b|,)\s*", re.I)
_MINING_INLINE = re.compile(r"\s*\(mining\)", re.I)
_MINING_SUFFIX = re.compile(r"\s*\((mining|r/w|misc|deed|lease)\)\s*$", re.I)


def norm_book_page(v: Any) -> tuple[Any, list[str]]:
    """0399-0142 pattern. Numeric books/folios zero-padded to 4; spans joined with '-'. Alpha book series are
    preserved (A060, 67MR, 86A70, R/W32); a '(Mining)' designation is dropped from the display (owner override); '86A-83-0071' style is collapsed to '86A83-0071'."""
    if is_blank(v):
        return None, ["BOOK_PAGE_BLANK"]
    if is_unknown(v):
        return None, [f"BOOK_PAGE_UNKNOWN_BLANKED:{v!r}"]
    raw = str(v).strip()
    notes: list[str] = []
    suffix = ""
    if _MINING_INLINE.search(raw):
        raw = _MINING_INLINE.sub("", raw)
        notes.append(f"BOOK_PAGE_MINING_DESIGNATION_DROPPED:{v!r}")
    m = _MINING_SUFFIX.search(raw)
    if m:
        suffix = " " + m.group(0).strip()
        raw = raw[: m.start()].strip()
    raw = re.sub(r"(?i)^R/?W(?=\d)", "R/W", raw)          # right-of-way series: RW32 -> R/W32 (authentic series keeps the slash)
    raw = raw.replace("R/W", "\x01").replace("r/w", "\x01")
    parens = re.findall(r"\s*\([^)]*\)", raw)
    raw = re.sub(r"\s*\([^)]*\)", "\x02", raw)
    raw = re.sub(r"(?i)^(book|bk\.?)\s*", "", raw)
    raw = re.sub(r"(?i)\s*(page|pg\.?|p\.)\s*", "-", raw)
    toks = [t for t in _BP_SPLIT.split(raw) if t]
    if len(toks) < 2:
        return raw + suffix, [f"BOOK_PAGE_UNPARSED_KEPT:{v!r}"]
    first = toks[0]
    rest = toks[1:]
    # alpha-series book split across tokens: '86A' '83' '0071' -> book '86A83'
    if re.search(r"[A-Za-z]", first) and len(rest) >= 2 and rest[0].isdigit() and not first.endswith("R/W"):
        if re.fullmatch(r"\d+[A-Za-z]+", first):
            first = first + rest[0]
            rest = rest[1:]
            notes.append("BOOK_PAGE_ALPHA_SERIES_JOINED")
    if first.isdigit():
        book = first.zfill(4)
    else:
        book = first.replace(" ", "")
    pages = []
    for t in rest:
        pages.append(t.zfill(4) if t.isdigit() else t)
    out = book + "-" + "-".join(pages) + suffix
    out = out.replace("\x01", "R/W")
    for ptxt in parens:
        out = out.replace("\x02", " " + ptxt.strip(), 1)
    if out != str(v).strip():
        notes.append(f"BOOK_PAGE_REFORMATTED:{v!r}->{out!r}")
    return out, notes


# ----------------------------------------------------------------------------- Dates
_DATE_FORMATS = ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%B %d %Y",
                 "%Y/%m/%d", "%m.%d.%Y"]
_YEAR_ONLY = re.compile(r"^\s*(\d{4})\s*$")
_MONTH_YEAR = re.compile(r"^\s*(\d{1,2})[/-](\d{4})\s*$|^\s*[A-Za-z]+\s+\d{4}\s*$")


def norm_date(v: Any) -> tuple[date | None, list[str]]:
    """Real date value, displayed m/d/yyyy. Year-only or month-year is NEVER expanded to a date (blank + log)."""
    if is_blank(v):
        return None, ["DATE_BLANK"]
    if is_unknown(v):
        return None, [f"DATE_UNKNOWN_BLANKED:{v!r}"]
    if isinstance(v, datetime):
        return v.date(), []
    if isinstance(v, date):
        return v, []
    s = str(v).strip()
    if _YEAR_ONLY.match(s):
        return None, [f"DATE_YEAR_ONLY_BLANKED:{s!r}"]
    if _MONTH_YEAR.match(s):
        return None, [f"DATE_MONTH_YEAR_BLANKED:{s!r}"]
    s2 = re.sub(r"\s+", " ", s)
    for fmt in _DATE_FORMATS:
        try:
            d = datetime.strptime(s2, fmt).date()
            if d.year < 100:
                return None, [f"DATE_AMBIGUOUS_CENTURY_BLANKED:{s!r}"]
            return d, []
        except ValueError:
            continue
    return None, [f"DATE_UNPARSED_BLANKED:{s!r}"]


# ----------------------------------------------------------------------------- Parties
_STRIP_ROLE = re.compile(
    r"\s*\((?:releasing party|recorder header|reciprocal|affiant|affiants?|mortgagee|mortgagor[^)]*|shown[^)]*|"
    r"alleged debtor[^)]*|working[- ]interest subscriber|debtor|secured party|lessor|lessee|assignor|assignee|"
    r"grantor|grantee|lender|borrower|trustee|beneficiary|claimant|owner|surface owner|et ?al\.?|etal|"
    r"on behalf of[^)]*|as [^)]*|by [^)]*|per [^)]*|see [^)]*|from [^)]*|to [^)]*)\)\s*", re.I)
_KEEP_PARENS = re.compile(r"\((?:operator|non-operator|formerly [^)]*)\)", re.I)
_LLC = re.compile(r"\b(L\.?\s?L\.?\s?C\.?)(?=[\s,;)]|$)", re.I)
_LLC_COMMA = re.compile(r"(?<![,])\s+LLC\b")
_LLLP = re.compile(r"\bL\.?L\.?L\.?P\.?\b", re.I)
_LLP = re.compile(r"\bL\.?L\.?P\.?\b", re.I)
_LP = re.compile(r"\bL\.?P\.?\b")
_ROLE_TAIL = re.compile(r",\s*(?:each|et ?al\.?|etal|debtor|secured party(?: authorizing (?:termination|amendment))?|grantors?|grantees?|mortgagee|mortgagor|individually)\s*$", re.I)
_CAPACITY_TAILS = re.compile(r",?\s*(?:as joint tenants[^,]*|with rights? of survivorship|for the benefit of [^,]+|"
                             r"on behalf of [^,]+|also identified as [^,]+(?:,[^,]+)?|debtor|each as [^,]+|"
                             r"in Schedule [A-Z0-9]+)", re.I)
_EXECUTED_BY = re.compile(r",?\s*(?:executed|signed|acting) by [^,]+(?:,[^,]+)*?(?: on behalf of the company)?\.?$", re.I)


def _clean_party(p: str) -> tuple[str, list[str]]:
    notes = []
    s = p.strip().strip(",").strip()
    # preserve legally material parentheticals by masking
    keeps = _KEEP_PARENS.findall(s)
    masked = _KEEP_PARENS.sub("\x00", s)
    s2 = _STRIP_ROLE.sub(" ", masked)
    if s2 != masked:
        notes.append(f"PARTY_ROLE_NOTE_STRIPPED:{p.strip()!r}")
    for k in keeps:
        s2 = s2.replace("\x00", k, 1)
    s3 = _EXECUTED_BY.sub("", s2)
    if s3 != s2:
        notes.append("PARTY_SIGNATORY_NOTE_STRIPPED")
    s3 = _ROLE_TAIL.sub("", s3)
    s3b = _CAPACITY_TAILS.sub("", s3)
    if s3b != s3:
        notes.append("PARTY_CAPACITY_NOTE_STRIPPED")
    s3 = s3b
    s3 = re.sub(r",?\s*also known as\s+", " a/k/a ", s3, flags=re.I)
    s4 = _LLC.sub("LLC", s3)
    s4 = _LLLP.sub("LLLP", s4)
    s4 = _LLP.sub("LLP", s4)
    s4 = _LLC_COMMA.sub(", LLC", s4)
    s4 = re.sub(r"\s+,", ",", s4)
    s4 = re.sub(r"\s{2,}", " ", s4).strip().strip(",").strip()
    s4 = s4.replace("H/W", "HW")
    if s4 != s3.strip().strip(",").strip():
        notes.append("PARTY_ENTITY_STYLE_NORMALIZED")
    return s4, notes


def norm_parties(v: Any) -> tuple[str | None, list[str]]:
    """Each distinct party comma-terminated with a real newline between parties, last party without a
    trailing comma. Entity suffixes rendered ', LLC'. Non-substantive role/provenance notes stripped."""
    if is_blank(v):
        return None, ["PARTY_BLANK"]
    if is_unknown(v):
        return None, [f"PARTY_UNKNOWN_BLANKED:{v!r}"]
    s = str(v).replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace(";", "\n")
    parts = [p for p in (x.strip() for x in s.split("\n")) if p]
    notes: list[str] = []
    cleaned = []
    for p in parts:
        c, n = _clean_party(p)
        notes += n
        if c and not is_unknown(c):
            cleaned.append(c)
    if not cleaned:
        return None, notes + [f"PARTY_EMPTY_AFTER_CLEAN:{v!r}"]
    out = ",\n".join(cleaned)
    return out, notes


# ----------------------------------------------------------------------------- Legals
_STRIP_LEGAL_NOTES = [
    re.compile(r",?\s*(?:johnson|campbell|sheridan|natrona|converse)\s+county(?:,\s*wyoming)?", re.I),
    re.compile(r",?\s*wyoming\b", re.I),
    re.compile(r",?\s*6th\s*P\.?M\.?", re.I),
    re.compile(r"\s*\((?:[^()]*(?:acre|ac\.|depth|formation|below|above|from the surface|lease|unit|claim|well|"
               r"sec\.?|insofar|limited to|only as to|down to|base of|top of|pa\b)[^()]*)\)", re.I),
    re.compile(r",?\s*(?:containing|cont\.)\s+[\d.,]+\s*(?:acres?|ac\.?)[^,;]*", re.I),
    re.compile(r",?\s*[\d.,]+\s*(?:acres?|ac\.)\b[^,;]*", re.I),
    re.compile(r",?\s*(?:insofar|limited|only)\s+(?:as|to)\b[^;]*", re.I),
    re.compile(r",?\s*(?:from the surface|below|above|down to|to the base|to the top|depths?|formations?)\b[^;]*", re.I),
    re.compile(r",?\s*well locations?\b[^;]*", re.I),
]
_ALIQUOT_MAP = [
    (re.compile(r"(?<![A-Za-z/])([NSEW]{1,2})\s*1/2(?![\d/])"), r"\1/2"),
    (re.compile(r"(?<![A-Za-z/])([NSEW]{2})\s*1/4(?![\d/])"), r"\1/4"),
    (re.compile(r"(?<![A-Za-z/])([NSEW]{2})4(?![\d/])"), r"\1/4"),
    (re.compile(r"(?<![A-Za-z/])([NSEW]{1,2})2(?![\d/])"), r"\1/2"),
    (re.compile(r"([NSEW]{1,2}/[24])(?=[NSEW]{1,2}/[24])"), r"\1 "),
]
_AOL = re.compile(r",?\s*\b(?:aol|a\.o\.l\.|and other lands|also other lands|et al lands|and others)\b\.?\s*$", re.I)
_SEC_FORMS = [
    # 'Section 19, T47N-R76W' / 'Sec. 19, T47N, R76W' / 'Section 19 of Township 47 North, Range 76 West'
    re.compile(r"(?:section|sec\.?)\s*(\d{1,2}),?\s*(?:of\s*)?(?:T|Township\s*)(\d{1,3})\s*N(?:orth)?[,\s-]*(?:R|Range\s*)(\d{1,3})\s*W(?:est)?", re.I),
    # '19-47N-76W'
    re.compile(r"\b(\d{1,2})-(\d{1,3})N-(\d{1,3})W\b", re.I),
    # 'T47N-R76W Section 19' / 'T47N R76W Sec 19'
    re.compile(r"(?:T|Township\s*)(\d{1,3})\s*N(?:orth)?[,\s-]*(?:R|Range\s*)(\d{1,3})\s*W(?:est)?[,:\s]*(?:section|sec\.?)\s*(\d{1,2})", re.I),
]


def _extract_str(s: str) -> tuple[tuple[int, int, int] | None, str]:
    for i, rx in enumerate(_SEC_FORMS):
        m = rx.search(s)
        if m:
            if i == 2:
                twp, rge, sec = m.group(1), m.group(2), m.group(3)
            else:
                sec, twp, rge = m.group(1), m.group(2), m.group(3)
            rest = (s[: m.start()] + " " + s[m.end():]).strip()
            return (int(sec), int(twp), int(rge)), rest
    return None, s


_LOT_RANGE = re.compile(r"(\d+)\s*[\u2013\u2014-]\s*(\d+)")


def _expand_lot_ranges(call: str) -> tuple[str, list[str]]:
    """'Lots 5-8' -> 'Lots 5, 6, 7, 8' (house format enumerates lots; no dash punctuation in client text)."""
    if "lot" not in call.lower():
        return call, []
    def rep(m: re.Match) -> str:
        a, b = int(m.group(1)), int(m.group(2))
        return ", ".join(str(i) for i in range(a, b + 1)) if a < b <= a + 60 else m.group(0)
    out = _LOT_RANGE.sub(rep, call)
    return out, ([f"LEGAL_LOT_RANGE_EXPANDED:{call!r}"] if out != call else [])


def norm_legal(v: Any, section: int | None = None, twp: int | None = None, rge: int | None = None,
               blm_casewide: bool = False) -> tuple[str | None, list[str]]:
    """House format '<CALL> of <SEC>-<TWP>N-<RGE>W' plus ', aol' when other lands are covered. Strips county, state,
    6th P.M., depth/formation/lease/acreage notes. If the call cannot be proved into house format the cleaned
    text is kept and a LEGAL_FORMAT_REVIEW hold is logged (never invents an aliquot or section)."""
    if is_blank(v):
        return None, ["LEGAL_BLANK"]
    if is_unknown(v):
        return None, [f"LEGAL_UNKNOWN_BLANKED:{v!r}"]
    raw = str(v).replace("\r\n", "\n").strip()
    if raw.strip().lower() == "outside lands only":
        return "outside lands only", []
    notes: list[str] = []
    lines = [ln for ln in (x.strip() for x in raw.split("\n")) if ln]
    out_lines = []
    aol_any = False
    for ln in lines:
        s = ln
        if _AOL.search(s):
            aol_any = True
            s = _AOL.sub("", s)
        s0 = s
        for rx in _STRIP_LEGAL_NOTES:
            s = rx.sub("", s)
        if s != s0:
            notes.append(f"LEGAL_NOTE_STRIPPED:{ln!r}")
        for rx, rep in _ALIQUOT_MAP:
            s = rx.sub(rep, s)
        s = re.sub(r"\s{2,}", " ", s).strip(" ,;")
        key, rest = _extract_str(s)
        if key is None and section and twp and rge:
            key = (section, twp, rge)
            rest = s
            notes.append("LEGAL_STR_ASSUMED_FROM_SECTION_CONTEXT")
        if key is None:
            notes.append(f"LEGAL_FORMAT_REVIEW:{ln!r}")
            out_lines.append(s)
            continue
        sec, t, r = key
        call = re.sub(r"^\s*(?:of|in|,)\s*", "", rest).strip(" ,;")
        call = re.sub(r"\s*,?\s*(?:of|in)\s*$", "", call).strip(" ,;")
        call = re.sub(r"\s{2,}", " ", call)
        call = re.sub(r"\bLots?\s+", "Lots ", call, flags=re.I)
        call = re.sub(r"(?<=\d),(?=\d)", ", ", call)
        call, rn = _expand_lot_ranges(call); notes += rn
        if not call or call.lower() in {"all", "all of"}:
            call = "All"
        out_lines.append(f"{call} of {sec}-{t}N-{r}W")
    if not out_lines:
        return None, notes + [f"LEGAL_EMPTY_AFTER_CLEAN:{v!r}"]
    if blm_casewide:
        out = ",\n".join(out_lines)
    else:
        out = ",\n".join(out_lines)
    if aol_any:
        out += ", aol"
    if out != raw:
        notes.append(f"LEGAL_REFORMATTED:{raw!r}->{out!r}")
    return out, notes


# ----------------------------------------------------------------------------- Comments
def norm_comment(v: Any) -> tuple[str | None, list[str]]:
    """Blank, or exactly 'missing image'. Any other text is moved to the QA log."""
    if is_blank(v):
        return None, []
    s = str(v).strip()
    if s.lower().rstrip(".") in {"missing image", "missing images", "image missing", "no image"}:
        return "missing image", [] if s == "missing image" else [f"COMMENT_NORMALIZED:{s!r}"]
    return None, [f"COMMENT_MOVED_TO_QA:{s!r}"]


def norm_int(v: Any, label: str) -> tuple[int | None, list[str]]:
    """Page / Part: single positive integer or blank (unnumbered part stays blank, never invented)."""
    if is_blank(v):
        return None, [f"{label}_BLANK"]
    if is_unknown(v):
        return None, [f"{label}_UNKNOWN_BLANKED:{v!r}"]
    if isinstance(v, bool):
        return None, [f"{label}_BAD_TYPE:{v!r}"]
    if isinstance(v, (int, float)):
        if float(v).is_integer() and v > 0:
            return int(v), []
        return None, [f"{label}_NON_INTEGER_BLANKED:{v!r}"]
    s = str(v).strip()
    m = re.fullmatch(r"(?:p\.?|page|part)?\s*(\d+)", s, re.I)
    if m:
        return int(m.group(1)), ([] if s.isdigit() else [f"{label}_PREFIX_STRIPPED:{s!r}"])
    s_np = re.sub(r"^(?:pp?\.?|pages?|part)\s*", "", s, flags=re.I)
    m = re.match(r"(\d+)\s*(?:-|–|to|,)\s*\d+", s_np)
    if m:
        return int(m.group(1)), [f"{label}_RANGE_FIRST_PAGE_KEPT:{s!r}"]
    return None, [f"{label}_UNPARSED_BLANKED:{s!r}"]


def norm_doc_type(v: Any) -> tuple[str | None, list[str]]:
    if is_blank(v):
        return None, ["DOC_TYPE_BLANK"]
    if is_unknown(v):
        return None, [f"DOC_TYPE_UNKNOWN_BLANKED:{v!r}"]
    s = re.sub(r"\s{2,}", " ", str(v).strip())
    notes = []
    s2 = re.sub(r"\s*(?:\u2014|\u2013|--)\s*", ": ", s)
    if s2 != s:
        s = s2
        notes.append("DOC_TYPE_DASH_PUNCTUATION_REPLACED")
    if s.isupper() and len(s) > 4:
        s = s.title().replace(" Of ", " of ").replace(" And ", " and ").replace(" To ", " to ")
        notes.append("DOC_TYPE_CASE_NORMALIZED")
    return s, notes


# ----------------------------------------------------------------------------- Row
@dataclass
class RowResult:
    values: list[Any]
    notes: list[str] = field(default_factory=list)
    open_items: list[str] = field(default_factory=list)


_OPEN_PREFIXES = ("DOC_NO_UNKNOWN", "DOC_NO_BLANK", "BOOK_PAGE_UNKNOWN", "BOOK_PAGE_BLANK", "DATE_UNKNOWN", "DATE_BLANK",
                  "DATE_YEAR_ONLY", "DATE_MONTH_YEAR", "DATE_UNPARSED", "PARTY_UNKNOWN", "PARTY_BLANK", "LEGAL_UNKNOWN",
                  "LEGAL_BLANK", "LEGAL_FORMAT_REVIEW", "COMMENT_MOVED", "DOC_TYPE_UNKNOWN", "DOC_TYPE_BLANK",
                  "PAGE_UNKNOWN", "PAGE_BLANK", "PART_UNKNOWN", "DOC_NO_NON_NUMERIC")


def normalize_county_row(row: list[Any], section: int, twp: int, rge: int) -> RowResult:
    """row = [Document Type, Grantor, Grantee, Doc No, Book-Page, Date of Doc, Rec Date, Legal, Comments]"""
    row = list(row) + [None] * (9 - len(row))
    vals, notes = [], []
    for fn, v in ((norm_doc_type, row[0]), (norm_parties, row[1]), (norm_parties, row[2]), (norm_doc_no, row[3]),
                  (norm_book_page, row[4]), (norm_date, row[5]), (norm_date, row[6])):
        x, n = fn(v)
        vals.append(x); notes += n
    x, n = norm_legal(row[7], section, twp, rge); vals.append(x); notes += n
    x, n = norm_comment(row[8]); vals.append(x); notes += n
    # Blank Comments on a blank-image row is intentional; only non-blank-related notes are open items
    opens = [n for n in notes if n.startswith(_OPEN_PREFIXES) and not n.startswith("PARTY_BLANK")]
    opens += [n for n in notes if n.startswith("PARTY_BLANK")]
    return RowResult(vals, notes, opens)


def normalize_blm_row(row: list[Any], unnumbered: bool = False) -> RowResult:
    """row = [Document Type, Grantor, Grantee, File No, Page, Date of Doc, Rec Date, Comments, Legal, Part]
    File No and Comments are intentionally blank in every data row (not research gaps)."""
    row = list(row) + [None] * (10 - len(row))
    vals, notes = [], []
    x, n = norm_doc_type(row[0]); vals.append(x); notes += n
    x, n = norm_parties(row[1]); vals.append(x); notes += n
    x, n = norm_parties(row[2]); vals.append(x); notes += n
    if not is_blank(row[3]):
        notes.append(f"BLM_FILE_NO_CLEARED:{row[3]!r}")
    vals.append(None)
    x, n = norm_int(row[4], "PAGE"); vals.append(x); notes += n
    x, n = norm_date(row[5]); vals.append(x); notes += n
    x, n = norm_date(row[6]); vals.append(x); notes += n
    if not is_blank(row[7]):
        notes.append(f"BLM_COMMENT_CLEARED:{row[7]!r}")
    vals.append(None)
    x, n = norm_legal(row[8], blm_casewide=True); vals.append(x); notes += n
    x, n = norm_int(row[9], "PART"); notes += n
    if unnumbered and x is not None:
        notes.append(f"PART_CLEARED_UNNUMBERED_SOURCE:{x}")
        x = None
    vals.append(x)
    opens = [n for n in notes if n.startswith(_OPEN_PREFIXES)]
    # a blank Rec Date on a BLM row is common (no RECEIVED stamp) - keep as open item, examiner decides
    return RowResult(vals, notes, opens)
