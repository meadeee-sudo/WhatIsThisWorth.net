rom flask import Flask, request, jsonify
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

# 🔥 CRITICAL: prevents slash redirects
app.url_map.strict_slashes = False

CORS(app)

# -----------------------------
# CONFIG
# -----------------------------
EBAY_VERIFICATION_TOKEN = os.getenv(
    "EBAY_VERIFICATION_TOKEN",
    "PUT_YOUR_TOKEN_HERE"
)

# 🔥 CANONICAL ENDPOINT (MUST MATCH EBAY CONFIG EXACTLY)
EBAY_ENDPOINT_URL = "https://whatisthisworth-net.onrender.com/ebay/account-deletion"

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
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
        "Connection": "close"
    }

    try:
        return requests.get(url, headers=headers, timeout=10)
    except Exception as e:
        print("❌ REQUEST ERROR:", repr(e))
        return None


# -----------------------------
# PRICE PARSER
# -----------------------------
def parse_price(text):
    if not text:
        return None

    text = text.replace(",", "").lower()
    nums = re.findall(r"\d+\.?\d*", text)

    if not nums:
        return None

    values = [float(n) for n in nums]

    if "to" in text and len(values) >= 2:
        return (values[0] + values[1]) / 2

    return values[0]


# -----------------------------
# OUTLIER FILTER
# -----------------------------
def remove_outliers(prices):
    if len(prices) < 5:
        return prices

    sorted_prices = sorted(prices)
    trim = max(1, int(len(sorted_prices) * 0.1))

    return sorted_prices[trim:-trim] if len(sorted_prices) > 2 * trim else sorted_prices


# -----------------------------
# SCRAPER
# -----------------------------
def fetch_from_scrape(query):
    encoded_query = quote_plus(query)

    url = (
        "https://www.ebay.com/sch/i.html"
        f"?_nkw={encoded_query}"
        "&LH_Sold=1"
        "&LH_Complete=1"
        "&_ipg=50"
    )

    res = safe_get(url)
    if not res or res.status_code != 200:
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    items = soup.select("li.s-item")

    comps = []

    for item in items:
        try:
            title_el = item.select_one(".s-item__title")
            price_el = item.select_one(".s-item__price")
            link_el = item.select_one("a")

            if not title_el or not price_el:
                continue

            title = title_el.get_text(strip=True)
            price = parse_price(price_el.get_text())
            url = link_el["href"] if link_el and link_el.has_attr("href") else None

            if not title or price is None:
                continue

            comps.append({
                "title": title,
                "price": price,
                "url": url
            })

        except Exception:
            continue

    return comps


# -----------------------------
# CONFIDENCE MODEL
# -----------------------------
def confidence_level(count, spread):
    if count < 5:
        return "low"
    if spread > 0.5:
        return "medium-low"
    if count < 15:
        return "medium"
    return "high"


# -----------------------------
# ESTIMATE ENGINE
# -----------------------------
def estimate(query):
    if not query:
        return {"error": "missing query"}

    cached = get_cached(query)
    if cached:
        return cached

    comps = fetch_from_scrape(query)

    if not comps:
        result = {
            "estimated_value": "N/A",
            "range": "N/A",
            "sales_found": 0,
            "confidence": "no data",
            "comps": []
        }
        set_cache(query, result)
        return result

    prices = [c["price"] for c in comps]
    filtered = remove_outliers(prices)

    median = statistics.median(filtered)
    low = min(filtered)
    high = max(filtered)

    spread = (high - low) / median if median else 0

    result = {
        "estimated_value": f"${int(median)}",
        "range": f"${int(low)} - ${int(high)}",
        "sales_found": len(comps),
        "confidence": confidence_level(len(comps), spread),
        "comps": sorted(comps, key=lambda x: x["price"])[:20]
    }

    set_cache(query, result)
    return result


# -----------------------------
# ROUTES
# -----------------------------
@app.route("/search")
def search():
    q = request.args.get("q", "")
    return jsonify(estimate(q))


@app.route("/")
def home():
    return "WhatIsThisWorth - MVP Engine Running"


# -----------------------------
# EBAY ACCOUNT DELETION
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

        # 🔥 FULLY CANONICAL (NO request-derived URL)
        raw = challenge_code + token + EBAY_ENDPOINT_URL
        sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        response = jsonify({"challengeResponse": sha})
        response.headers["Cache-Control"] = "no-store"

        return response


    # -------------------------
    # POST
    # -------------------------
    if request.method == "POST":
        try:
            data = request.get_json(force=True, silent=True)

            print("📩 eBay Account Deletion Event Received")
            print(json.dumps(data, indent=2))

            return jsonify({"status": "received"}), 200

        except Exception as e:
            print("❌ POST error:", repr(e))
            return jsonify({"error": "bad request"}), 400


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
