import math
import random
import os
import requests
from datetime import datetime, timezone, timedelta

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Trūksta Telegram kintamųjų.")
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

def get_active_basketball_sports():
    if not ODDS_API_KEY:
        return []
    url = f"https://api.the-odds-api.com/v4/sports/?apiKey={ODDS_API_KEY}"
    try:
        res = requests.get(url, timeout=8)
        if res.status_code == 200:
            sports = res.json()
            # Paimame visas krepšinio lygas
            return [s["key"] for s in sports if s.get("group") == "Basketball"]
    except Exception as e:
        print("Klaida gaunant lygas:", e)
    return ["basketball_euroleague", "basketball_spain_acb", "basketball_germany_bbl"]

def fetch_today_odds():
    sports = get_active_basketball_sports()
    matches = []

    now = datetime.now(timezone.utc)
    end_of_day = now + timedelta(hours=20) # Tikriname artimiausias 20 valandų (šios dienos mačus)

    for sport_key in sports:
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "eu,us",
            "markets": "totals",
            "oddsFormat": "decimal"
        }

        try:
            res = requests.get(url, params=params, timeout=8)
            if res.status_code == 200:
                events = res.json()
                for ev in events:
                    # Tikriname rungtynių laiką – paliekame TIK šios dienos
                    commence_time_str = ev.get("commence_time")
                    if commence_time_str:
                        match_time = datetime.fromisoformat(commence_time_str.replace("Z", "+00:00"))
                        if not (now <= match_time <= end_of_day):
                            continue # Praleidžiame mačus, kurie vyks po kelių dienų

                    home = ev.get("home_team")
                    away = ev.get("away_team")
                    sport_title = ev.get("sport_title", "KREPŠINIS")

                    bookmakers = ev.get("bookmakers", [])
                    if not bookmakers:
                        continue

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
                                        local_time = match_time.strftime("%H:%M") if commence_time_str else ""
                                        matches.append({
                                            "league": f"🏀 {str(sport_title).upper()}",
                                            "match": match_name,
                                            "time": local_time,
                                            "line": line,
                                            "over_odds": over_odds,
                                            "under_odds": under_odds
                                        })
                                    break
        except Exception as e:
            print(f"Klaida imant {sport_key}:", e)

    return matches

def run_agent():
    today_date = datetime.now().strftime("%Y-%m-%d")
    matches = fetch_today_odds()

    if not matches:
        send_telegram_msg(f"ℹ️ *{today_date}:* Šios dienos krepšinio pasiūloje aktyvių mačų su Over/Under ribomis nerasta.")
        return

    full_report = f"🔥 *ŠIOS DIENOS KREPŠINIO PROGNOZĖS ({today_date})*\n"
    full_report += f"Rasta šios dienos mačų: *{len(matches)}*\n"
    full_report += "───────────────────────────\n\n"

    for m in matches:
        sims = 10000
        base_exp = m["line"] / 2
        home_exp = base_exp + random.uniform(-1.5, 1.8)
        away_exp = base_exp + random.uniform(-1.8, 1.5)
        
        h, a = simulate_basketball_game(home_exp, away_exp, sims)
        totals = [x + y for x, y in zip(h, a)]

        prob_over = sum(1 for t in totals if t > m["line"]) / sims
        prob_under = sum(1 for t in totals if t < m["line"]) / sims

        val_over = (prob_over * m["over_odds"]) - 1
        val_under = (prob_under * m["under_odds"]) - 1

        proj_total = sum(totals) / sims
        time_str = f"| 🕒 `{m['time']}`" if m['time'] else ""

        full_report += f"🏆 *{m['league']}* {time_str}\n"
        full_report += f"⚔️ *{m['match']}*\n"
        full_report += f"📊 Riba: *{m['line']}* | Prognozuojama: *{proj_total:.1f}*\n"

        if val_over >= val_under and val_over > 0:
            full_report += f"🎯 *REKOMENDACIJA:* **OVER {m['line']}** (Koef: `{m['over_odds']}`, Vertė: +{val_over*100:.1f}%)\n"
        elif val_under > 0:
            full_report += f"🎯 *REKOMENDACIJA:* **UNDER {m['line']}** (Koef: `{m['under_odds']}`, Vertė: +{val_under*100:.1f}%)\n"
        else:
            full_report += f"⚖️ *Riba nustatyta tiksliai.*\n"

        full_report += "\n" + "─"*20 + "\n\n"

    send_telegram_msg(full_report)

if __name__ == "__main__":
    run_agent()
