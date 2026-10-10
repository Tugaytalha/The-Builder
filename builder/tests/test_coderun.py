from builder.blocks.coderun import DATES_SOURCE, run_snippet, with_dates


def test_source_has_no_template_braces():
    assert "{{" not in DATES_SOURCE and "}}" not in DATES_SOURCE


def test_run_snippet_writes_vars():
    out = run_snippet(with_dates("vars['d'] = nth_business_day_after(date(2031,3,5), 1, set()).isoformat()"), {})
    assert out["d"] == "2031-03-06"


def test_run_tool_gives_params():
    from builder.blocks.coderun import run_tool
    assert run_tool("vars['x'] = params['p']", {}, {"p": 3}) == {"x": 3}
