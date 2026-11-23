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

# == Password checks

@app.route("/api/password/<prefix>")
def password_check(prefix):
    #we only sends the first 5 characters of the SHA-1 hash, so passwords aren't seen'.
    
    if not re.fullmatch(r"[0-9A-Fa-f]{5}", prefix):
        return jsonify({"error": "Invalid hash prefix."}), 400

    try:
        response = requests.get(f"{pwned_base}/range/{prefix.upper()}",
                                headers=headers, timeout=timeout)
    except requests.exceptions.RequestException as error:
        print("GET password range failed:", error)
        return jsonify({"error": "The password service is not answering. "
                                 "Please try again."}), 503

    if response.status_code == 200:
        # each line looks like "SUFFIX:COUNT"
        results = {}
        for line in response.text.splitlines():
            suffix, count = line.split(":")
            results[suffix] = int(count)
        return jsonify({"results": results})
    elif response.status_code == 429:
        return jsonify({"error": "Too many checks. "
                                 "Wait a few seconds and try again."}), 429
    else:
        print("GET password range failed:", response.status_code)
        return jsonify({"error": "The password service had a problem. "
                                 "Please try again."}), 502


# == One time links

def ots_ready(): #checks api in the .env
    return ots_username != "" and ots_api_key != ""


@app.route("/api/share", methods=["POST"])
def share():
    if not ots_ready():
        return jsonify({"error": "Sharing is not set up on this server."}), 500

    data = request.get_json(silent=True) or {}
    secret = str(data.get("secret", "")).strip()
    ttl = data.get("ttl")

    if secret == "":
        return jsonify({"error": "Please type something to share."}), 400
    if len(secret) > max_secret_length:
        return jsonify({"error": "Keep it under 500 characters."}), 400
    if type(ttl) is not int or ttl < min_ttl or ttl > max_ttl:
        return jsonify({"error": "pick an expiry between 1 minute and 7 days."}), 400

    try:
        response = requests.post(f"{ots_base}/share",
                                 auth=(ots_username, ots_api_key),
                                 data={"secret": secret, "ttl": ttl},
                                 timeout=timeout)
    except requests.exceptions.RequestException as error:
        print("POST share failed:", error)
        return jsonify({"error": "The sharing service is not answering. "
                                 "please try again."}), 503

    if response.status_code == 200:
        result = response.json()
        return jsonify({"secret_key": result["secret_key"],
                        "metadata_key": result["metadata_key"]})
    elif response.status_code == 429:
        return jsonify({"error": "Too many links made. "
                                 "plz wait and try again."}), 429
    else:
        # do not show the real reason: it could mention our account
        print("POST share failed:", response.status_code)
        return jsonify({"error": "Cannot create the link now. "
                                 "please try again later."}), 502


@app.route("/api/reveal/<secret_key>", methods=["POST"])
def reveal(secret_key):
    if not re.fullmatch(r"[A-Za-z0-9]{8,64}", secret_key):
        return jsonify({"error": "This link is invalid."}), 400
    if not ots_ready():
        return jsonify({"error": "Sharing is not set up on this server."}), 500

    try:
        response = requests.post(f"{ots_base}/secret/{secret_key}",
                                 auth=(ots_username, ots_api_key),
                                 timeout=timeout)
    except requests.exceptions.RequestException as error:
        print("POST reveal failed:", error)
        return jsonify({"error": "The sharing service is not answering. "
                                 "Your secret is still safe, try again."}), 503

    if response.status_code == 200:
        return jsonify({"value": response.json()["value"]})
    elif response.status_code == 404:
        return jsonify({"error": "This secret was already viewed "
                                 "or has expired."}), 404
    else:
        print("POST reveal failed:", response.status_code)
        return jsonify({"error": "Could not open the secret. "
                                 "Please try again."}), 502


@app.route("/api/burn/<metadata_key>", methods=["POST"])
def burn(metadata_key):
    if not re.fullmatch(r"[A-Za-z0-9]{8,64}", metadata_key):
        return jsonify({"error": "This link is not valid."}), 400
    if not ots_ready():
        return jsonify({"error": "Sharing is not set up on this server."}), 500

    try:
        response = requests.post(f"{ots_base}/private/{metadata_key}/burn",
                                 auth=(ots_username, ots_api_key),
                                 timeout=timeout)
    except requests.exceptions.RequestException as error:
        print("POST burn failed:", error)
        return jsonify({"error": "The sharing service is not answering. "
                                 "Please try again."}), 503

    if response.status_code == 200:
        return jsonify({"burned": True})
    else:
        print("POST burn failed:", response.status_code)
        return jsonify({"error": "This link was already opened "
                                 "or deleted."}), 404

if __name__ == "__main__":
    app.run(debug=True)
