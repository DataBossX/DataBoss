"""Cross-key proposals require independent corroboration."""

from horizon.crosskey import OracleRow, Suspect, digit_distance, suggest


def test_proximity_alone_never_proposes() -> None:
    result = suggest(
        Suspect(docno="900112", locator="p04r6"),
        [OracleRow(docno="900113")],
    )
    assert result["status"] == "NO_ORACLE_MATCH"
    assert result["candidates"] == []


def test_bookpage_match_is_decisive() -> None:
    result = suggest(
        Suspect(docno="900112", locator="p04r6", bookpage="0654-0561"),
        [OracleRow(docno="900113", bookpage="654-561")],
    )
    assert result["status"] == "CORRECTION_PROPOSED"
    assert result["candidates"][0]["docno"] == "900113"
    assert result["candidates"][0]["decisive"] is True
    assert result["candidates"][0]["digit_distance"] == 1


def test_recorded_date_can_corroborate_without_bookpage() -> None:
    result = suggest(
        Suspect(
            docno="900112",
            locator="p10r2",
            rec_date="3/4/2024",
            grantor="SYNTH ALPHA LLC",
        ),
        [
            OracleRow(
                docno="900114",
                rec_date="03/04/2024",
                grantor="Synth Alpha, LLC",
            )
        ],
    )
    assert result["status"] == "CORRECTION_PROPOSED"
    assert result["candidates"][0]["decisive"] is False
    assert any("recorded date" in item for item in result["candidates"][0]["evidence"])


def test_exact_oracle_hit_without_neighbour_is_confirmed() -> None:
    result = suggest(
        Suspect(docno="900200", bookpage="1000-0001"),
        [OracleRow(docno="900200", bookpage="1000-0001")],
    )
    assert result["status"] == "CONFIRMED"
    assert result["candidates"] == []


def test_digit_distance_rejects_length_mismatch() -> None:
    assert digit_distance("90011", "900112") == -1
    assert digit_distance("900112", "900113") == 1
