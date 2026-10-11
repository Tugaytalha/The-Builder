from builder.trace import Trace


def test_trace_redacts_key_inside_exception(tmp_path, capsys):
    t = Trace(tmp_path / "t.jsonl", ["sekret123"])
    t.log("error", message="boom fak_ABC123 and sekret123")
    text = (tmp_path / "t.jsonl").read_text()
    out = capsys.readouterr().out
    assert "fak_ABC123" not in text and "sekret123" not in text
    assert "fak_ABC123" not in out and "sekret123" not in out and "[REDACTED]" in out


def test_trace_redacts_anthropic_keys(tmp_path):
    t = Trace(tmp_path / "t.jsonl", [])
    t.log("x", message="token sk-ant-oat01-AbC_d-123 end")
    assert "sk-ant-" not in (tmp_path / "t.jsonl").read_text()
