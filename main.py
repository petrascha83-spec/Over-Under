import math
import random
import os
import requests
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Trūksta Telegram Token arba Chat ID!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Klaida siunčiant žinutę:", e)

def generate_poisson(lam):
    L = math.exp(-lam)
    k, p = 0, 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1

def simulate_basketball_game(expected_home_pts, expected_away_pts, simulations=10000):
    home_scores, away_scores = [], []
    for _ in range(simulations):
        home_scores.append(generate_poisson(expected_home_pts))
        away_scores.append(generate_poisson(expected_away_pts))
    return home_scores, away_scores

def run_agent():
    today_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Pranešimas apie paleidimą
    send_telegram_msg(f"🚀 *BOTO PATIKRA PALEISTA ({today_date})*\nODDS_API_KEY rasta: `{'TAIP' if ODDS_API_KEY else 'NE'}`")

    if not ODDS_API_KEY:
        send_telegram_msg("⚠️ *Stabdoma:* `ODDS_API_KEY` nerastas tarp kintamųjų.")
        return

    # Užklausa į The Odds API
    try:
        url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={ODDS_API_KEY}&regions=us&markets=totals"
        res = requests.get(url, timeout=10)
        
        if res.status_code != 200:
            send_telegram_msg(f"⚠️ *API Klaida:* Kodas {res.status_code} - {res.text[:100]}")
            return

        data = res.json()
        send_telegram_msg(f"✅ *API Atsakas gautas sėkmingai!* Surasta NBA mačų pasiūloje: *{len(data)}*")

    except Exception as e:
        send_telegram_msg(f"💥 *Sisteminė klaida:* `{e}`")

if __name__ == "__main__":
    run_agent()
