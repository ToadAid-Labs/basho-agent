import os
import json
import webbrowser
import base64
import hashlib
import secrets
import time
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse
import requests
from rich.console import Console
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from google.oauth2.credentials import Credentials

console = Console()
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"

# Configuration for Google OAuth
SCOPES = [
    'https://www.googleapis.com/auth/generative-language.retriever',
    'https://www.googleapis.com/auth/cloud-platform',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid'
]

# Path to store the token
TOKEN_PATH = os.path.expanduser(os.getenv("GOOGLE_TOKEN_PATH", "~/.agent_google_token.json"))
OPENAI_CODEX_TOKEN_PATH = os.path.expanduser(os.getenv("OPENAI_CODEX_TOKEN_PATH", "~/.agent_openai_codex_auth.json"))
OPENAI_CODEX_CLIENT_ID = os.getenv("OPENAI_CODEX_CLIENT_ID", "app_EMoamEEZ73f0CkXaXp7hrann")
OPENAI_CODEX_REDIRECT_URI = os.getenv("OPENAI_CODEX_REDIRECT_URI", "http://localhost:1455/auth/callback")
OPENAI_CODEX_TOKEN_ENDPOINT = "https://auth.openai.com/oauth/token"

def get_google_client_config():
    """Load Google OAuth client config from env or an explicit local secrets path."""
    configured_path = os.getenv("GOOGLE_OAUTH_CLIENT_SECRETS")
    if configured_path:
        client_secret_path = Path(configured_path)
        if not client_secret_path.exists():
            raise FileNotFoundError(f"Google OAuth client secrets file not found: {client_secret_path}")
        with client_secret_path.open() as f:
            return json.load(f)

    env_client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    env_client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    if env_client_id and env_client_secret:
        return {
            "installed": {
                "client_id": env_client_id,
                "client_secret": env_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

    token_path = Path(os.path.expanduser(TOKEN_PATH))
    if token_path.exists():
        with token_path.open() as f:
            token_data = json.load(f)
        token_client_id = token_data.get("client_id")
        token_client_secret = token_data.get("client_secret")
        if token_client_id and token_client_secret:
            return {
                "installed": {
                    "client_id": token_client_id,
                    "client_secret": token_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                }
            }

    raise RuntimeError(
        "Google OAuth is not configured. Set GOOGLE_OAUTH_CLIENT_ID and "
        "GOOGLE_OAUTH_CLIENT_SECRET, set GOOGLE_OAUTH_CLIENT_SECRETS to a local "
        "client secrets JSON file, or use a Gemini API key."
    )

def google_api_key_login():
    """Gemini API key flow."""
    console.print("[bold cyan]Gemini API Key Authentication[/bold cyan]")
    console.print("Opening browser to Google AI Studio API Keys: https://aistudio.google.com/apikey")

    try:
        webbrowser.open("https://aistudio.google.com/apikey")
    except Exception:
        pass

    api_key = console.input("[bold blue]Enter Gemini API Key:[/bold blue] ").strip()
    if api_key:
        update_env("GEMINI_API_KEY", api_key)
        update_env("MODEL_PROVIDER", "gemini")
        console.print("[green]Gemini API Key saved![/green]")

def _google_oauth_missing_config_message() -> str:
    return (
        "Google OAuth needs your own OAuth client. Set GOOGLE_OAUTH_CLIENT_ID and "
        "GOOGLE_OAUTH_CLIENT_SECRET, or set GOOGLE_OAUTH_CLIENT_SECRETS to a local "
        "client secrets JSON file. For API-key auth, choose Gemini API Key."
    )

def _legacy_public_google_client_config():
    """Deprecated: retained only to make old docs/tests fail loudly if referenced."""
    return {
        "installed": {}
    }

def build_google_web_flow(redirect_uri: str, state: str | None = None) -> Flow:
    """Create a Google OAuth flow for Flask routes."""
    flow = Flow.from_client_config(
        get_google_client_config(),
        scopes=SCOPES,
        state=state,
    )
    flow.redirect_uri = redirect_uri
    return flow

def save_google_credentials(creds: Credentials) -> None:
    """Persist Google OAuth credentials for the Gemini client."""
    token_path = Path(os.path.expanduser(TOKEN_PATH))
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())

    update_env("MODEL_PROVIDER", "gemini")
    update_env("GOOGLE_TOKEN_PATH", str(token_path))

def save_openai_api_key(api_key: str) -> None:
    """Persist an OpenAI API key for the OpenAI client."""
    update_env("MODEL_PROVIDER", "openai")
    update_env("OPENAI_API_KEY", api_key)


def save_openai_model(model: str) -> None:
    """Persist the preferred standard OpenAI API model."""
    update_env("OPENAI_MODEL", model)

def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

def build_openai_codex_oauth_url(redirect_uri: str | None = None) -> tuple[str, str, str, str]:
    """Build a ChatGPT/Codex OAuth URL using the public Codex PKCE client."""
    redirect_uri = redirect_uri or OPENAI_CODEX_REDIRECT_URI
    verifier = _base64url(secrets.token_bytes(64))
    challenge = _base64url(hashlib.sha256(verifier.encode("ascii")).digest())
    state = secrets.token_urlsafe(32)
    query = urlencode({
        "response_type": "code",
        "client_id": OPENAI_CODEX_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "openid profile email offline_access",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "state": state,
        "originator": "web_dashboard",
    })
    return f"https://auth.openai.com/oauth/authorize?{query}", state, verifier, redirect_uri

def exchange_openai_codex_code(code: str, verifier: str, redirect_uri: str) -> dict:
    """Exchange a ChatGPT/Codex authorization code for OAuth tokens."""
    response = requests.post(
        OPENAI_CODEX_TOKEN_ENDPOINT,
        data={
            "grant_type": "authorization_code",
            "client_id": OPENAI_CODEX_CLIENT_ID,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()

def save_openai_codex_credentials(tokens: dict) -> None:
    """Persist ChatGPT/Codex OAuth tokens separately from OpenAI API keys."""
    token_path = Path(os.path.expanduser(OPENAI_CODEX_TOKEN_PATH))
    token_path.parent.mkdir(parents=True, exist_ok=True)

    expires_in = tokens.get("expires_in")
    payload = {
        "auth_mode": "chatgpt",
        "client_id": OPENAI_CODEX_CLIENT_ID,
        "tokens": tokens,
        "last_refresh": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if isinstance(expires_in, int):
        payload["expires_at"] = int(time.time()) + expires_in

    token_path.write_text(json.dumps(payload, indent=2))
    update_env("OPENAI_CODEX_TOKEN_PATH", str(token_path))
    update_env("MODEL_PROVIDER", "openai-codex")


def save_openai_codex_model(model: str) -> None:
    """Persist the preferred Codex CLI model."""
    update_env("OPENAI_CODEX_MODEL", model)

def _extract_oauth_code_and_state(value: str) -> tuple[str, str | None]:
    """Extract an OAuth code/state pair from a pasted callback URL or bare code."""
    value = value.strip()
    if value.startswith("http://") or value.startswith("https://"):
        query = parse_qs(urlparse(value).query)
        return query.get("code", [""])[0], query.get("state", [None])[0]
    return value, None

def _wait_for_openai_codex_callback(expected_state: str, timeout_seconds: int = 300) -> tuple[str | None, str | None]:
    """Capture the Codex OAuth callback on localhost:1455 when possible."""
    callback = {"code": None, "state": None, "error": None}

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def do_GET(self):
            query = parse_qs(urlparse(self.path).query)
            callback["code"] = query.get("code", [None])[0]
            callback["state"] = query.get("state", [None])[0]
            callback["error"] = query.get("error_description", query.get("error", [None]))[0]

            ok = callback["code"] and callback["state"] == expected_state
            status = 200 if ok else 400
            body = (
                "Authentication complete. You may close this window."
                if ok else
                "Invalid OAuth callback. Return to the terminal and paste the callback URL."
            )
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

    server = HTTPServer(("127.0.0.1", 1455), CallbackHandler)
    server.timeout = timeout_seconds
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    thread.join(timeout_seconds + 1)
    server.server_close()

    if callback["error"]:
        raise RuntimeError(callback["error"])
    return callback["code"], callback["state"]

def openai_codex_oauth_login():
    """OpenAI ChatGPT/Codex OAuth flow."""
    console.print("[bold cyan]OpenAI ChatGPT/Codex Web Authentication[/bold cyan]")
    authorization_url, state, verifier, redirect_uri = build_openai_codex_oauth_url(OPENAI_CODEX_REDIRECT_URI)
    console.print("\n[yellow]Opening your browser to sign in with ChatGPT...[/yellow]")
    console.print(f"[dim]{authorization_url}[/dim]\n")

    try:
        webbrowser.open(authorization_url)
    except Exception:
        pass

    code = None
    returned_state = None
    try:
        console.print("[dim]Waiting for OAuth callback on http://127.0.0.1:1455/auth/callback ...[/dim]")
        code, returned_state = _wait_for_openai_codex_callback(state)
    except OSError as exc:
        console.print(f"[yellow]Could not bind the local callback server:[/yellow] {exc}")
    except Exception as exc:
        console.print(f"[yellow]OAuth callback was not captured automatically:[/yellow] {exc}")

    if not code:
        pasted_value = console.input("[bold blue]Paste the final callback URL or authorization code:[/bold blue] ").strip()
        code, returned_state = _extract_oauth_code_and_state(pasted_value)

    if not code:
        console.print("[red]OpenAI OAuth failed: missing authorization code.[/red]")
        return
    if returned_state and returned_state != state:
        console.print("[red]OpenAI OAuth failed: invalid OAuth state.[/red]")
        return

    try:
        tokens = exchange_openai_codex_code(code, verifier, redirect_uri)
        save_openai_codex_credentials(tokens)
        console.print("[green]OpenAI ChatGPT/Codex OAuth saved![/green]")
        console.print(f"[dim]Token file: {OPENAI_CODEX_TOKEN_PATH}[/dim]")
        console.print(
            "[yellow]Note:[/yellow] OpenAI Codex is now the default provider. "
            "You can also run: python3 agent.py chat --provider openai-codex"
        )
    except Exception as exc:
        console.print(f"[red]OpenAI OAuth Error:[/red] {exc}")

def google_oauth_login():
    """Execute 'One-Click' Google Web Login using public credentials."""
    console.print("[bold cyan]Google Web Authentication[/bold cyan]")
    
    try:
        # We define the client config directly to avoid needing a file
        # The flow will now use a local server to capture the response
        flow = InstalledAppFlow.from_client_config(
            get_google_client_config(),
            scopes=SCOPES
        )

        console.print("\n[yellow]Opening your browser to link your Google Account...[/yellow]\n")
        
        # This starts a local server on a random port
        creds = flow.run_local_server(
            port=0, 
            prompt='consent',
            success_message='[green]Success! Your account is now linked to the trading bot. You can close this tab.[/green]'
        )
        
        save_google_credentials(creds)
        
        console.print("\n[green]Authentication Successful![/green]")
        
    except Exception as e:
        console.print(f"\n[red]OAuth Error:[/red] {e}")
        console.print(f"\n[yellow]Alternative:[/yellow] {_google_oauth_missing_config_message()}")

def openai_login():
    """OpenAI API Key flow."""
    console.print("[bold cyan]OpenAI Authentication[/bold cyan]")
    console.print("Opening browser to OpenAI API Keys: https://platform.openai.com/api-keys")
    
    try:
        webbrowser.open("https://platform.openai.com/api-keys")
    except Exception:
        pass
        
    api_key = console.input("[bold blue]Enter OpenAI API Key:[/bold blue] ").strip()
    if api_key:
        save_openai_api_key(api_key)
        console.print("[green]OpenAI API Key saved![/green]")

def update_env(key: str, value: str):
    """Update the .env file with the new key-value pair."""
    env_file = ENV_PATH
    os.environ[key] = value
    if not env_file.exists():
        with env_file.open('w') as f:
            f.write(f"{key}={value}\n")
        return

    with env_file.open('r') as f:
        lines = f.readlines()

    key_found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            key_found = True
            break
            
    if not key_found:
        lines.append(f"{key}={value}\n")

    with env_file.open('w') as f:
        f.writelines(lines)

def select_gemini_model():
    """Allow user to select or enter a specific Gemini model."""
    console.print("\n[bold]Select Gemini Model:[/bold]")
    console.print("  [bold cyan]1.[/bold cyan] Gemini 2.5 Flash (Recommended)")
    console.print("  [bold cyan]2.[/bold cyan] Gemini 2.5 Pro")
    console.print("  [bold cyan]3.[/bold cyan] Gemini 2.0 Flash")
    console.print("  [bold cyan]4.[/bold cyan] Gemini 3.0 Flash Preview")
    console.print("  [bold cyan]5.[/bold cyan] Enter custom model name")
    
    choice = console.input("[bold blue]Choice [1-5]:[/bold blue] ").strip()
    
    model = "gemini-2.5-flash"
    if choice == "1":
        model = "gemini-2.5-flash"
    elif choice == "2":
        model = "gemini-2.5-pro"
    elif choice == "3":
        model = "gemini-2.0-flash"
    elif choice == "4":
        model = "gemini-3-flash-preview"
    elif choice == "5":
        model = console.input("[bold blue]Enter model name (e.g. gemini-2.5-flash):[/bold blue] ").strip()
    
    if model:
        update_env("GEMINI_MODEL", model)
        console.print(f"[green]Gemini model set to {model}![/green]")

def interactive_login():
    """Run the interactive login flow."""
    console.print()
    console.print("[bold]How would you like to authenticate for this project?[/bold]")
    console.print("  [bold cyan]1.[/bold cyan] Google/Gemini Web Auth")
    console.print("  [bold cyan]2.[/bold cyan] Gemini API Key")
    console.print("  [bold cyan]3.[/bold cyan] OpenAI ChatGPT/Codex Web Auth")
    console.print("  [bold cyan]4.[/bold cyan] OpenAI API Key")
    console.print("  [bold cyan]5.[/bold cyan] Anthropic API Key")
    console.print("  [bold cyan]6.[/bold cyan] Use Local Ollama (No Auth)")
    console.print()
    
    choice = console.input("[bold blue]Choice [1-6]:[/bold blue] ").strip()
    
    if choice == "1":
        google_oauth_login()
        update_env("MODEL_PROVIDER", "gemini")
        select_gemini_model()
        console.print("[green]Provider set to Gemini![/green]")
    elif choice == "2":
        google_api_key_login()
        select_gemini_model()
    elif choice == "3":
        openai_codex_oauth_login()
    elif choice == "4":
        openai_login()
        update_env("MODEL_PROVIDER", "openai")
        console.print("[green]Provider set to OpenAI![/green]")
    elif choice == "5":
        console.print("Opening browser to Anthropic Console: https://console.anthropic.com/")
        try:
            webbrowser.open("https://console.anthropic.com/")
        except Exception:
            pass
        api_key = console.input("[bold blue]Enter Anthropic API Key:[/bold blue] ").strip()
        if api_key:
            update_env("ANTHROPIC_API_KEY", api_key)
            update_env("MODEL_PROVIDER", "anthropic")
            console.print("[green]Anthropic API Key saved![/green]")
    elif choice == "6":
        update_env("MODEL_PROVIDER", "ollama")
        console.print("[green]Provider set to Ollama. Make sure Ollama is running locally.[/green]")
    else:
        console.print("[red]Invalid choice.[/red]")
