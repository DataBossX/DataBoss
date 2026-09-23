from tools.penterra.document_type_purity import merge_legal, split_document_type


def test_split_keeps_clean_type():
    clean, qual = split_document_type("Transfer of Operating Rights - below Shannon")
    assert clean == "Transfer of Operating Rights"
    assert qual == "below Shannon"


def test_split_without_separator_is_unchanged():
    clean, qual = split_document_type("Warranty Deed")
    assert clean == "Warranty Deed"
    assert qual == ""


def test_merge_legal_does_not_duplicate():
    assert merge_legal("Lots 1 and 8; below Shannon", "below Shannon") == "Lots 1 and 8; below Shannon"
