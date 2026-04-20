import os
import warnings
import json
from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv

load_dotenv()

token_path = os.path.expanduser(os.getenv("GOOGLE_TOKEN_PATH", "~/.agent_google_token.json"))
if not os.path.exists(token_path):
    print(f"Token not found at {token_path}")
    exit(1)

creds = Credentials.from_authorized_user_file(token_path)

# The new SDK doesn't natively support OAuth creds easily in the Client constructor
# but we can try to use the API key if available or use the legacy SDK for inspection
api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    client = genai.Client(api_key=api_key)
    model_id = "gemini-3-flash-preview"

    tools = [
        types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name="check_price",
                description="Get the current price of a cryptocurrency",
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"}
                    },
                    "required": ["symbol"]
                }
            )
        ])
    ]

    print(f"Testing {model_id} with tools...")
    try:
        response = client.models.generate_content(
            model=model_id,
            contents="get the price for ETH",
            config=types.GenerateContentConfig(
                tools=tools
            )
        )

        print(f"Status: SUCCESS")
        print(f"Finish Reason: {response.candidates[0].finish_reason}")
        
        for i, part in enumerate(response.candidates[0].content.parts):
            print(f"\nPart {i}:")
            # Print all attributes of the part to see what's inside
            for attr in dir(part):
                if not attr.startswith('_') and getattr(part, attr) is not None:
                    val = getattr(part, attr)
                    if not callable(val):
                        print(f"  {attr}: {val}")

    except Exception as e:
        print(f"Error: {e}")
else:
    # Use legacy SDK to inspect
    import google.generativeai as legacy_genai
    legacy_genai.configure(credentials=creds)
    model = legacy_genai.GenerativeModel("gemini-3-flash-preview")
    
    tools = [{
        "function_declarations": [{
            "name": "check_price",
            "description": "Get the current price of a cryptocurrency",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"}
                },
                "required": ["symbol"]
            }
        }]
    }]
    
    print(f"Testing gemini-3-flash-preview with legacy SDK...")
    try:
        response = model.generate_content("get the price for ETH", tools=tools)
        print(f"Status: SUCCESS")
        candidate = response.candidates[0]
        print(f"Finish Reason: {candidate.finish_reason}")
        
        for i, part in enumerate(candidate.content.parts):
            print(f"\nPart {i}:")
            # Convert to dict to see all fields
            print(json.dumps(type(part).to_dict(part), indent=2))
    except Exception as e:
        print(f"Error: {e}")
