import os
import warnings
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv

load_dotenv()

token_path = os.path.expanduser(os.getenv("GOOGLE_TOKEN_PATH", "~/.agent_google_token.json"))
if not os.path.exists(token_path):
    print(f"Token not found at {token_path}")
    exit(1)

with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai

try:
    creds = Credentials.from_authorized_user_file(token_path)
    genai.configure(credentials=creds)

    print("Available models supporting generateContent:")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"Error listing models: {e}")
