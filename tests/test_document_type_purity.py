from tools.penterra.document_type_purity import merge_legal, split_document_type


def test_split_keeps_clean_type_and_moves_scope():
    clean, qual = split_document_type(
        "Transfer of Operating Rights - below base of Shannon Formation"
    )
    assert clean == "Transfer of Operating Rights"
    assert qual == "below base of Shannon Formation"
    assert merge_legal("Lots 1-3, 6-8, aol", qual) == (
        "Lots 1-3, 6-8, aol; below base of Shannon Formation"
    )


def test_split_does_not_invent_when_already_clean():
    clean, qual = split_document_type("Assignment of Record Title Interest")
    assert clean == "Assignment of Record Title Interest"
    assert qual == ""
    assert merge_legal("All of 11, aol", qual) == "All of 11, aol"


def test_merge_is_idempotent():
    legal = merge_legal("All of 11, aol", "non-Shannon rights")
    assert merge_legal(legal, "non-Shannon rights") == legal
