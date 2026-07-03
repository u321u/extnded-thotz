from extnded_thotz.llm_cleanup import polish, should_polish


class _Msg:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class FakeClient:
    def __init__(self, reply=None, error=None):
        self.reply = reply
        self.error = error
        outer = self

        class _Completions:
            def create(self, **kwargs):
                if outer.error:
                    raise outer.error
                return type("R", (), {"choices": [_Msg(outer.reply)]})()

        self.chat = type("C", (), {"completions": _Completions()})()


def test_polish_returns_cleaned_text():
    out = polish("um hello", "sk-x", _client=FakeClient(reply="Hello."))
    assert out == "Hello."


def test_polish_falls_back_on_error():
    out = polish("original text", "sk-x", _client=FakeClient(error=RuntimeError("boom")))
    assert out == "original text"


def test_polish_falls_back_on_empty_reply():
    assert polish("keep", "sk-x", _client=FakeClient(reply="")) == "keep"


def test_polish_noop_without_key_or_text():
    assert polish("text", "") == "text"
    assert polish("", "sk-x") == ""


def test_should_polish_matrix():
    assert should_polish({"llm_cleanup": "on"}, "") is True
    assert should_polish({"llm_cleanup": "auto"}, "sk-x") is True
    assert should_polish({"llm_cleanup": "auto"}, "") is False
    assert should_polish({"llm_cleanup": "off"}, "sk-x") is False
