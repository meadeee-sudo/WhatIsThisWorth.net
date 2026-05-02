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
# CONFIG & CREDENTIALS
# -----------------------------
# Pulling from Render Environment Variables
EBAY_VERIFICATION_TOKEN = os.getenv("EBAY_VERIFICATION_TOKEN")
EBAY_CLIENT_ID = "JamesMea-WITW-PRD-1ae8dccdf-5f0a505e"
EBAY_CLIENT_SECRET = os.getenv("EBAY_CLIENT_SECRET") # Best to keep this in Render Env

# The exact endpoint used for your successful handshake
EBAY_ENDPOINT = "https://whatisthisworth-net.onrender.com/ebay/account-deletion"

# -----------------------------
# EBAY OAUTH TOKEN HELPER
# -----------------------------
_cached_token = {"access_token": None, "expires_at": 0}

def get_ebay_token():
    """Generates an Application Access Token (OAuth2)"""
    now = time.time()
    if _cached_token["access_token"] and now < _cached_token["expires_at"]:
        return _cached_token["access_token"]

    print("Refreshing eBay OAuth Token...")
    # Credentials must be base64 encoded for the token endpoint
    auth_str = f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()

    url = "https://api.ebay.com/identity/v1/oauth2/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded_auth}"
    }
    # We use 'client_credentials' for a general app-level search
    payload = {
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope"
    }

    try:
        res = requests.post(url, headers=headers, data=payload)
        if res.status_code == 200:
            data = res.json()
            _cached_token["access_token"] = data["access_token"]
            _cached_token["expires_at"] = now + data["expires_in"] - 60
            return data["access_token"]
        print(f"Auth Error: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"OAuth Exception: {e}")
    return None

# -----------------------------
# EBAY BROWSE API CALL
# -----------------------------
def fetch_ebay_data(query):
    token = get_ebay_token()
    if not token: return []

    # API Endpoint for Browse Search
    url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    
    # We filter for 'FIXED_PRICE' and 'AUCTION'
    # Note: To get 'Marketplace Insights' (True Sold Data), you need extra approval.
    # For a general search, we use 'item_summary'.
    params = {
        "q": query,
        "limit": 50,
        "filter": "buyingOptions:{FIXED_PRICE|AUCTION},conditions:{USED|NEW}"
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        res = requests.get(url, headers=headers, params=params)
        if res.status_code != 200:
            print(f"eBay Search Error: {res.text}")
            return []
        
        items = res.json().get("itemSummaries", [])
        comps = []
        for item in items:
            try:
                comps.append({
                    "title": item["title"],
                    "price": float(item["price"]["value"]),
                    "url": item.get("itemWebUrl"),
                    "thumbnail": item.get("image", {}).get("imageUrl")
                })
            except (KeyError, ValueError):
                continue
        return comps
    except Exception as e:
        print(f"Search Exception: {e}")
        return []

# -----------------------------
# ANALYSIS LOGIC
# -----------------------------
def analyze_prices(comps):
    if not comps:
        return {"estimated_value": "N/A", "range": "N/A", "sales_found": 0, "comps": []}

    prices = sorted([c["price"] for c in comps])
    
    # Remove outliers (top/bottom 10%)
    if len(prices) > 5:
        trim = max(1, int(len(prices) * 0.1))
        prices = prices[trim:-trim]

    median = statistics.median(prices)
    low, high = min(prices), max(prices)
    
    return {
        "estimated_value": f"${int(median)}",
        "range": f"${int(low)} - ${int(high)}",
        "sales_found": len(comps),
        "comps": comps[:15] # Return first 15 for the UI
    }

# -----------------------------
# ROUTES
# -----------------------------
@app.route("/search")
def search_route():
    q = request.args.get("q", "")
    if not q: return jsonify({"error": "No query"}), 400
    
    raw_data = fetch_ebay_data(q)
    analysis = analyze_prices(raw_data)
    return jsonify(analysis)

@app.route("/ebay/account-deletion", methods=["GET", "POST"])
def account_deletion():
    # KEEPING YOUR SUCCESSFUL HANDSHAKE LOGIC
    if request.method == "GET":
        challenge = request.args.get("challenge_code")
        # Ensure raw concatenation matches what you verified
        raw = f"{challenge}{EBAY_VERIFICATION_TOKEN}{EBAY_ENDPOINT}"
        sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return jsonify({"challengeResponse": sha}), 200

    if request.method == "POST":
        print(f"Deletion Request Received: {request.get_json()}")
        return jsonify({"status": "received"}), 200

@app.route("/")
def home():
    return "WhatIsThisWorth API - eBay Official Engine Active"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
