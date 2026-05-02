from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import os
import hashlib
import json

app = Flask(__name__)

# Prevent Flask from redirecting /endpoint to /endpoint/ 
app.url_map.strict_slashes = False

CORS(app)

# -----------------------------
# CONFIG
# -----------------------------
# This will pull 'ebay_wh_2026_LongBeach_api_secret_91kxQ' from Render env
EBAY_VERIFICATION_TOKEN = os.getenv("EBAY_VERIFICATION_TOKEN")

# MUST match exactly what you typed into the eBay Developer Portal
EBAY_ENDPOINT = "https://whatisthisworth-net.onrender.com/ebay/account-deletion"

# -----------------------------
# EBAY WEBHOOK ENDPOINT
# -----------------------------
@app.route("/ebay/account-deletion", methods=["GET", "POST"])
def ebay_account_deletion():
    
    # Validation check for environment variable
    if not EBAY_VERIFICATION_TOKEN or "PUT_YOUR_TOKEN" in EBAY_VERIFICATION_TOKEN:
        print("ERROR: EBAY_VERIFICATION_TOKEN is not set correctly in Render.")
        return jsonify({"error": "server misconfigured"}), 500

    # -------------------------
    # GET: eBay handshake (Verification)
    # -------------------------
    if request.method == "GET":
        challenge_code = request.args.get("challenge_code")
        if not challenge_code:
            return jsonify({"error": "missing challenge_code"}), 400

        # Build the hash string: challengeCode + verificationToken + endpoint
        # We use the constant EBAY_ENDPOINT to ensure no dynamic URL parts interfere
        raw_str = f"{challenge_code}{EBAY_VERIFICATION_TOKEN}{EBAY_ENDPOINT}"
        
        sha256_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

        # Detailed Debug Logs
        print("--- eBay Handshake Start ---")
        print(f"Challenge: {challenge_code}")
        print(f"Token:     {EBAY_VERIFICATION_TOKEN}")
        print(f"Endpoint:  {EBAY_ENDPOINT}")
        print(f"Raw Concatenation: {raw_str}")
        print(f"Generated SHA:     {sha256_hash}")
        print("--- eBay Handshake End ---")

        return jsonify({"challengeResponse": sha256_hash}), 200

    # -------------------------
    # POST: Actual Notification
    # -------------------------
    if request.method == "POST":
        data = request.get_json(force=True, silent=True)
        
        print("📩 eBay Account Deletion Event Received")
        print(json.dumps(data, indent=2))

        # eBay expects a 200 or 204 to acknowledge receipt
        return jsonify({"status": "received"}), 200


# -----------------------------
# BASIC ROUTES
# -----------------------------
@app.route("/")
def home():
    return "WhatIsThisWorth API is active"

@app.route("/search")
def search():
    return jsonify({"status": "ok"})

# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    # Render uses the PORT environment variable
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
