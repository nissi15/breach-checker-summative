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

if __name__ == "__main__":
    app.run(debug=True)
