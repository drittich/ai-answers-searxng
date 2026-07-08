import hashlib
import hmac
import json
import time

import pytest


# ---------------------------------------------------------------- config

def test_no_provider_means_inactive(make_plugin):
    p = make_plugin()
    assert p.provider == ''
    assert p.api_key == ''


def test_openrouter_preset_defaults(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='sk-or-x')
    assert p.provider == 'openrouter'
    assert p.endpoint_url == 'https://openrouter.ai/api/v1/chat/completions'
    assert p.model  # preset default present
    assert p.api_key == 'sk-or-x'


def test_model_override(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_MODEL='deepseek/deepseek-v4-flash')
    assert p.model == 'deepseek/deepseek-v4-flash'


@pytest.mark.parametrize("url,expected", [
    ("https://api.openai.com/v1/chat/completions", "openai"),
    ("https://openrouter.ai/api/v1/chat/completions", "openrouter"),
    ("http://localhost:11434/v1/chat/completions", "ollama"),
    ("https://generativelanguage.googleapis.com/v1beta/models/x:streamGenerateContent", "gemini"),
    ("https://myinstance.openai.azure.com/deploy", "azure"),
    ("https://api-inference.huggingface.co/models/m/v1/chat/completions", "huggingface"),
    ("https://my-custom-llm.example.com/v1/chat/completions", "openai"),
])
def test_provider_autodetect_from_url(make_plugin, url, expected):
    p = make_plugin(LLM_URL=url, LLM_KEY='k')
    assert p.provider == expected


def test_local_provider_gets_dummy_key(make_plugin):
    p = make_plugin(LLM_PROVIDER='ollama')
    assert p.api_key == 'none'


def test_invalid_max_tokens_falls_back(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_MAX_TOKENS='banana')
    assert p.max_tokens == 500


def test_reasoning_max_tokens(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    assert p.reasoning_max_tokens == 0
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_REASONING_MAX_TOKENS='2000')
    assert p.reasoning_max_tokens == 2000
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_REASONING_MAX_TOKENS='-5')
    assert p.reasoning_max_tokens == 0


def test_extra_body_parsing(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k',
                    LLM_EXTRA_BODY='{"reasoning_effort": "high", "top_p": 0.9}')
    assert p.extra_body == {"reasoning_effort": "high", "top_p": 0.9}
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_EXTRA_BODY='not json')
    assert p.extra_body == {}
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_EXTRA_BODY='[1,2]')
    assert p.extra_body == {}


def test_collapsed_flag(make_plugin):
    assert make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k').collapsed is True
    assert make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_COLLAPSED='false').collapsed is False


def test_bare_host_url_defaults_to_https(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_URL='myhost.lan:8080/v1/chat/completions')
    assert p.endpoint_url.startswith('https://')


# ---------------------------------------------------------------- context assembly

class AttrResult:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _results(n):
    return [
        {"title": f"Title {i}", "content": f"Content {i} " + "x" * 900,
         "url": f"https://example{i}.com/page", "publishedDate": "2026-01-01"}
        for i in range(1, n + 1)
    ]


def test_parse_aux_results_dict_and_attr(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    raw = [
        {"title": "Dict", "content": "c", "url": "https://d.com"},
        AttrResult(title="Attr", content="c2", url="https://a.com", publishedDate=""),
    ]
    clean, infoboxes, answers = p._parse_aux_results(raw, [], [])
    assert clean[0]['title'] == 'Dict'
    assert clean[1]['title'] == 'Attr'


def test_parse_aux_results_respects_limit(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k',
                    LLM_CONTEXT_DEEP_COUNT='2', LLM_CONTEXT_SHALLOW_COUNT='3')
    clean, _, _ = p._parse_aux_results(_results(20), [], [])
    assert len(clean) == 5


def test_parse_aux_results_skips_own_widget_answer(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    answers = [
        {"answer": '<article id="sxng-stream-box">...</article>'},
        {"answer": "42 is the answer"},
    ]
    _, _, parsed = p._parse_aux_results([], [], answers)
    assert parsed == ["42 is the answer"]


def test_assemble_context_tiers(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k',
                    LLM_CONTEXT_DEEP_COUNT='2', LLM_CONTEXT_SHALLOW_COUNT='3')
    clean, _, _ = p._parse_aux_results(_results(10), [], [])
    ctx, urls = p._assemble_context(clean, [{"infobox": "IB", "content": "info content", "attributes": []}], ["quick answer"])
    assert "KNOWLEDGE GRAPH:" in ctx
    assert "DEEP SOURCES:" in ctx
    assert "SHALLOW SOURCES (headlines):" in ctx
    # deep sources carry content, shallow are headline-only
    assert "[1] example1.com" in ctx and "Content 1" in ctx
    assert "[3] example3.com" in ctx and "Content 3" not in ctx
    assert len(urls) == 5
    # deep content is truncated to 800 chars
    deep_line = next(line for line in ctx.split("\n") if line.startswith("[1]"))
    assert len(deep_line) < 900


def test_assemble_context_offset_numbers_follow_up_sources(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k',
                    LLM_CONTEXT_DEEP_COUNT='2', LLM_CONTEXT_SHALLOW_COUNT='0')
    clean, _, _ = p._parse_aux_results(_results(2), [], [])
    ctx, _ = p._assemble_context(clean, [], [], offset=7)
    assert "[8]" in ctx and "[9]" in ctx


# ---------------------------------------------------------------- routes / token security

def _make_app(plugin):
    import flask
    app = flask.Flask(__name__)
    plugin.init(app)
    return app.test_client()


def _token(plugin, ts=None):
    ts = str(int(ts if ts is not None else time.time()))
    sig = hmac.new(plugin.secret.encode(), ts.encode(), hashlib.sha256).hexdigest()
    return f"{ts}.{sig}"


def _legacy_token(plugin, ts=None):
    """Pre-HMAC token format: sha256(ts + secret). Must be rejected."""
    ts = str(int(ts if ts is not None else time.time()))
    sig = hashlib.sha256(f"{ts}{plugin.secret}".encode()).hexdigest()
    return f"{ts}.{sig}"


def test_stream_rejects_bad_tokens(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    client = _make_app(p)
    for tk in ["", "garbage", "123.deadbeef", _token(p) + "x", _legacy_token(p)]:
        rv = client.post('/ai-stream', json={"q": "test", "tk": tk})
        assert rv.status_code == 403, f"token {tk!r} should be rejected"


def test_token_roundtrip_hmac(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    ts = str(int(time.time()))
    assert p._verify_token(p._make_token(ts)) is True
    assert p._verify_token(_legacy_token(p)) is False
    assert p._verify_token(None) is False
    assert p._verify_token(12345) is False


def test_stream_rejects_expired_token(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    client = _make_app(p)
    rv = client.post('/ai-stream', json={"q": "test", "tk": _token(p, ts=time.time() - 7200)})
    assert rv.status_code == 403


def test_stream_missing_key_returns_400(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter')  # no LLM_KEY
    client = _make_app(p)
    rv = client.post('/ai-stream', json={"q": "test", "tk": _token(p)})
    assert rv.status_code == 400


def test_aux_search_rejects_bad_token(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    client = _make_app(p)
    rv = client.post('/ai-auxiliary-search', json={"query": "test", "tk": "garbage"})
    assert rv.status_code == 403


def test_aux_search_bad_offset_does_not_crash(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    client = _make_app(p)
    # empty query short-circuits after input parsing; a non-numeric offset
    # must not raise in the clamping code
    rv = client.post('/ai-auxiliary-search', json={"query": "", "offset": "abc", "tk": _token(p)})
    assert rv.status_code == 200
    assert rv.get_json() == {"results": []}


def test_weak_secret_warning(make_plugin, monkeypatch, caplog):
    import ai_answers
    monkeypatch.setitem(ai_answers.settings['server'], 'secret_key', 'ultrasecretkey')
    with caplog.at_level('WARNING'):
        make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    assert any('secret_key' in r.message for r in caplog.records)


# ---------------------------------------------------------------- streaming parser

class FakeHTTPResponse:
    def __init__(self, status, lines):
        self.status = status
        self._lines = [line if isinstance(line, bytes) else line.encode() for line in lines]
        self._i = 0

    def readline(self):
        if self._i < len(self._lines):
            line = self._lines[self._i]
            self._i += 1
            return line
        return b''

    def read(self, n=-1):
        return b''


class FakeConn:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def request(self, method, path, body=None, headers=None):
        self.requests.append({"method": method, "path": path, "body": body, "headers": headers})

    def getresponse(self):
        return self.response

    def close(self):
        pass


def _sse(obj):
    return f"data: {json.dumps(obj)}\n"


def _delta(**kw):
    return _sse({"choices": [{"delta": kw}]})


def _stream_with(monkeypatch, plugin, lines, status=200):
    import ai_answers
    conn = FakeConn(FakeHTTPResponse(status, lines))
    monkeypatch.setattr(ai_answers, "_get_streaming_connection", lambda url: (conn, "/v1/chat/completions"))
    client = _make_app(plugin)
    rv = client.post('/ai-stream', json={"q": "why is the sky blue", "lang": "en",
                                         "context": "[1] example.com: Sky: Rayleigh", "tk": _token(plugin)})
    return conn, rv.get_data(as_text=True)


def test_stream_reasoning_content_wrapped_in_think_tags(make_plugin, monkeypatch):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    lines = [
        _delta(role="assistant", content=None),          # null content (issue #10 shape)
        _delta(reasoning_content="pondering "),
        _delta(reasoning_content="deeply"),
        _delta(content="The sky is blue [1]."),
        _sse({"choices": [{"finish_reason": "stop", "delta": {}}]}),
        "data: [DONE]\n",
    ]
    _, out = _stream_with(monkeypatch, p, lines)
    assert "<think>" in out and "</think>" in out
    assert "pondering deeply" in out
    assert out.index("</think>") < out.index("The sky is blue")


def test_stream_reasoning_only_still_closes_think_tag(make_plugin, monkeypatch):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    lines = [_delta(reasoning_content="thinking forever"), "data: [DONE]\n"]
    _, out = _stream_with(monkeypatch, p, lines)
    assert out.count("<think>") == 1 and out.count("</think>") == 1


def test_stream_upstream_error_is_generic(make_plugin, monkeypatch):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    lines = [_sse({"error": {"message": "rate limited (key sk-secret)"}})]
    _, out = _stream_with(monkeypatch, p, lines)
    assert "sk-secret" not in out
    assert "Upstream API error" in out


def test_connection_error_is_generic(make_plugin, monkeypatch):
    import ai_answers

    def boom(url):
        raise RuntimeError("secret-detail http://internal-host:8080")

    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    monkeypatch.setattr(ai_answers, "_get_streaming_connection", boom)
    client = _make_app(p)
    rv = client.post('/ai-stream', json={"q": "test", "tk": _token(p)})
    out = rv.get_data(as_text=True)
    assert "secret-detail" not in out and "internal-host" not in out
    assert "Connection error" in out


def test_stream_non_200_surfaced(make_plugin, monkeypatch):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    _, out = _stream_with(monkeypatch, p, ["irrelevant"], status=500)
    assert "API error 500" in out


def test_request_payload_shape(make_plugin, monkeypatch):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k',
                    LLM_MODEL='deepseek/deepseek-v4-flash',
                    LLM_MAX_TOKENS='500', LLM_REASONING_MAX_TOKENS='2000',
                    LLM_EXTRA_BODY='{"reasoning_effort": "high"}')
    conn, _ = _stream_with(monkeypatch, p, ["data: [DONE]\n"])
    body = json.loads(conn.requests[0]["body"])
    assert body["model"] == 'deepseek/deepseek-v4-flash'
    assert body["max_tokens"] == 2500                      # answer + reasoning budget
    assert body["reasoning_effort"] == "high"              # extra body merged
    assert body["stream"] is True
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["system", "user"]
    assert "CORE_DIRECTIVES" in body["messages"][0]["content"]
    assert "USER_QUERY" in body["messages"][1]["content"]
    assert "why is the sky blue" in body["messages"][1]["content"]
    # rule numbering regression (missing-comma bug): every rule gets its own number
    directives = body["messages"][0]["content"]
    nums = [int(m) for m in __import__('re').findall(r'^(\d+)\.', directives, __import__('re').M)]
    assert nums == list(range(1, len(nums) + 1)) and len(nums) >= 7
    assert conn.requests[0]["headers"]["Authorization"] == "Bearer k"


def test_default_prompt_anti_injection_and_recency(make_plugin, monkeypatch):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    conn, _ = _stream_with(monkeypatch, p, ["data: [DONE]\n"])
    system = json.loads(conn.requests[0]["body"])["messages"][0]["content"]
    assert "untrusted" in system
    assert "publishedDate" in system
    assert "Valid citation indices" in system
    assert "[*]" in system
    assert "Insufficient information to answer." in system


def test_stream_caps_context_and_q(make_plugin, monkeypatch):
    import ai_answers
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    conn = FakeConn(FakeHTTPResponse(200, ["data: [DONE]\n"]))
    monkeypatch.setattr(ai_answers, "_get_streaming_connection", lambda url: (conn, "/v1/chat/completions"))
    client = _make_app(p)
    rv = client.post('/ai-stream', json={"q": "q" * 10000, "context": "[1] " + "c" * 100000,
                                         "tk": _token(p)})
    rv.get_data()  # consume the streamed response so the request is issued
    user_msg = json.loads(conn.requests[0]["body"])["messages"][1]["content"]
    assert "q" * (ai_answers.MAX_QUERY_LEN + 1) not in user_msg
    assert "q" * ai_answers.MAX_QUERY_LEN in user_msg
    assert "c" * (ai_answers.MAX_CONTEXT_LEN + 1) not in user_msg


def test_gemini_key_in_header_not_url(make_plugin, monkeypatch):
    import ai_answers
    p = make_plugin(LLM_PROVIDER='gemini', LLM_KEY='AIza-test')
    seen_urls = []
    conn = FakeConn(FakeHTTPResponse(200, []))

    def fake_connect(url):
        seen_urls.append(url)
        return conn, "/v1beta/models/x:streamGenerateContent"

    monkeypatch.setattr(ai_answers, "_get_streaming_connection", fake_connect)
    client = _make_app(p)
    rv = client.post('/ai-stream', json={"q": "test", "tk": _token(p)})
    rv.get_data()  # consume the streamed response so the request is issued
    assert seen_urls and all('key=' not in u for u in seen_urls)
    assert conn.requests[0]["headers"]["x-goog-api-key"] == 'AIza-test'


# ---------------------------------------------------------------- post_search injection

class MockSearchQuery:
    def __init__(self, query="why is the sky blue", pageno=1, categories=None, lang='en'):
        self.query = query
        self.pageno = pageno
        self.categories = categories or ['general']
        self.lang = lang


class MockResultContainer:
    def __init__(self, results):
        self.answers = set()
        self.infoboxes = []
        self._results = results

    def get_ordered_results(self):
        return self._results


class MockSearch:
    def __init__(self, **kw):
        results = kw.pop('results', _results(5))
        self.search_query = MockSearchQuery(**kw)
        self.result_container = MockResultContainer(results)


def test_post_search_injects_answer(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    search = MockSearch()
    p.post_search(None, search)
    assert len(search.result_container.answers) == 1
    html = list(search.result_container.answers)[0]
    assert 'id="sxng-stream-box"' in html
    assert 'AI Overview' in html
    assert '__' not in html.replace('__proto__', ''), "unsubstituted JS placeholders remain"
    assert 'sxng-collapsed' in html


def test_post_search_respects_collapsed_off(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_COLLAPSED='false')
    search = MockSearch()
    p.post_search(None, search)
    html = list(search.result_container.answers)[0]
    assert 'class="sxng-collapsed"' not in html
    assert 'id="sxng-show-more"' not in html


@pytest.mark.parametrize("kw", [
    {"pageno": 2},
    {"categories": ["images"]},
])
def test_post_search_gating(make_plugin, kw):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    search = MockSearch(**kw)
    p.post_search(None, search)
    assert len(search.result_container.answers) == 0


def test_url_state_toggle(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    search = MockSearch()
    p.post_search(None, search)
    assert 'const url_state = true' in list(search.result_container.answers)[0]

    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_URL_STATE='false')
    search = MockSearch()
    p.post_search(None, search)
    assert 'const url_state = false' in list(search.result_container.answers)[0]


def test_citation_url_allowlist_present(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    search = MockSearch()
    p.post_search(None, search)
    html = list(search.result_container.answers)[0]
    assert 'safeCitationUrl' in html
    assert 'state.u.map(safeCitationUrl)' in html
    assert 'new_urls.map(safeCitationUrl)' in html


def test_post_search_question_mark_gate(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_QUESTION_MARK_REQUIRED='true')
    search = MockSearch(query="sky color")
    p.post_search(None, search)
    assert len(search.result_container.answers) == 0
    search = MockSearch(query="why is the sky blue?")
    p.post_search(None, search)
    assert len(search.result_container.answers) == 1
