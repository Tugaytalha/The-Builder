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


def test_chat_takes_a_504_on_a_later_turn_as_the_call_end(monkeypatch):
    # the wrong-person close answered 504, not 502, three times (rehearsal build and chat, 11 Oct)
    def api(method, path, body):
        if body.get("callId"):
            raise RuntimeError("POST /api/v2/chat/message -> 504: error code: 504")
        return {"callId": "c1", "response": "Merhaba"}
    monkeypatch.setattr(smoke.freya, "api", api)
    assert smoke.chat("w", {}, ["Hayır, ben eşiyim."]) == ["Merhaba", smoke.ENDED]
