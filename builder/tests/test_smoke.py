from builder.blocks import smoke


def test_chat_does_not_end_a_call_that_already_ended(monkeypatch):
    # /chat/end after the closing 502 ran the end-of-call tools again: close_call was recorded twice (rehearsal, 11 Oct)
    sent = []

    def api(method, path, body):
        sent.append(path)
        if path == "/api/v2/chat/message" and len(sent) == 2:
            raise RuntimeError("POST /api/v2/chat/message -> 502: error code: 502")
        return {"callId": "c1", "response": "Merhaba"}
    monkeypatch.setattr(smoke.freya, "api", api)
    assert smoke.chat("w", {}, ["Evet."]) == ["Merhaba", smoke.ENDED]
    assert "/api/v2/chat/end" not in sent


def test_chat_ends_a_call_that_is_still_open(monkeypatch):
    sent = []
    monkeypatch.setattr(smoke.freya, "api", lambda method, path, body: sent.append(path) or {"callId": "c1", "response": "x"})
    smoke.chat("w", {}, ["Evet."])
    assert sent[-1] == "/api/v2/chat/end"
