import requests

invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"

headers = {
  "Authorization": "Bearer ***REDACTED_KEY***",
  "Accept": "application/json"
}

payload = {
  "model": "moonshotai/kimi-k2.5",
  "messages": [{"role":"user","content":"Hello Kimi, non-streaming test."}],
  "max_tokens": 100,
  "temperature": 1.00,
  "top_p": 1.00,
  "stream": False,
  "chat_template_kwargs": {"thinking":True},
}

try:
    print("Testing NEW API key with NVIDIA API (kimi-k2.5) without streaming...")
    response = requests.post(invoke_url, headers=headers, json=payload)
    print("Success. Content:")
    print(response.json())
except Exception as e:
    print(f"Error occurred: {e}")
