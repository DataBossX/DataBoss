"""well_data_collector -- build well records from OCC public-record context."""
from __future__ import annotations

from ..model import Well
from . import source_reader
from .party_and_date_extractor import to_short_date


def _find(d: dict, *names, default=""):
    for n in names:
        for k in d:
            if k and k.strip().lower() == n.lower():
                v = d[k]
                if v is not None and str(v).strip():
                    return str(v).strip()
    return default


def build_wells(path: str, wells_sheet: str, comp_sheet: str) -> list[Well]:
    wells_rows = source_reader.as_dicts(source_reader.read_sheet(path, wells_sheet))
    comp_rows = source_reader.as_dicts(source_reader.read_sheet(path, comp_sheet))
    comp_by_api = {_find(c, "API"): c for c in comp_rows}

    out: list[Well] = []
    for w in wells_rows:
        api = _find(w, "API")
        comp = comp_by_api.get(api, {})
        status = _find(w, "Status")
        name = f"{_find(w, 'Well Name', 'Well')} {_find(w, 'Well No.')}".strip()
        well = Well(
            name=name or "Unknown",
            api=api or "Unknown",
            operator=_find(w, "Operator") or _find(comp, "Operator / No."),
            location=_find(comp, "Location") or "Sec 27-11N-25W IM",
            str_label=f"{_find(w,'Section').replace('.00','')}-{_find(w,'Township')}-{_find(w,'Range')} {_find(w,'Meridian')}".strip(),
            formation=_find(comp, "Type / Class") or _find(w, "Well Type"),
            status=("Active" if status == "AC" else "Plugged/Abandoned" if status == "PA" else status or "Unknown"),
            spud_date=to_short_date(_find(comp, "Spud")),
            completion_date=to_short_date(_find(comp, "Completion")),
            first_production=to_short_date(_find(comp, "First Production")) or _find(comp, "First Sales"),
            last_production="Not Found (OTC production not pulled)",
            lease_unit="Needs Review (unit/order not image-verified)",
            hbp_relevance=(
                "Active well in section -> possible HBP support, but Cherokee-formation "
                "HBP NOT confirmed (completion match was Hogshooter, not Cherokee)."
                if status == "AC" else
                "Plugged/abandoned -> historic context only; no current HBP support."
            ),
            source="OCC RBDMS Wells + OCC Completion Data (context_public_records.xlsx)",
            notes=_find(comp, "OCC Data Set"),
            confidence=72,  # official OCC well presence/status: good, but title effect unverified
        )
        out.append(well)
    return out
