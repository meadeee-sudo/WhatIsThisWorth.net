from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import time
import statistics
import os
import hashlib
import json
import base64

app = Flask(__name__)
app.url_map.strict_slashes = False
CORS(app)

# -----------------------------
# CONFIG
# -----------------------------
EBAY_VERIFICATION_TOKEN = os.getenv("EBAY_VERIFICATION_TOKEN")
EBAY_CLIENT_ID = "JamesMea-WITW-PRD-1ae8dccdf-5f0a505e"
EBAY_CLIENT_SECRET = os.getenv("EBAY_CLIENT_SECRET")
EBAY_ENDPOINT = "https://whatisthisworth-net.onrender.com/ebay/account-deletion"

# -----------------------------
# OAUTH HELPER
# -----------------------------
_cached_token = {"access_token": None, "expires_at": 0}

def get_ebay_token():
    now = time.time()
    if _cached_token["access_token"] and now < _cached_token["expires_at"]:
        return _cached_token["access_token"]

    auth_str = f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()

    url = "https://api.ebay.com/identity/v1/oauth2/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded_auth}"
    }
    payload = {"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}

    res = requests.post(url, headers=headers, data=payload)
    if res.status_code == 200:
        data = res.json()
        _cached_token["access_token"] = data["access_token"]
        _cached_token["expires_at"] = now + data["expires_in"] - 60
        return data["access_token"]
    return None

# -----------------------------
# EBAY API ENGINE
# -----------------------------
def fetch_ebay_data(query):
    token = get_ebay_token()
    if not token: return []

    url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    
    # BROADENING PARAMS: 
    # Removed strict condition filters to ensure we get results first
    params = {
        "q": query,
        "limit": 30,
        "sort": "price" # Helpful for finding a baseline
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US" # ⚡ CRITICAL HEADER
    }

    try:
        res = requests.get(url, headers=headers, params=params)
        if res.status_code != 200:
            print(f"DEBUG Error: {res.text}")
            return []
        
        items = res.json().get("itemSummaries", [])
        return [{
            "title": i["title"],
            "price": float(i["price"]["value"]),
            "url": i.get("itemWebUrl"),
            "thumbnail": i.get("image", {}).get("imageUrl")
        } for i in items]
    except:
        return []

# -----------------------------
# ROUTES
# -----------------------------
@app.route("/search")
def search_route():
    q = request.args.get("q", "")
    if not q: return jsonify({"error": "No query"}), 400
    
    comps = fetch_ebay_data(q)
    
    if not comps:
        return jsonify({"comps": [], "estimated_value": "N/A", "sales_found": 0})

    prices = sorted([c["price"] for c in comps])
    # Basic outlier removal
    if len(prices) > 4:
        prices = prices[1:-1]

    median = statistics.median(prices)
    
    return jsonify({
        "estimated_value": f"${int(median)}",
        "range": f"${int(min(prices))} - ${int(max(prices))}",
        "sales_found": len(comps),
        "comps": comps[:15]
    })

@app.route("/ebay/account-deletion", methods=["GET", "POST"])
def account_deletion():
    if request.method == "GET":
        challenge = request.args.get("challenge_code")
        raw = f"{challenge}{EBAY_VERIFICATION_TOKEN}{EBAY_ENDPOINT}"
        sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return jsonify({"challengeResponse": sha}), 200
    return jsonify({"status": "received"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
