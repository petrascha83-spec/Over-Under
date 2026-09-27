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
        print(message)
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

def fetch_real_live_odds():
    if not ODDS_API_KEY:
        print("Trūksta ODDS_API_KEY paslaptyje.")
        return []

    # Jungiamės prie visų krepšinio lygų koeficientų
    url = f"https://api.the-odds-api.com/v4/sports/basketball/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=totals&oddsFormat=decimal"
    matches = []
    today_str = datetime.now().strftime("%Y-%m-%d")

    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            events = res.json()
            for event in events:
                home = event.get("home_team")
                away = event.get("away_team")
                sport_title = event.get("sport_title", "Krepšinis")
                commence_time = event.get("commence_time", "")[11:16]

                bookmakers = event.get("bookmakers", [])
                if not bookmakers:
                    continue
                
                totals_market = next((m for m in bookmakers[0].get("markets", []) if m["key"] == "totals"), None)
                if not totals_market:
                    continue

                outcomes = totals_market.get("outcomes", [])
                over_obj = next((o for o in outcomes if o["name"] == "Over"), None)
                under_obj = next((o for o in outcomes if o["name"] == "Under"), None)

                if over_obj and under_obj:
                    line = over_obj.get("point", 160.0)
                    over_odds = over_obj.get("price", 1.90)
                    under_odds = under_obj.get("price", 1.90)

                    matches.append({
                        "date": today_str,
                        "time": commence_time,
                        "league": f"🏀 {sport_title.upper()}",
                        "match": f"{home} vs {away}",
                        "home_exp": line / 2 + random.uniform(-1.5, 2.0),
                        "away_exp": line / 2 + random.uniform(-2.0, 1.5),
                        "line": line,
                        "over_odds": over_odds,
                        "under_odds": under_odds
                    })
    except Exception as e:
        print("Klaida traukiant gyvus duomenis:", e)

    return matches

def run_agent():
    today_date = datetime.now().strftime("%Y-%m-%d")
    matches = fetch_real_live_odds()

    if not matches:
        send_telegram_msg(f"ℹ️ *{today_date}:* Būsimų mačų su lažybų ribomis šiuo metu pasiūloje nerasta.")
        return

    full_report = f"🏀 *TIKROS ŠIOS DIENOS RUNGTYNĖS IR PROGNOZĖS ({today_date})*\n"
    full_report += f"Išanalizuota mačų: *{len(matches)}*\n"
    full_report += "───────────────────────────\n\n"

    for m in matches:
        sims = 10000
        h, a = simulate_basketball_game(m["home_exp"], m["away_exp"], sims)
        totals = [x + y for x, y in zip(h, a)]

        prob_over = sum(1 for t in totals if t > m["line"]) / sims
        prob_under = sum(1 for t in totals if t < m["line"]) / sims

        val_over = (prob_over * m["over_odds"]) - 1
        val_under = (prob_under * m["under_odds"]) - 1

        full_report += f"⏰ *Laikas:* {m['time']} | 🏆 *Lyga:* {m['league']}\n"
        full_report += f"⚔️ *Rungtynės:* {m['match']}\n"
        full_report += f"📊 Prognozuojamas totalas: *{m['home_exp'] + m['away_exp']:.1f}* | Riba: *{m['line']}*\n"

        if val_over > 0.02:
            full_report += f"✅ *PROGNOZĖ:* OVER {m['line']} (Koef: `{m['over_odds']}`, Vertė: +{val_over*100:.1f}%)\n"
        elif val_under > 0.02:
            full_report += f"✅ *PROGNOZĖ:* UNDER {m['line']} (Koef: `{m['under_odds']}`, Vertė: +{val_under*100:.1f}%)\n"
        else:
            full_report += f"⚖️ *Riba nustatyta tiksliai (vertės nėra).*\n"

        full_report += "\n" + "─"*20 + "\n\n"

    send_telegram_msg(full_report)

if __name__ == "__main__":
    run_agent()
