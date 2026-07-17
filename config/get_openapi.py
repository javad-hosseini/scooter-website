# get_openapi.py
import json
import requests

response = requests.get('http://127.0.0.1:8000/api/schema/')
with open('openapi-schema.json', 'w', encoding='utf-8') as f:
    json.dump(response.json(), f, ensure_ascii=False, indent=2)

print('✅ فایل openapi-schema.json ذخیره شد!')