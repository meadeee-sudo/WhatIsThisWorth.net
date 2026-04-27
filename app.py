from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import time
import statistics
from bs4 import BeautifulSoup
import re

app = Flask(__name__)
CORS(app)

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
# CATEGORY DETECTION
# -----------------------------
def detect_category(q):
    q = q.lower()

    if any(x in q for x in ["iphone", "ipad", "macbook", "samsung", "laptop"]):
        return "electronics"

    if any(x in q for x in ["nike", "air jordan", "adidas", "yeezy"]):
        return "sneakers"

    if any(x in q for x in ["lego", "pokemon", "funko"]):
        return "collectibles"

    return "general"


# -----------------------------
# PRICE PARSER
# -----------------------------
def parse_price(text):
    if not text:
        return None
    text = text.replace(",", "")
    match = re.findall(r"\d+\.?\d*", text)
    return float(match[0]) if match else None


# -----------------------------
# SCRAPER (EBAY SOLD)
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
            title = item.select_one(".s-item__title")
            price = item.select_one(".s-item__price")
            link = item.select_one("a.s-item__link")

            p = parse_price(price.get_text() if price else "")
            if not p:
                continue

            comps.append({
                "price": p,
                "title": title.get_text() if title else "",
                "url": link["href"] if link else None
            })

        return comps

    except:
        return []


# -----------------------------
# OUTLIER CLEANING
# -----------------------------
def clean_prices(prices):
    if len(prices) < 8:
        return prices

    prices.sort()
    low = int(len(prices) * 0.12)
    high = int(len(prices) * 0.88)

    return prices[low:high]


# -----------------------------
# WEIGHTING MODEL
# -----------------------------
def weight(comp):
    title = comp["title"].lower()
    w = 1.0

    if "new" in title:
        w *= 1.1
    if "used" in title:
        w *= 0.95
    if "for parts" in title or "not working" in title:
        w *= 0.4

    return w


# -----------------------------
# HISTOGRAM
# -----------------------------
def build_histogram(prices):
    if not prices:
        return []

    min_p = min(prices)
    max_p = max(prices)

    bins = 5
    step = (max_p - min_p) / bins if max_p > min_p else 1

    hist = [0] * bins

    for p in prices:
        idx = min(int((p - min_p) / step), bins - 1)
        hist[idx] += 1

    return hist


# -----------------------------
# ACCURACY SCORE
# -----------------------------
def accuracy(count):
    if count >= 30:
        return 95
    if count >= 15:
        return 85
    if count >= 8:
        return 70
    return 50


# -----------------------------
# CATEGORY ADJUSTMENT
# -----------------------------
def adjust(price, category):
    if category == "sneakers":
        return price * 1.05
    if category == "electronics":
        return price * 0.98
    if category == "collectibles":
        return price * 1.10
    return price


# -----------------------------
# MAIN CALCULATION
# -----------------------------
def calculate(comps, category):
    if len(comps) < 3:
        return None

    prices = []
    weighted_prices = []

    for c in comps:
        p = adjust(c["price"], category)
        w = weight(c)

        prices.append(p)
        weighted_prices.extend([p] * max(1, int(w * 10)))

    prices = clean_prices(prices)
    weighted_prices = clean_prices(weighted_prices)

    median = int(statistics.median(weighted_prices))
    low = int(min(prices))
    high = int(max(prices))

    p25 = int(statistics.median(prices[:len(prices)//2])) if prices else median
    p75 = int(statistics.median(prices[len(prices)//2:])) if prices else median

    return {
        "estimated_value": f"${median}",
        "range": f"${low} - ${high}",
        "valuation_band": {
            "min": low,
            "p25": p25,
            "median": median,
            "p75": p75,
            "max": high
        },
        "histogram": build_histogram(prices),
        "sales_found": len(comps),
        "confidence": "High" if len(comps) > 25 else "Medium" if len(comps) > 10 else "Low",
        "accuracy_score": accuracy(len(comps)),
        "comps": comps[:8]
    }


# -----------------------------
# ESTIMATOR
# -----------------------------
def estimate(query):
    cached = get_cached(query)
    if cached:
        return cached

    category = detect_category(query)

    comps = fetch_from_scrape(query)

    result = calculate(comps, category)

    if not result:
        result = {
            "estimated_value": "N/A",
            "range": "N/A",
            "sales_found": 0
        }

    set_cache(query, result)
    return result


# -----------------------------
# API
# -----------------------------
@app.route("/search")
def search():
    q = request.args.get("q")
    if not q:
        return jsonify({"error": "missing query"}), 400

    return jsonify(estimate(q))


@app.route("/")
def home():
    return "WhatIsThisWorth API running"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
