# uses 3 api HIBP and onetime secret: for sharing password links and hacked sites
import os
import re
import time
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)

hibp_base = "https://haveibeenpwned.com/api/v3"
pwned_base = "https://api.pwnedpasswords.com"

ots_region = os.getenv("OTS_REGION", "us")
ots_base = f"https://{ots_region}.onetimesecret.com/api/v1"
ots_username = os.getenv("OTS_USERNAME", "")
ots_api_key = os.getenv("OTS_API_KEY", "")

server_name = os.getenv("SERVER_NAME", "local")

# HIBP asks every app to say who it is
headers = {"User-Agent": "breachcheck-student-project"}
timeout = 10

cache = {"breaches": None, "saved_at": 0}
cache_time = 6 * 60 * 60

# a link can stay for 1 min to 7 days
min_ttl = 60
max_ttl = 7 * 24 * 60 * 60
max_secret_length = 500

# === shows pages: 2 tabs and cover card for the pages ===
@app.route("/")
def home():
    return render_template("index.html", server_name=server_name)

@app.route("/secret/<secret_key>")
def secret_page(secret_key):
    return render_template("index.html", server_name=server_name)

@app.route("/health")
def health():
    return {"status": "ok"}

@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    # never send our secret links to other websites
    response.headers["Referrer-Policy"] = "no-referrer"
    # blocks XSS
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self'"
    )

    if request.path.startswith("/secret") or request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Served-By"] = server_name
    return response

# shows the list of hacked websites
def get_breaches():
    age = time.time() - cache["saved_at"]
    if cache["breaches"] is not None and age < cache_time:
        return cache["breaches"], "cache"

    try:
        response = requests.get(f"{hibp_base}/breaches",
                                headers=headers, timeout=timeout)
    except requests.exceptions.RequestException as error:
        print("GET breaches failed:", error)
        return None, "error"

    if response.status_code == 200:
        breaches = []
        for item in response.json(): #skips everything thats not a hacked site
            if (item.get("IsSpamList") or item.get("IsFabricated")
                    or item.get("IsSensitive") or item.get("IsMalware")
                    or item.get("IsStealerLog")):
                continue

            breaches.append({
                "name": item["Title"],
                "domain": item["Domain"],
                "date": item["BreachDate"],
                "added": item["AddedDate"][:10],
                "count": item["PwnCount"],
                "data": item["DataClasses"],
                "verified": item["IsVerified"],
            })
        cache["breaches"] = breaches
        cache["saved_at"] = time.time()
        return breaches, "api"
    else:
        print("GET breaches failed:", response.status_code)
        return None, "error"


@app.route("/api/breaches")
def breaches(): #send the hacked list to our app
    data, source = get_breaches()

    if data is not None:
        return jsonify({"breaches": data, "source": source})

    if cache["breaches"] is not None:
        return jsonify({"breaches": cache["breaches"], "source": "old-cache"})

    return jsonify({"error": "The breach service is down. "
                             "please try again in a minute."}), 503

if __name__ == "__main__":
    app.run(debug=True)
