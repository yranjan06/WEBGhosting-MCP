import requests, base64, json

invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"

headers = {
  "Authorization": "Bearer ***REDACTED_KEY***",
  "Accept": "application/json"
}

with open('debug_text.txt', 'r') as f:
    text = f.read()

prompt = f"""Page Content:
{text}

Requested Schema:
Find all job listings in the text.
Output format: A JSON array of objects.
Each object must have exactly these keys: "title", "company", "experience", "location".
Example Output:
[
  {{"title": "Data Engineer", "company": "TCS", "experience": "5-10 Yrs", "location": "Bengaluru"}}
]
Return ONLY a valid JSON array.
"""

payload = {
  "model": "moonshotai/kimi-k2.5",
  "messages": [{"role":"user","content": prompt}],
  "max_tokens": 4096,
  "temperature": 0.1,
  "top_p": 1.00,
  "stream": False,
  "chat_template_kwargs": {"thinking":True},
}

response = requests.post(invoke_url, headers=headers, json=payload)
print(response.json())
