import pytest
from app.config import settings
from app.state.session_store import store

@pytest.fixture(autouse=True)
def test_environment_setup(monkeypatch):
    """
    Ensures unit tests run in hermetic simulation mode by default
    without relying on an active external server on port 8000.
    Integration tests explicitly override these settings.
    """
    store.clear()
    monkeypatch.setattr(settings, "decision_api_url", None)
    monkeypatch.setattr(settings, "ai_backend_url", None)
    yield
    store.clear()
