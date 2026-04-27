# app.py

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import time
import statistics
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

# -----------------------------
# SIMPLE CACHE (upgrade later)
# -----------------------------
CACHE = {}
CACHE_TTL = 60 * 60  # 1 hour


def get_cached(query):
    entry = CACHE.get(query)
    if not entry:
        return None
    if time.time() - entry["time"] > CACHE_TTL:
        del CACHE[query]
        return None
    return entry["data"]


def set_cache(query, data):
    CACHE[query] = {
        "time": time.time(),
        "data": data
    }


# -----------------------------
# SOURCE 1: RapidAPI (example)
# -----------------------------
def fetch_from_rapidapi(query):
    try:
        url = "https://example-ebay-api.p.rapidapi.com/search"

        headers = {
            "X-RapidAPI-Key": "YOUR_RAPIDAPI_KEY"
        }

        params = {"query": query}

        res = requests.get(url, headers=headers, params=params, timeout=5)
        data = res.json()

        prices = []
        for item in data.get("results", []):
            price = item.get("price")
            if price:
                prices.append(float(price))

        return prices

    except:
        return []


# -----------------------------
# SOURCE 2: eBay SOLD SCRAPE
# (use carefully, fallback only)
# -----------------------------
def fetch_from_scrape(query):
    try:
        url = f"https://www.ebay.com/sch/i.html?_nkw={query}&LH_Sold=1&LH_Complete=1"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")

        prices = []

        for tag in soup.select(".s-item__price"):
            text = tag.get_text().replace("$", "").replace(",", "")
            try:
                value = float(text.split()[0])
                prices.append(value)
            except:
                continue

        return prices

    except:
        return []


# -----------------------------
# CLEAN + CALCULATE
# -----------------------------
def clean_prices(prices):
    if len(prices) < 3:
        return prices

    prices.sort()

    # remove top/bottom 20% (outliers)
    trim = int(len(prices) * 0.2)
    if trim > 0:
        prices = prices[trim:-trim]

    return prices


def calculate(prices):
    if not prices:
        return None

    prices = clean_prices(prices)

    median = int(statistics.median(prices))
    low = int(min(prices))
    high = int(max(prices))

    return {
        "estimated_value": f"${median}",
        "range": f"${low} - ${high}",
        "sales_found": len(prices)
    }


# -----------------------------
# MAIN ESTIMATION LOGIC
# -----------------------------
def estimate_price(query):
    # 1. Check cache
    cached = get_cached(query)
    if cached:
        return cached

    # 2. Fetch from multiple sources
    prices = []

    # Primary source
    prices += fetch_from_rapidapi(query)

    # Fallback if not enough data
    if len(prices) < 5:
        prices += fetch_from_scrape(query)

    # 3. Calculate
    result = calculate(prices)

    if not result:
        result = {
            "estimated_value": "N/A",
            "range": "N/A",
            "sales_found": 0
        }

    # 4. Cache result
    set_cache(query, result)

    return result


# -----------------------------
# API ROUTE
# -----------------------------
@app.route("/search")
def search():
    query = request.args.get("q")

    if not query:
        return jsonify({"error": "Missing query"}), 400

    result = estimate_price(query)
    return jsonify(result)


# -----------------------------
# HEALTH CHECK
# -----------------------------
@app.route("/")
def home():
    return "Hybrid pricing API running"


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
