import os
from google import genai
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv

load_dotenv()

token_path = os.path.expanduser(os.getenv("GOOGLE_TOKEN_PATH", "~/.agent_google_token.json"))
if not os.path.exists(token_path):
    print(f"Token not found at {token_path}")
    exit(1)

creds = Credentials.from_authorized_user_file(token_path)

print("Attempting to initialize new google.genai Client with Credentials...")
try:
    # vertexai=False for standard Google AI (non-vertex)
    # The new SDK might not take 'credentials' directly in Client()
    # but let's check its signature or common patterns.
    client = genai.Client(credentials=creds, vertexai=False)
    print("Success! Client initialized.")
    
    # Try a simple call
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="hello"
    )
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Failed: {e}")
    print("\nTrying alternative: pass token via config or environment?")
    
    try:
        # Check if we can pass it as a dict or something
        print("Dir of genai.Client:", dir(genai.Client))
    except:
        pass
