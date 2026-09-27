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

def fetch_basketball_odds():
    if not ODDS_API_KEY:
        send_telegram_msg("⚠️ *KLAIDA:* `ODDS_API_KEY` nėra pridėtas prie GitHub Secrets!")
        return []

    # Gauti visas šiuo metu aktyvias krepšinio lygas
    sports_url = f"https://api.the-odds-api.com/v4/sports?apiKey={ODDS_API_KEY}"
    matches = []

    try:
        s_res = requests.get(sports_url, timeout=10)
        if s_res.status_code != 200:
            send_telegram_msg(f"⚠️ *API klaida ({s_res.status_code}):* Patikrinkite, ar teisingas API raktas.")
            return []

        all_sports = s_res.json()
        b_sports = [s["key"] for s in all_sports if s.get("group") == "Basketball"]

        if not b_sports:
            send_telegram_msg("ℹ️ Šiuo metu API neturi jokių aktyvių krepšinio lygų.")
            return []

        for sport_key in b_sports:
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
            params = {
                "apiKey": ODDS_API_KEY,
                "regions": "eu,us",
                "markets": "totals",
                "oddsFormat": "decimal"
            }

            res = requests.get(url, params=params, timeout=10)
            if res.status_code == 200:
                events = res.json()
                for ev in events:
                    home = ev.get("home_team")
                    away = ev.get("away_team")
                    sport_title = ev.get("sport_title", "KREPŠINIS")

                    bookmakers = ev.get("bookmakers", [])
                    if not bookmakers:
                        continue

                    bm = bookmakers[0]
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

                                matches.append({
                                    "league": f"🏀 {str(sport_title).upper()}",
                                    "match": f"{home} vs {away}",
                                    "line": line,
                                    "over_odds": over_odds,
                                    "under_odds": under_odds
                                })
                                break
    except Exception as e:
        print("Klaida:", e)

    return matches

def run_agent():
    today_date = datetime.now().strftime("%Y-%m-%d")
    matches = fetch_basketball_odds()

    if not matches and ODDS_API_KEY:
        send_telegram_msg(f"ℹ️ *{today_date}:* API užklausa pavyko, bet šiuo metu krepšinio rungtynėse nėra pateiktų Over/Under ribų.")
        return

    if not matches:
        return

    full_report = f"🏀 *KREPŠINIO PASIŪLA IR PROGNOZĖS ({today_date})*\n"
    full_report += f"Surasta mačų: *{len(matches)}*\n"
    full_report += "───────────────────────────\n\n"

    for m in matches:
        sims = 10000
        home_exp = m["line"] / 2 + random.uniform(-1.5, 2.0)
        away_exp = m["line"] / 2 + random.uniform(-2.0, 1.5)
        
        h, a = simulate_basketball_game(home_exp, away_exp, sims)
        totals = [x + y for x, y in zip(h, a)]

        prob_over = sum(1 for t in totals if t > m["line"]) / sims
        prob_under = sum(1 for t in totals if t < m["line"]) / sims

        val_over = (prob_over * m["over_odds"]) - 1
        val_under = (prob_under * m["under_odds"]) - 1

        full_report += f"🏆 *Lyga:* {m['league']}\n"
        full_report += f"⚔️ *Rungtynės:* {m['match']}\n"
        full_report += f"📊 Prognozuojama: *{home_exp + away_exp:.1f}* | Riba: *{m['line']}*\n"

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
