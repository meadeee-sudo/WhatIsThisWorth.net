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

    if any(x in q for x in ["iphone", "ipad", "macbook", "samsung", "laptop", "apple watch"]):
        return "electronics"

    if any(x in q for x in ["nike", "air jordan", "adidas", "yeezy"]):
        return "sneakers"

    if any(x in q for x in ["lego", "pokemon", "funko", "card"]):
        return "collectibles"

    return "general"


# -----------------------------
# CONDITION DETECTION
# -----------------------------
def detect_condition(title):
    t = title.lower()

    if any(x in t for x in ["brand new", "new in box", "sealed"]):
        return "new"

    if "open box" in t:
        return "open_box"

    if any(x in t for x in ["used", "preowned", "pre-owned"]):
        return "used"

    if any(x in t for x in ["broken", "not working", "for parts"]):
        return "damaged"

    return "unknown"


# -----------------------------
# SAFE REQUEST
# -----------------------------
def safe_get(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
        "Connection": "keep-alive"
    }

    try:
        return requests.get(url, headers=headers, timeout=6)
    except:
        return None


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
# EBAY SCRAPER
# -----------------------------
def fetch_from_scrape(query):
    try:
        url = f"https://www.ebay.com/sch/i.html?_nkw={query}&LH_Sold=1&LH_Complete=1"

        res = safe_get(url)
        if not res or res.status_code != 200:
            return []

        html = res.text

        if "captcha" in html.lower() or "robot" in html.lower():
            return []

        soup = BeautifulSoup(html, "html.parser")

        comps = []
        items = soup.select(".s-item")

        for item in items:
            title_el = item.select_one(".s-item__title")
            price_el = item.select_one(".s-item__price")
            link_el = item.select_one("a.s-item__link")

            if not title_el or not price_el:
                continue

            title = title_el.get_text().strip()
            price = parse_price(price_el.get_text())

            if not title or not price:
                continue

            comps.append({
                "title": title,
                "price": price,
                "url": link_el["href"] if link_el else None
            })

        return comps

    except:
        return []


# -----------------------------
# FALLBACK
# -----------------------------
def fallback_simulated_comps(query):
    q = query.lower()

    base = 50

    if "iphone" in q:
        base = 450
    elif "nike" in q or "air jordan" in q:
        base = 120
    elif "lego" in q:
        base = 80
    elif "pokemon" in q:
        base = 60

    return [
        {"title": "Market fallback comp", "price": base * 0.9, "url": None},
        {"title": "Market fallback comp", "price": base, "url": None},
        {"title": "Market fallback comp", "price": base * 1.1, "url": None},
    ]


# -----------------------------
# COMP SCORING (ZILLOW CORE)
# -----------------------------
def comp_score(comp, query):
    title = comp["title"].lower()
    q = query.lower()

    score = 0

    for word in q.split():
        if word in title:
            score += 3

    condition = detect_condition(title)

    if condition == "new":
        score += 3
    elif condition == "open_box":
        score += 2
    elif condition == "used":
        score += 1
    elif condition == "damaged":
        score -= 3

    return score


# -----------------------------
# ADJUSTMENTS
# -----------------------------
def adjust(price, category):
    if category == "sneakers":
        return price * 1.06
    if category == "electronics":
        return price * 0.97
    if category == "collectibles":
        return price * 1.12
    return price


# -----------------------------
# CLEAN
# -----------------------------
def clean(prices):
    if len(prices) < 6:
        return prices

    prices.sort()
    trim = int(len(prices) * 0.1)
    return prices[trim:-trim]


# -----------------------------
# STABILITY
# -----------------------------
def stability(prices):
    if len(prices) < 5:
        return 50

    mean = statistics.mean(prices)
    variance = sum((x - mean) ** 2 for x in prices) / len(prices)

    if variance < mean * 0.05:
        return 90
    if variance < mean * 0.15:
        return 75
    return 55


# -----------------------------
# ACCURACY
# -----------------------------
def accuracy(count):
    if count >= 30:
        return 90
    if count >= 15:
        return 80
    if count >= 8:
        return 70
    return 55


# -----------------------------
# MAIN CALCULATION
# -----------------------------
def calculate(comps, query, category):
    if len(comps) < 3:
        return None

    # score comps
    for c in comps:
        c["score"] = comp_score(c, query)

    comps = sorted(comps, key=lambda x: x["score"], reverse=True)

    best = comps[:10]

    values = []
    weighted = []

    for c in best:
        p = adjust(c["price"], category)
        w = max(1, c["score"] + 1)

        values.append(p)
        weighted.extend([p] * w)

    values = clean(values)
    weighted = clean(weighted)

    median = int(statistics.median(weighted))

    low = int(min(values))
    high = int(max(values))

    confidence_score = 0

    avg_score = sum(c["score"] for c in best) / len(best)

    if len(best) >= 10:
        confidence_score += 40
    elif len(best) >= 5:
        confidence_score += 25
    else:
        confidence_score += 15

    if avg_score > 4:
        confidence_score += 40
    elif avg_score > 2:
        confidence_score += 25
    else:
        confidence_score += 10

    confidence = "High" if confidence_score >= 70 else "Medium" if confidence_score >= 40 else "Low"

    return {
        "estimated_value": f"${median}",
        "range": f"${low} - ${high}",
        "sales_found": len(comps),

        # Zillow-style comps
        "comps": [
            {
                "title": c["title"],
                "price": c["price"],
                "url": c["url"],
                "score": c["score"]
            }
            for c in best
        ],

        "confidence": confidence,
        "accuracy_score": accuracy(len(comps)),
        "stability_score": stability(values)
    }


# -----------------------------
# ESTIMATE
# -----------------------------
def estimate(query):
    cached = get_cached(query)
    if cached:
        return cached

    category = detect_category(query)

    comps = fetch_from_scrape(query)

    # ONLY fallback if no data
    if len(comps) == 0:
        comps = fallback_simulated_comps(query)

    result = calculate(comps, query, category)

    if not result:
        result = {
            "estimated_value": "N/A",
            "range": "N/A",
            "sales_found": 0,
            "confidence": "Low",
            "accuracy_score": 0,
            "stability_score": 0,
            "comps": []
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
