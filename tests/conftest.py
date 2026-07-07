"""Pytest fixtures: mock the searx package so ai_answers.py imports standalone."""
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_searx_mocks():
    if "searx" in sys.modules:
        return

    searx = ModuleType("searx")
    searx.settings = {"server": {"secret_key": "test-secret"}}

    searx_plugins = ModuleType("searx.plugins")

    class Plugin:
        def __init__(self, cfg):
            self.active = getattr(cfg, "active", True)

    class PluginInfo:
        def __init__(self, **kwargs):
            self.meta = kwargs

    searx_plugins.Plugin = Plugin
    searx_plugins.PluginInfo = PluginInfo

    searx_results = ModuleType("searx.result_types")

    class EngineResults:
        def __init__(self):
            self.types = ModuleType("types")
            self.types.Answer = lambda *args, **kwargs: kwargs.get("answer", args[0] if args else "")

    searx_results.EngineResults = EngineResults

    searx_network = ModuleType("searx.network")

    class _Network:
        verify = True

    searx_network.get_network = lambda: _Network()

    flask_babel = ModuleType("flask_babel")
    flask_babel.gettext = lambda s: s

    searx.plugins = searx_plugins
    searx.result_types = searx_results
    searx.network = searx_network

    sys.modules["searx"] = searx
    sys.modules["searx.plugins"] = searx_plugins
    sys.modules["searx.result_types"] = searx_results
    sys.modules["searx.network"] = searx_network
    sys.modules["flask_babel"] = flask_babel


_install_searx_mocks()

LLM_ENV_VARS = [
    "LLM_PROVIDER", "LLM_KEY", "LLM_MODEL", "LLM_URL",
    "LLM_MAX_TOKENS", "LLM_REASONING_MAX_TOKENS", "LLM_EXTRA_BODY",
    "LLM_TEMPERATURE", "LLM_CONTEXT_DEEP_COUNT", "LLM_CONTEXT_SHALLOW_COUNT",
    "LLM_TABS", "LLM_INTERACTIVE", "LLM_COLLAPSED",
    "LLM_QUESTION_MARK_REQUIRED", "LLM_OLLAMA_UNLOAD_AFTER", "LLM_SYSTEM_PROMPT",
]


@pytest.fixture
def make_plugin(monkeypatch):
    """Build a fresh SXNGPlugin with exactly the given env vars set."""
    def _make(**env):
        for var in LLM_ENV_VARS:
            monkeypatch.delenv(var, raising=False)
        for key, val in env.items():
            monkeypatch.setenv(key, val)
        import ai_answers

        class Cfg:
            active = True

        return ai_answers.SXNGPlugin(Cfg())

    return _make
