import hashlib
import hmac
import json
import time

import pytest


# ---------------------------------------------------------------- follow-ups

def _req_with_plugin_choices(choices):
    """Minimal stand-in for an SXNG request carrying per-user plugin prefs."""
    class Plugins:
        def __init__(self, c): self.choices = c
    class Prefs:
        def __init__(self, c): self.plugins = Plugins(c)
    class Req:
        def __init__(self, c): self.preferences = Prefs(c)
    return Req(choices)


def test_followups_default_off(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    assert p.followups is False
    # No preferences on the request -> falls back to the (off) env default.
    assert p._followups_enabled(object()) is False


def test_followups_env_var_enables(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_FOLLOWUPS='true')
    assert p.followups is True
    assert p._followups_enabled(object()) is True


def test_followups_per_user_toggle_overrides_env(make_plugin):
    import ai_answers
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_FOLLOWUPS='true')
    pid = ai_answers.FOLLOWUPS_PLUGIN_ID
    # User toggle off wins over the instance-wide env default.
    assert p._followups_enabled(_req_with_plugin_choices({pid: False})) is False
    # User toggle on.
    assert p._followups_enabled(_req_with_plugin_choices({pid: True})) is True
    # Toggle absent (companion plugin not registered) -> env fallback.
    assert p._followups_enabled(_req_with_plugin_choices({})) is True


def test_followups_companion_plugin_defaults_opt_in():
    import ai_answers
    class Cfg:
        active = False
    comp = ai_answers.AIFollowupsPlugin(Cfg())
    assert comp.id == ai_answers.FOLLOWUPS_PLUGIN_ID
    assert comp.active is False  # off by default (opt-in)


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


def test_reasoning_effort_parsing(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    assert p.reasoning_effort == ''
    for alias in ('off', 'none', 'disable', 'disabled', 'OFF'):
        p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_REASONING_EFFORT=alias)
        assert p.reasoning_effort == 'off'
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_REASONING_EFFORT='low')
    assert p.reasoning_effort == 'low'
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_REASONING_EFFORT='banana')
    assert p.reasoning_effort == ''


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


def test_session_cache_flag(make_plugin):
    assert make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k').session_cache is True
    assert make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k',
                       LLM_SESSION_CACHE='false').session_cache is False


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


def test_stream_openrouter_reasoning_field_wrapped_in_think_tags(make_plugin, monkeypatch):
    """OpenRouter's normalized schema uses delta.reasoning, not reasoning_content."""
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    lines = [
        _delta(reasoning="hmm, "),
        _delta(reasoning="Rayleigh scattering", content=None),
        _delta(content="The sky is blue [1]."),
        "data: [DONE]\n",
    ]
    _, out = _stream_with(monkeypatch, p, lines)
    assert "<think>" in out and "</think>" in out
    assert "hmm, Rayleigh scattering" in out
    assert out.index("</think>") < out.index("The sky is blue")


def test_reasoning_effort_sent_to_openrouter(make_plugin, monkeypatch):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_REASONING_EFFORT='off')
    conn, _ = _stream_with(monkeypatch, p, ["data: [DONE]\n"])
    assert json.loads(conn.requests[0]["body"])["reasoning"] == {"enabled": False}

    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_REASONING_EFFORT='low')
    conn, _ = _stream_with(monkeypatch, p, ["data: [DONE]\n"])
    assert json.loads(conn.requests[0]["body"])["reasoning"] == {"effort": "low"}

    # unset -> param absent; extra body wins over the effort setting
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    conn, _ = _stream_with(monkeypatch, p, ["data: [DONE]\n"])
    assert "reasoning" not in json.loads(conn.requests[0]["body"])
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_REASONING_EFFORT='off',
                    LLM_EXTRA_BODY='{"reasoning": {"effort": "high"}}')
    conn, _ = _stream_with(monkeypatch, p, ["data: [DONE]\n"])
    assert json.loads(conn.requests[0]["body"])["reasoning"] == {"effort": "high"}


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
    assert "published date" in system
    assert "Valid citation indices" in system
    assert "headlines only" in system
    assert "[*]" in system
    assert "Insufficient information to answer." in system


def test_max_source_idx_ignores_brackets_inside_snippets(make_plugin, monkeypatch):
    import ai_answers
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    conn = FakeConn(FakeHTTPResponse(200, ["data: [DONE]\n"]))
    monkeypatch.setattr(ai_answers, "_get_streaming_connection", lambda url: (conn, "/v1/chat/completions"))
    client = _make_app(p)
    ctx = "[1] example.com: Best of [2023]: snippet\n[2] other.com: Title: text"
    client.post('/ai-stream', json={"q": "test", "context": ctx, "tk": _token(p)}).get_data()
    system = json.loads(conn.requests[0]["body"])["messages"][0]["content"]
    assert "1-2" in system and "1-2023" not in system


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
    assert '<span>AI Summary</span>' in html
    assert '__' not in html.replace('__proto__', ''), "unsubstituted JS placeholders remain"
    assert 'sxng-collapsed' in html


def test_post_search_theme_and_a11y(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    search = MockSearch()
    p.post_search(None, search)
    html = list(search.result_container.answers)[0]
    # theme-safe colors: no hardcoded dark-theme text colors
    assert 'rgb(230, 232, 240)' not in html
    assert 'color: white' not in html
    assert 'var(--color-base-font' in html
    assert "var(--color-error" in html
    # screen-reader status region + disclaimer + reduced motion
    assert 'id="sxng-live-status"' in html
    assert 'role="status"' in html
    assert 'May contain mistakes' in html
    assert 'prefers-reduced-motion' in html
    # collapse is a whole-line multiple with a fade mask and a Show less toggle
    assert 'calc(10 * 1.5em)' in html
    assert 'mask-image' in html
    assert 'collapseAnswer' in html
    # error paths reveal the footer for retry
    assert 'revealFooter();' in html


def test_post_search_hides_native_answers(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    search = MockSearch()
    p.post_search(None, search)
    html = list(search.result_container.answers)[0]
    assert 'hideNativeAnswers();' in html
    assert 'function restoreNativeAnswers()' in html


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


def test_session_cache_toggle_and_key(make_plugin):
    # Default on: cache flag true and the key mixes in the category set so the
    # same query on a different tab is a distinct cache entry.
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    search = MockSearch(categories=['general'])
    p.post_search(None, search)
    html = list(search.result_container.answers)[0]
    assert 'const session_cache = true' in html
    assert 'const categories_init = "general"' in html
    assert 'sessionStorage.setItem(cacheKey' in html

    # Off via env.
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_SESSION_CACHE='false')
    search = MockSearch()
    p.post_search(None, search)
    assert 'const session_cache = false' in list(search.result_container.answers)[0]


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


# ---------------------------------------------------------------- overview frequency

@pytest.mark.parametrize("query,expected", [
    ("sky color?", True),                      # contains '?'
    ("why sky blue", True),                    # question word
    ("How rainbows form", True),               # case-insensitive
    ("what's a monad", True),                  # contraction of a question word
    ("compare rust go", True),
    ("difference tcp udp", True),
    ("best budget mechanical keyboard 2026", True),  # 5 words
    ("python list comprehension", False),      # short keyword search
    ("weather", False),
    ("whatever forever", False),
    ("how-to guides", False),                  # hyphenated word isn't "how"               # starts with, but isn't, a question word
    ("", False),
])
def test_auto_rule(query, expected):
    import ai_answers
    assert ai_answers.should_auto_generate(query, has_direct_answer=False) is expected


def test_auto_rule_skips_when_direct_answer():
    import ai_answers
    assert ai_answers.should_auto_generate("what is 2+2?", has_direct_answer=True) is False


class FakeRequest:
    """Stand-in for the SearXNG request seen by post_search."""
    def __init__(self, cookies=None, script_root=''):
        self.cookies = cookies or {}
        self.form = {}
        self.headers = {}
        self.script_root = script_root


@pytest.mark.parametrize("raw,expected", [
    (None, "manual"),
    ("always", "always"),
    ("auto", "auto"),
    (" Manual ", "manual"),
])
def test_overview_mode_env(make_plugin, raw, expected):
    env = {"LLM_PROVIDER": "openrouter", "LLM_KEY": "k"}
    if raw is not None:
        env["LLM_OVERVIEW_MODE"] = raw
    p = make_plugin(**env)
    assert p._overview_mode(None) == expected


@pytest.mark.parametrize("raw", ["never", "sometimes"])
def test_overview_mode_env_invalid_falls_back(make_plugin, caplog, raw):
    with caplog.at_level("WARNING"):
        p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_OVERVIEW_MODE=raw)
    assert p._overview_mode(None) == "manual"
    assert "LLM_OVERVIEW_MODE" in caplog.text
    assert "Falling back to 'manual'" in caplog.text


def test_overview_mode_cookie_overrides_env(make_plugin):
    import ai_answers
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_OVERVIEW_MODE='auto')
    cookie = ai_answers.OVERVIEW_MODE_COOKIE
    assert p._overview_mode(FakeRequest({cookie: 'manual'})) == "manual"
    assert p._overview_mode(FakeRequest({cookie: 'always'})) == "always"
    # A junk cookie is ignored in favour of the admin default.
    assert p._overview_mode(FakeRequest({cookie: 'never'})) == "auto"
    assert p._overview_mode(FakeRequest()) == "auto"


def test_question_mark_required_is_deprecated(make_plugin, caplog):
    with caplog.at_level("WARNING"):
        make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_QUESTION_MARK_REQUIRED='true')
    assert "LLM_QUESTION_MARK_REQUIRED" in caplog.text
    assert "LLM_OVERVIEW_MODE=auto" in caplog.text


def _render(plugin, request=None, **search_kw):
    search = MockSearch(**search_kw)
    plugin.post_search(request, search)
    answers = list(search.result_container.answers)
    assert len(answers) == 1
    return answers[0]


def _assert_start_state(html):
    if 'const auto_start = true' in html:
        assert 'class="answer sxng-pending"' not in html
        return True
    assert 'const auto_start = false' in html
    assert 'class="answer sxng-pending"' in html
    return False


def test_post_search_always_mode_assert_start_state(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_OVERVIEW_MODE='always')
    assert _assert_start_state(_render(p, query="weather")) is True


def test_post_search_manual_mode_shows_generate_button(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_OVERVIEW_MODE='manual')
    html = _render(p, query="why is the sky blue?")
    assert _assert_start_state(html) is False
    assert 'id="sxng-generate"' in html
    start = html.index('<button id="sxng-generate"')
    button = html[start:html.index('</button>', start)]
    assert button.endswith('</svg>Generate AI Summary')
    # The context is already in the page, so the click needs no extra search.
    assert 'const b64_init = "' in html


def test_generate_button_shows_bot_icon_not_sparkles(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_OVERVIEW_MODE='manual')
    html = _render(p, query="why is the sky blue?")
    start = html.index('<button id="sxng-generate"')
    button = html[start:html.index('</button>', start)]
    assert '✨' not in html
    assert '<svg' in button and 'aria-hidden="true"' in button
    # Same bot glyph as the panel header.
    assert '<path d="M12 6V2H8" />' in button
    assert button.index('<svg') < button.index('Generate AI Summary')


def test_no_sparkle_names_in_rendered_panel(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    html = _render(p, query="weather")
    assert 'sparkle' not in html.lower()


@pytest.mark.parametrize("query,expected", [
    ("why is the sky blue", True),
    ("python list comprehension", False),
])
def test_post_search_auto_mode_applies_rule(make_plugin, query, expected):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_OVERVIEW_MODE='auto')
    html = _render(p, query=query)
    assert _assert_start_state(html) is expected
    if not expected:
        assert 'id="sxng-generate"' in html


def test_post_search_auto_mode_skips_on_infobox(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_OVERVIEW_MODE='auto')
    search = MockSearch(query="what is python")
    search.result_container.infoboxes = [{'infobox': 'Python', 'content': 'A language'}]
    p.post_search(None, search)
    assert _assert_start_state(list(search.result_container.answers)[0]) is False


def test_post_search_cookie_mode_wins(make_plugin):
    import ai_answers
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_OVERVIEW_MODE='always')
    req = FakeRequest({ai_answers.OVERVIEW_MODE_COOKIE: 'manual'})
    html = _render(p, request=req, query="why is the sky blue?")
    assert _assert_start_state(html) is False
    assert 'const overview_mode = "manual"' in html
    # ...and the other way round: the cookie beats the built-in manual default.
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    req = FakeRequest({ai_answers.OVERVIEW_MODE_COOKIE: 'always'})
    html = _render(p, request=req, query="python list comprehension")
    assert _assert_start_state(html) is True


def test_post_search_cookieless_defaults_to_you_decide(make_plugin):
    # No cookie and no LLM_OVERVIEW_MODE: show the Generate button, make no
    # AI request until it is clicked.
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    html = _render(p, request=FakeRequest(), query="why is the sky blue?")
    assert _assert_start_state(html) is False
    assert 'const overview_mode = "manual"' in html
    assert 'id="sxng-generate"' in html


@pytest.mark.parametrize("interactive", ["true", "false"])
def test_post_search_gear_menu_in_both_modes(make_plugin, interactive):
    import ai_answers
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_INTERACTIVE=interactive)
    html = _render(p, request=FakeRequest(script_root='/searx'))
    # One gear in the panel header, one on the "You decide" button row.
    assert html.count('class="sxng-gear"') == 2
    assert 'id="sxng-mode-menu"' in html
    for label in ("Always", "It decides", "You decide", "Never"):
        assert f'>{label}<' in html
    # "Never" explains the Preferences switch and links to it.
    assert "script_root + '/preferences'" in html
    # Cookie is scoped to the script root, kept a year, SameSite=Lax.
    assert f'const mode_cookie = "{ai_answers.OVERVIEW_MODE_COOKIE}"' in html
    assert 'const script_root = "/searx"' in html
    assert 'max-age=31536000' in html
    assert 'SameSite=Lax' in html


@pytest.mark.parametrize("mode", ["always", "auto", "manual"])
def test_post_search_restores_shared_and_cached_answers_in_every_mode(make_plugin, mode):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_OVERVIEW_MODE=mode)
    html = _render(p, query="python list comprehension")
    # Restore paths run before the mode is consulted and reveal the panel.
    restore = html.index('restoreFromCache()) restored = true')
    decide = html.index('if (restored) revealPanel()')
    assert restore < decide
    assert html.index("location.hash.includes('ai=')") < decide


def test_post_search_question_mark_gate_applies_in_manual_mode(make_plugin):
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k',
                    LLM_QUESTION_MARK_REQUIRED='true', LLM_OVERVIEW_MODE='manual')
    search = MockSearch(query="sky color")
    p.post_search(None, search)
    assert len(search.result_container.answers) == 0


def test_cookieless_user_gets_no_followups_with_companion_plugin_default(make_plugin, monkeypatch):
    # SearXNG seeds a cookieless user's plugin choices from each registered
    # plugin's `active` state; README registers the companion with active: false.
    import flask
    import ai_answers

    class Cfg:
        active = False
    companion = ai_answers.AIFollowupsPlugin(Cfg())
    prefs = _req_with_plugin_choices({ai_answers.FOLLOWUPS_PLUGIN_ID: companion.active}).preferences

    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k')
    req = FakeRequest()
    req.preferences = prefs
    assert 'const show_followups = false' in _render(p, request=req)

    # The stream route must not ask the model for the follow-up block either.
    conn = FakeConn(FakeHTTPResponse(200, ["data: [DONE]\n"]))
    monkeypatch.setattr(ai_answers, "_get_streaming_connection", lambda url: (conn, "/v1/chat/completions"))
    app = flask.Flask(__name__)

    @app.before_request
    def _attach_prefs():
        flask.request.preferences = prefs
    p.init(app)
    app.test_client().post('/ai-stream', json={"q": "why is the sky blue", "lang": "en",
                                               "context": "[1] example.com: Sky: Rayleigh", "tk": _token(p)})
    system = json.loads(conn.requests[0]["body"])["messages"][0]["content"]
    assert "<<FOLLOWUPS>>" not in system


def _coarse_pointer_css(html):
    """Bodies of every `@media (pointer: coarse)` block in the page CSS."""
    import re
    return re.findall(r'@media \(pointer: coarse\)\s*\{(.*?)\n\s*\}\n', html, re.S)


def test_post_search_generate_button_keeps_44px_touch_target(make_plugin):
    import re
    p = make_plugin(LLM_PROVIDER='openrouter', LLM_KEY='k', LLM_OVERVIEW_MODE='manual')
    html = _render(p, query="why is the sky blue?")
    touch = "\n".join(_coarse_pointer_css(html))
    # The visible pill stays short; an invisible pseudo-element supplies the
    # tap area on touch screens.
    hit = re.search(r'\.sxng-generate-btn::(?:before|after)\s*\{([^}]*)\}', touch)
    assert hit, "no touch hit-area pseudo-element for the Generate button"
    rule = hit.group(1)
    assert re.search(r'min-height:\s*44px', rule)
    assert re.search(r'position:\s*absolute', rule)
    assert re.search(r'\.sxng-generate-btn\s*\{[^}]*position:\s*relative', html)
