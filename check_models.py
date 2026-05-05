import os
import requests
from dotenv import load_dotenv

# Load your Grok API key from the .env file
load_dotenv()
GROK_API_KEY = os.getenv("GROK_API_KEY")

def list_available_models():
    url = "https://api.x.ai/v1/models"
    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}"
    }
    
    try:
        print("Fetching available models from xAI...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        models = [model["id"] for model in data.get("data", [])]
        
        print("\n✅ Models available to your API key:")
        print("-" * 40)
        for model_id in sorted(models):
            print(f" - {model_id}")
            
    except Exception as e:
        print(f"\n❌ Error fetching models: {e}")
        if 'response' in locals() and response.status_code != 200:
            print(f"Details: {response.text}")

if __name__ == "__main__":
    list_available_models()