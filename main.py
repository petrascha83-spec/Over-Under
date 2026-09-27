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
        print("Klaida siunčiant į Telegram:", e)

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

def fetch_basketball_odds():
    if not ODDS_API_KEY:
        return []

    url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us,eu",
        "markets": "totals",
        "oddsFormat": "decimal"
    }

    matches = []
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            events = res.json()
            for ev in events:
                home = ev.get("home_team")
                away = ev.get("away_team")
                sport_title = ev.get("sport_title", "NBA")

                bookmakers = ev.get("bookmakers", [])
                if not bookmakers:
                    continue

                # Paimame pirmą turimą lažybų bendrovę su totals rinka
                for bm in bookmakers:
                    markets = bm.get("markets", [])
                    for m in markets:
                        if m.get("key") == "totals":
                            outcomes = m.get("outcomes", [])
                            over_obj = next((o for o in outcomes if o.get("name") == "Over"), None)
                            under_obj = next((o for o in outcomes if o.get("name") == "Under"), None)

                            if over_obj and under_obj:
                                line = float(over_obj.get("point", 0))
                                over_odds = float(over_obj.get("price", 1.85))
                                under_odds = float(under_obj.get("price", 1.85))

                                match_name = f"{home} vs {away}"
                                if not any(x["match"] == match_name for x in matches):
                                    matches.append({
                                        "league": f"🏀 {str(sport_title).upper()}",
                                        "match": match_name,
                                        "line": line,
                                        "over_odds": over_odds,
                                        "under_odds": under_odds
                                    })
                                break
    except Exception as e:
        print("Klaida imant duomenis:", e)

    return matches

def run_agent():
    today_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    matches = fetch_basketball_odds()

    if not matches:
        send_telegram_msg(f"ℹ️ *{today_date}:* Krepšinio mačų su pateiktomis Over/Under ribomis nerasta.")
        return

    full_report = f"🏀 *KREPŠINIO PASIŪLA IR PROGNOZĖS ({today_date})*\n"
    full_report += f"Išanalizuota mačų: *{len(matches)}*\n"
    full_report += "───────────────────────────\n\n"

    for m in matches[:10]:  # Rodyti pirmus 10 mačų, kad žinutė neviršytų Telegram limito
        sims = 10000
        home_exp = m["line"] / 2 + random.uniform(-1.5, 2.0)
        away_exp = m["line"] / 2 + random.uniform(-2.0, 1.5)
        
        h, a = simulate_basketball_game(home_exp, away_exp, sims)
        totals = [x + y for x, y in zip(h, a)]

        prob_over = sum(1 for t in totals if t > m["line"]) / sims
        prob_under = sum(1 for t in totals if t < m["line"]) / sims

        val_over = (prob_over * m["over_odds"]) - 1
        val_under = (prob_under * m["under_odds"]) - 1

        full_report += f"🏆 *{m['league']}*\n"
        full_report += f"⚔️ *{m['match']}*\n"
        full_report += f"📊 Riba: *{m['line']}* | Prognozuojama: *{home_exp + away_exp:.1f}*\n"

        if val_over > 0.01:
            full_report += f"✅ *PROGNOZĖ:* OVER {m['line']} (Koef: `{m['over_odds']}`, Vertė: +{val_over*100:.1f}%)\n"
        elif val_under > 0.01:
            full_report += f"✅ *PROGNOZĖ:* UNDER {m['line']} (Koef: `{m['under_odds']}`, Vertė: +{val_under*100:.1f}%)\n"
        else:
            full_report += f"⚖️ *Riba nustatyta tiksliai.*\n"

        full_report += "\n" + "─"*20 + "\n\n"

    send_telegram_msg(full_report)

if __name__ == "__main__":
    run_agent()
