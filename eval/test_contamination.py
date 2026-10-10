from contamination import brief_tokens, find_leaks


def make(tmp_path, code):
    b = tmp_path / "builder"
    (b / "runs").mkdir(parents=True)
    (b / "x.py").write_text(code)
    brief = tmp_path / "brief.md"
    brief.write_text("Holiday 2031-05-01. Floor 12.50, limit 1500. Close as `call_later`. Day 7.")
    return b, brief


def test_brief_tokens():
    assert brief_tokens("On 2031-05-01 pay 12.50 or 1500 as `call_later`, not 7 or `word`.") == {
        "2031-05-01", "12.50", "1500", "call_later"}


def test_finds_a_date(tmp_path):
    b, brief = make(tmp_path, "H = ['2031-05-01']\n")
    assert find_leaks(b, [brief], set()) == [f"{b / 'x.py'}:1: 2031-05-01"]


def test_finds_a_code_word(tmp_path):
    b, brief = make(tmp_path, "close = 'call_later'\n")
    assert len(find_leaks(b, [brief], set())) == 1


def test_ignores_allowed_token(tmp_path):
    b, brief = make(tmp_path, "close = 'call_later'\n")
    assert find_leaks(b, [brief], {"call_later"}) == []


def test_skips_runs_folder(tmp_path):
    b, brief = make(tmp_path, "x = 1\n")
    (b / "runs" / "r.py").write_text("H = ['2031-05-01']\n")
    assert find_leaks(b, [brief], set()) == []
