from logic.formatters import format_naira_compact, format_naira_full


def test_format_naira_compact_millions():
    assert format_naira_compact(272_895_000) == "₦272.9M"


def test_format_naira_compact_thousands():
    assert format_naira_compact(88_062) == "₦88.1K"


def test_format_naira_full():
    assert format_naira_full(272_895_000) == "₦272,895,000.00"
