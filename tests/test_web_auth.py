import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.auth as auth
from backend.app import app


def login(client):
    return client.post("/login", data={"password": "admin123"})


def test_google_auth_redirects_with_state(monkeypatch):
    class FakeFlow:
        def authorization_url(self, **kwargs):
            assert kwargs["access_type"] == "offline"
            assert kwargs["prompt"] == "consent"
            return "https://accounts.google.com/o/oauth2/auth?state=test-state", "test-state"

    monkeypatch.setattr("backend.app.build_google_web_flow", lambda redirect_uri: FakeFlow())
    app.config.update(TESTING=True, SERVER_NAME="localhost")

    with app.test_client() as client:
        login(client)
        response = client.get("/auth/google")

        assert response.status_code == 302
        assert response.headers["Location"].startswith("https://accounts.google.com/")
        with client.session_transaction() as session:
            assert session["google_oauth_state"] == "test-state"


def test_openai_auth_saves_key_and_provider(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    monkeypatch.setattr(auth, "ENV_PATH", env_path)

    app.config.update(TESTING=True)

    with app.test_client() as client:
        login(client)
        response = client.post("/auth/openai", data={"api_key": "sk-test", "api_model": "gpt-5.5"})

    assert response.status_code == 302
    assert "MODEL_PROVIDER=openai" in env_path.read_text()
    assert "OPENAI_API_KEY=sk-test" in env_path.read_text()
    assert "OPENAI_MODEL=gpt-5.5" in env_path.read_text()


def test_openai_codex_oauth_redirects_with_pkce_state(monkeypatch):
    def fake_build(redirect_uri):
        assert redirect_uri is None
        return "https://auth.openai.com/oauth/authorize?state=codex-state", "codex-state", "verifier", "http://localhost:1455/auth/callback"

    monkeypatch.setattr("backend.app.build_openai_codex_oauth_url", fake_build)
    app.config.update(TESTING=True)

    with app.test_client() as client:
        login(client)
        response = client.get("/auth/openai/oauth")

        assert response.status_code == 302
        assert response.headers["Location"].startswith("https://auth.openai.com/")
        with client.session_transaction() as session:
            assert session["openai_oauth_state"] == "codex-state"
            assert session["openai_oauth_verifier"] == "verifier"


def test_openai_codex_oauth_paste_saves_tokens(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    token_path = tmp_path / "codex.json"
    monkeypatch.setattr(auth, "ENV_PATH", env_path)
    monkeypatch.setattr(auth, "OPENAI_CODEX_TOKEN_PATH", str(token_path))
    monkeypatch.setattr("backend.app.exchange_openai_codex_code", lambda code, verifier, redirect_uri: {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600})

    app.config.update(TESTING=True)

    with app.test_client() as client:
        login(client)
        with client.session_transaction() as session:
            session["openai_oauth_state"] = "state-1"
            session["openai_oauth_verifier"] = "verifier"
            session["openai_oauth_redirect_uri"] = "http://localhost:1455/auth/callback"
            session["openai_oauth_model"] = "gpt-5.5"
        response = client.post(
            "/auth/openai/oauth/complete",
            data={"callback_value": "http://localhost:1455/auth/callback?code=code-1&state=state-1"},
        )

    assert response.status_code == 302
    assert "OPENAI_CODEX_TOKEN_PATH=" in env_path.read_text()
    assert "OPENAI_CODEX_MODEL=gpt-5.5" in env_path.read_text()
    assert '"access_token": "access"' in token_path.read_text()


def test_openai_model_settings_can_switch_default_provider(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    monkeypatch.setattr(auth, "ENV_PATH", env_path)

    app.config.update(TESTING=True)

    with app.test_client() as client:
        login(client)
        response = client.post(
            "/auth/openai/models",
            data={
                "api_model": "gpt-5.4",
                "codex_model": "gpt-5.5",
                "active_provider": "openai-codex",
            },
        )

    assert response.status_code == 302
    text = env_path.read_text()
    assert "OPENAI_MODEL=gpt-5.4" in text
    assert "OPENAI_CODEX_MODEL=gpt-5.5" in text
    assert "MODEL_PROVIDER=openai-codex" in text
