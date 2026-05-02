from flask import Flask, request, jsonify
from flask_cors import CORS
import time
import os
import hashlib
import json

app = Flask(__name__)

# Prevent Flask redirect behavior (important)
app.url_map.strict_slashes = False

CORS(app)

# -----------------------------
# CONFIG
# -----------------------------
EBAY_VERIFICATION_TOKEN = os.getenv(
    "EBAY_VERIFICATION_TOKEN",
    "PUT_YOUR_TOKEN_HERE"
)

# IMPORTANT:
# MUST EXACTLY MATCH eBay Developer Portal
EBAY_ENDPOINT = "https://whatisthisworth-net.onrender.com/ebay/account-deletion"


# -----------------------------
# EBAY WEBHOOK ENDPOINT
# -----------------------------
@app.route("/ebay/account-deletion", methods=["GET", "POST"])
def ebay_account_deletion():

    token = EBAY_VERIFICATION_TOKEN
    if not token or token == "PUT_YOUR_TOKEN_HERE":
        return jsonify({"error": "server misconfigured"}), 500

    # -------------------------
    # GET: eBay handshake
    # -------------------------
    if request.method == "GET":

        challenge_code = request.args.get("challenge_code")
        if not challenge_code:
            return jsonify({"error": "missing challenge_code"}), 400

        # 🔥 CRITICAL FIX:
        # Use EXACT endpoint string eBay expects (no request.base_url, no request.url)
        endpoint = EBAY_ENDPOINT.rstrip("/")

        # IMPORTANT ORDER (eBay spec):
        # challengeCode + verificationToken + endpoint
        raw = challenge_code + token + endpoint

        sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        # Debug logs (keep for now)
        print("DEBUG challenge_code:", challenge_code)
        print("DEBUG endpoint:", endpoint)
        print("DEBUG raw:", raw)
        print("DEBUG sha:", sha)

        return jsonify({"challengeResponse": sha}), 200

    # -------------------------
    # POST: notification event
    # -------------------------
    if request.method == "POST":
        data = request.get_json(force=True, silent=True)

        print("📩 eBay Account Deletion Event Received")
        print(json.dumps(data, indent=2))

        return jsonify({"status": "received"}), 200


# -----------------------------
# BASIC ROUTES
# -----------------------------
@app.route("/")
def home():
    return "WhatIsThisWorth running"


@app.route("/search")
def search():
    return jsonify({"status": "ok"})


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
