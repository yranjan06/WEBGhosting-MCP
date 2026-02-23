import os
import requests
import json

api_key = "***REDACTED_KEY***"
base_url = "https://integrate.api.nvidia.com/v1"
model = "moonshotai/kimi-k2.5"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

payload = {
    "model": model,
    "messages": [
        {
            "role": "system",
            "content": "You are a web automation assistant. Return ONLY a JSON object with a test result like {'selector': '#success', 'confidence': 1.0}."
        },
        {
            "role": "user",
            "content": "Test prompt: Provide a test selector."
        }
    ],
    "max_tokens": 100,
    "temperature": 0.1
}

print("Testing NVIDIA API with Kimi K2.5...")
try:
    response = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=15)
    response.raise_for_status()
    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    print("API Response successful! Content received:")
    print(content)
except Exception as e:
    print(f"API Error: {e}")
    if 'response' in locals() and hasattr(response, 'text'):
        print(f"Response Body: {response.text}")
