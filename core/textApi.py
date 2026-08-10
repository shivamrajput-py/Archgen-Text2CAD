import requests
import json

# ==============================
# CONFIGURATION (EDIT THIS)
# ==============================
BASE_URL = "http://localhost:8000"      # Change port if needed
ENDPOINT = "/generate-cad"         # <-- PUT YOUR ENDPOINT HERE

URL = BASE_URL + ENDPOINT

# ==============================
# JSON BODY (EDIT THIS)
# ==============================
payload = {
    "prompt": """ 
design a twin tower, two 11 floors building attached with each other through a 2 skywalk, one at 4th floor and one at 7th floor and with a modern facade.
    """,
    "session_id": "",
    "new_session": True,
    "model_name": "mistralai/devstral-2512:free",
    "max_iterations": 5,
    "min_quality_score": 0.8,
    "temperature": 0.3
    # WHEN KEEPING 0.05, IT IS STAYING CONSTANT OR STATIC TOWARDS THE RAG DATASET MEANS LESS ERRORS LESS CREATIVITY.
}

# ==============================
# HEADERS
# ==============================
headers = {
    "Content-Type": "application/json",
    # "Authorization": "Bearer YOUR_TOKEN_HERE"  # Optional
}

# ==============================
# API CALL
# ==============================
try:
    response = requests.post(
        URL,
        headers=headers,
        json=payload,
        timeout=10000
    )

    # Raise error for 4xx / 5xx
    response.raise_for_status()

    print("✅ Status Code:", response.status_code)
    print("✅ Response JSON:")
    print(json.dumps(response.json(), indent=2))

except requests.exceptions.RequestException as e:
    print("❌ API Call Failed")
    print(e)
