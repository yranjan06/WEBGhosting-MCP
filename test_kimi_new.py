import requests, base64

invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
stream = True

headers = {
  "Authorization": "Bearer ***REDACTED_KEY***",
  "Accept": "text/event-stream" if stream else "application/json"
}

payload = {
  "model": "moonshotai/kimi-k2.5",
  "messages": [{"role":"user","content":"Hello Kimi, are you online?"}],
  "max_tokens": 100,
  "temperature": 1.00,
  "top_p": 1.00,
  "stream": stream,
  "chat_template_kwargs": {"thinking":True},
}

try:
    print("Testing NEW API key with NVIDIA API (moonshotai/kimi-k2.5)...")
    response = requests.post(invoke_url, headers=headers, json=payload, timeout=20)
    
    if stream:
        for line in response.iter_lines():
            if line:
                print(line.decode("utf-8"))
    else:
        print(response.json())
except Exception as e:
    print(f"Error occurred: {e}")
