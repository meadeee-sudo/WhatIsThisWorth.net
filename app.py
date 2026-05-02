from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import time
import statistics
from bs4 import BeautifulSoup
import re
from urllib.parse import quote_plus
import os
import hashlib
import json

app = Flask(__name__)

# IMPORTANT: prevents Flask from redirecting /path vs /path/
app.url_map.strict_slashes = False

CORS(app)

# -----------------------------
# CONFIG
# -----------------------------
EBAY_VERIFICATION_TOKEN = os.getenv("EBAY_VERIFICATION_TOKEN", "PUT_YOUR_TOKEN_HERE")

# MUST EXACTLY MATCH eBay portal (no trailing slash)
EBAY_ENDPOINT_URL = "https://whatisthisworth-net.onrender.com/ebay/account-deletion"


# -----------------------------
# EBAY WEBHOOK
# -----------------------------
@app.route("/ebay/account-deletion", methods=["GET", "POST"])
def ebay_account_deletion():

    token = EBAY_VERIFICATION_TOKEN
    if not token or token == "PUT_YOUR_TOKEN_HERE":
        return jsonify({"error": "server misconfigured"}), 500

    # -------------------------
    # GET: eBay verification handshake
    # -------------------------
    if request.method == "GET":

        challenge_code = request.args.get("challenge_code")
        if not challenge_code:
            return jsonify({"error": "missing challenge_code"}), 400

        # 🔥 CRITICAL FIX:
        # NEVER use request.base_url (eBay rejects due to proxy variations)
        endpoint = EBAY_ENDPOINT_URL

        # REQUIRED ORDER (DO NOT CHANGE):
        # challengeCode + verificationToken + endpoint
        raw = challenge_code + token + endpoint

        sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        print("DEBUG CHALLENGE:", challenge_code)
        print("DEBUG ENDPOINT:", endpoint)
        print("DEBUG RAW:", raw)
        print("DEBUG SHA:", sha)

        response = jsonify({"challengeResponse": sha})
        response.headers["Content-Type"] = "application/json"
        response.headers["Cache-Control"] = "no-store"

        return response, 200

    # -------------------------
    # POST: deletion notification
    # -------------------------
    if request.method == "POST":
        try:
            data = request.get_json(force=True, silent=True)

            print("📩 eBay Account Deletion Event Received")
            print(json.dumps(data, indent=2))

            return jsonify({"status": "received"}), 200

        except Exception as e:
            print("POST ERROR:", repr(e))
            return jsonify({"error": "bad request"}), 400


# -----------------------------
# HEALTH CHECK
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
