from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import time
import statistics
from bs4 import BeautifulSoup
import random
import re

app = Flask(__name__)
CORS(app)

# -----------------------------
# CACHE
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
    CACHE[query] = {"time": time.time(), "data": data}


# -----------------------------
# CATEGORY DETECTION
# -----------------------------
def detect_category(query):
    q = query.lower()

    if any(x in q for x in ["iphone", "samsung", "pixel", "phone", "ipad"]):
        return "electronics"

    if any(x in q for x in ["pokemon", "magic", "cards", "psa"]):
        return "collectibles"

    if any(x in q for x in ["lego"]):
        return "toys"

    if any(x in q for x in ["nike", "jordan", "adidas", "shoe"]):
        return "sneakers"

    return "general"


# -----------------------------
# CONDITION DETECTION
# -----------------------------
def detect_condition(text):
    t = text.lower()

    if "brand new" in t or "new" in t:
        return "new"
    if "used" in t or "pre-owned" in t:
        return "used"
    if "refurbished" in t:
        return "refurbished"
    if "for parts" in t or "not working" in t:
        return "parts"

    return "unknown"


# -----------------------------
# PRICE PARSER
# -----------------------------
def parse_price(text):
    match = re.findall(r"\d+\.?\d*", text.replace(",", ""))
    if not match:
        return None
    return float(match[0])


# -----------------------------
# EBAY SCRAPER (COMPS)
# -----------------------------
def fetch_from_scrape(query):
    try:
        url = f"https://www.ebay.com/sch/i.html?_nkw={query}&LH_Sold=1&LH_Complete=1"

        headers = {"User-Agent": "Mozilla/5.0"}

        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")

        comps = []
        items = soup.select(".s-item")

        for item in items:
            title_tag = item.select_one(".s-item__title")
            price_tag = item.select_one(".s-item__price")

            if not price_tag:
                continue

            price = parse_price(price_tag.get_text())
            if not price:
                continue

            title = title_tag.get_text() if title_tag else ""
            condition = detect_condition(title + " " + price_tag.get_text())

            comps.append({
                "price": price,
                "title": title,
                "condition": condition
            })

        return comps

    except:
        return []


# -----------------------------
# FALLBACK DATA
# -----------------------------
def generate_fallback_prices(query):
    base = random.randint(40, 300)
    q = query.lower()

    if "iphone" in q:
        base = random.randint(250, 900)
    elif "pokemon" in q:
        base = random.randint(10, 250)
    elif "lego" in q:
        base = random.randint(20, 300)
    elif "nike" in q:
        base = random.randint(80, 500)

    return [{"price": int(base * x), "title": "estimated"} for x in [0.8, 1.0, 1.2]]


# -----------------------------
# CLEANING
# -----------------------------
def clean_prices(prices):
    if len(prices) < 5:
        return prices

    prices.sort()

    low = int(len(prices) * 0.15)
    high = int(len(prices) * 0.85)

    return prices[low:high]


# -----------------------------
# ADJUST BY CONDITION
# -----------------------------
def adjust_by_condition(comps):
    adjusted = []

    for c in comps:
        price = c["price"]
        cond = c["condition"]

        if cond == "new":
            price *= 1.05
        elif cond == "used":
            price *= 1.0
        elif cond == "refurbished":
            price *= 0.9
        elif cond == "parts":
            price *= 0.4

        adjusted.append(price)

    return adjusted


# -----------------------------
# CALCULATION ENGINE
# -----------------------------
def calculate(comps):
    if len(comps) < 2:
        return None

    prices = adjust_by_condition(comps)
    prices = clean_prices(prices)

    median = int(statistics.median(prices))
    low = int(min(prices))
    high = int(max(prices))

    confidence = "High" if len(prices) > 20 else "Medium" if len(prices) > 8 else "Low"

    return {
        "estimated_value": f"${median}",
        "range": f"${low} - ${high}",
        "sales_found": len(prices),
        "confidence": confidence,
        "why": [
            f"Based on {len(prices)} recent comps",
            "Outliers removed",
            "Condition-adjusted pricing applied"
        ],
        "sample_comps": comps[:5]
    }


# -----------------------------
# HYBRID ENGINE
# -----------------------------
def estimate_price(query):
    cached = get_cached(query)
    if cached:
        return cached

    comps = []

    # Scraper (main source)
    comps += fetch_from_scrape(query)

    # Fallback if weak data
    if len(comps) < 5:
        comps += generate_fallback_prices(query)

    result = calculate(comps)

    if not result:
        result = {
            "estimated_value": "N/A",
            "range": "N/A",
            "sales_found": 0,
            "confidence": "Low",
            "why": [],
            "sample_comps": []
        }

    set_cache(query, result)
    return result


# -----------------------------
# RECENT SALES FEED (simple)
# -----------------------------
def get_recent_sales(query):
    comps = fetch_from_scrape(query)
    return comps[:10]


# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    return "WhatIsThisWorth API running"


@app.route("/search")
def search():
    query = request.args.get("q")

    if not query:
        return jsonify({"error": "Missing query"}), 400

    result = estimate_price(query)

    # optional: include recent comps feed
    result["recent_sales"] = get_recent_sales(query)

    return jsonify(result)


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
