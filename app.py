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
# SAFE REQUEST (FIXED + DEBUGGED)
# -----------------------------
def safe_get(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
        "Connection": "close"
    }

    print("🌐 REQUESTING:", url)

    for attempt in range(3):
        try:
            res = requests.get(url, headers=headers, timeout=10)
            print("🌐 STATUS:", res.status_code)
            return res

        except Exception as e:
            print(f"❌ REQUEST ERROR (attempt {attempt+1}):", repr(e))
            time.sleep(1)

    print("❌ ALL REQUEST ATTEMPTS FAILED")
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
# EBAY SOLD SCRAPER
# -----------------------------
def fetch_from_scrape(query):
    print("🔥 SCRAPER FUNCTION ENTERED")

    try:
        url = f"https://www.ebay.com/sch/i.html?_nkw={query}&LH_Sold=1&LH_Complete=1&_ipg=50"

        res = safe_get(url)

        if not res:
            print("❌ NO RESPONSE OBJECT")
            return []

        print("HTML SIZE:", len(res.text))
        print("HAS s-item:", "s-item" in res.text)

        soup = BeautifulSoup(res.text, "html.parser")

        comps = []

        items = soup.select("li.s-item")
        print("RAW ITEMS:", len(items))

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

            except Exception as e:
                print("ITEM PARSE ERROR:", e)
                continue

        print("VALID COMPS:", len(comps))

        return comps

    except Exception as e:
        print("SCRAPER CRASH:", repr(e))
        return []


# -----------------------------
# ESTIMATE
# -----------------------------
def estimate(query):
    cached = get_cached(query)
    if cached:
        return cached

    comps = fetch_from_scrape(query)

    if len(comps) == 0:
        result = {
            "debug": "no comps returned",
            "estimated_value": "N/A",
            "range": "N/A",
            "sales_found": 0,
            "comps": [],
            "confidence": "No data"
        }
        set_cache(query, result)
        return result

    prices = [c["price"] for c in comps]

    median = int(statistics.median(prices))
    low = int(min(prices))
    high = int(max(prices))

    comps_sorted = sorted(comps, key=lambda x: x["price"])

    result = {
        "debug": "success",
        "estimated_value": f"${median}",
        "range": f"${low} - ${high}",
        "sales_found": len(comps_sorted),

        "comps": [
            {
                "title": c["title"],
                "price": c["price"],
                "url": c["url"]
            }
            for c in comps_sorted[:20]
        ],

        "confidence": "Based on real sold listings"
    }

    set_cache(query, result)
    return result


# -----------------------------
# ROUTE DEBUG
# -----------------------------
@app.route("/search")
def search():
    print("🔥 SEARCH ROUTE HIT")

    q = request.args.get("q")
    print("QUERY RECEIVED:", q)

    result = estimate(q)

    print("🔥 FINAL RESULT KEYS:", list(result.keys()) if result else None)

    return jsonify(result)


# -----------------------------
# HEALTH CHECK
# -----------------------------
@app.route("/")
def home():
    return "WhatIsThisWorth - Sold Comps Engine Running"


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
