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

# Prevent slash redirect mismatch issues
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
# This MUST EXACTLY match what you entered in eBay Developer Portal
EBAY_ENDPOINT = "https://whatisthisworth-net.onrender.com/ebay/account-deletion"


# -----------------------------
# CACHE
# -----------------------------
CACHE = {}
CACHE_TTL = 60 * 60


def get_cached(query):
    entry = CACHE.get(query)
    if not entry:
        return None
    if time.time() - entry["time"] > CACHE_TTL:
        del CACHE[query]
        return None
    return entry["data"]


def set_cache(query, data):
    CACHE[query] = {"time": time.time(), "data": data}


# -----------------------------
# EBAY WEBHOOK
# -----------------------------
@app.route("/ebay/account-deletion", methods=["GET", "POST"])
def ebay_account_deletion():

    token = EBAY_VERIFICATION_TOKEN
    if not token or token == "PUT_YOUR_TOKEN_HERE":
        return jsonify({"error": "server misconfigured"}), 500

    # -------------------------
    # GET (challenge handshake)
    # -------------------------
    if request.method == "GET":

        challenge_code = request.args.get("challenge_code")
        if not challenge_code:
            return jsonify({"error": "missing challenge_code"}), 400

        # 🔥 CRITICAL: EXACT ORDER REQUIRED BY EBAY
        # challengeCode + verificationToken + endpoint
        raw = challenge_code + token + EBAY_ENDPOINT

        sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        # Debug (safe to remove later)
        print("DEBUG challenge_code:", challenge_code)
        print("DEBUG endpoint:", EBAY_ENDPOINT)
        print("DEBUG sha:", sha)

        response = jsonify({"challengeResponse": sha})
        response.headers["Content-Type"] = "application/json"
        response.headers["Cache-Control"] = "no-store"

        return response

    # -------------------------
    # POST (real notifications)
    # -------------------------
    if request.method == "POST":
        data = request.get_json(force=True, silent=True)

        print("📩 eBay Account Deletion Event Received")
        print(json.dumps(data, indent=2))

        return jsonify({"status": "received"}), 200


# -----------------------------
# SEARCH ENDPOINT (optional)
# -----------------------------
@app.route("/search")
def search():
    return jsonify({"status": "ok"})


@app.route("/")
def home():
    return "WhatIsThisWorth running"


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
