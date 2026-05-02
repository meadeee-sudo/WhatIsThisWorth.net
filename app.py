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

# IMPORTANT: remove redirect ambiguity
app.url_map.strict_slashes = False

CORS(app)

# -----------------------------
# CONFIG
# -----------------------------
EBAY_VERIFICATION_TOKEN = os.getenv("EBAY_VERIFICATION_TOKEN", "PUT_YOUR_TOKEN_HERE")


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
# SAFE REQUEST
# -----------------------------
def safe_get(url):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
        "Connection": "close"
    }

    try:
        return requests.get(url, headers=headers, timeout=10)
    except Exception as e:
        print("REQUEST ERROR:", repr(e))
        return None


# -----------------------------
# EBAY ACCOUNT DELETION WEBHOOK
# -----------------------------
@app.route("/ebay/account-deletion", methods=["GET", "POST"])
def ebay_account_deletion():

    token = EBAY_VERIFICATION_TOKEN
    if not token or token == "PUT_YOUR_TOKEN_HERE":
        return jsonify({"error": "server misconfigured"}), 500

    # -------------------------
    # GET CHALLENGE VALIDATION
    # -------------------------
    if request.method == "GET":

        challenge_code = request.args.get("challenge_code")
        if not challenge_code:
            return jsonify({"error": "missing challenge_code"}), 400

        # 🔥 CRITICAL FIX: use EXACT request URL eBay called
        endpoint = request.base_url  # THIS is key (no guessing, no hardcoding)

        # MUST be EXACT ORDER:
        raw = challenge_code + token + endpoint

        sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        response = jsonify({"challengeResponse": sha})
        response.headers["Content-Type"] = "application/json"
        response.headers["Cache-Control"] = "no-store"

        print("DEBUG ENDPOINT:", endpoint)
        print("DEBUG SHA:", sha)

        return response

    # -------------------------
    # POST EVENT
    # -------------------------
    if request.method == "POST":
        data = request.get_json(force=True, silent=True)
        print("eBay deletion event:", json.dumps(data, indent=2))
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
