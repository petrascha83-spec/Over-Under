import math
import random
import os
import requests
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

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

def fetch_topsport_basketball():
    matches = []
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Topsport krepšinio pasiūlos srauto URL ir antraštės
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.topsport.lt/lažybos/krepšinis"
    }

    # TOPSPORT vidiniai krepšinio kategorijų endpointai
    url = "https://www.topsport.lt/api/v1/sports/basketball/events"

    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            events = data.get("data", []) or data.get("events", [])

            for ev in events:
                home = ev.get("home_team_name", "Komanda A")
                away = ev.get("away_team_name", "Komanda B")
                league = ev.get("competition_name", "TOPSPORT Krepšinis")
                match_time = ev.get("start_time", "")[11:16]

                # Iškrapštome Totalų (OVER/UNDER) rinką
                markets = ev.get("markets", [])
                totals_market = next((m for m in markets if "total" in m.get("name", "").lower() or "suminis" in m.get("name", "").lower()), None)

                if totals_market:
                    outcomes = totals_market.get("outcomes", [])
                    over_obj = next((o for o in outcomes if "daugiau" in o.get("name", "").lower() or "over" in o.get("name", "").lower()), None)
                    under_obj = next((o for o in outcomes if "mažiau" in o.get("name", "").lower() or "under" in o.get("name", "").lower()), None)

                    if over_obj and under_obj:
                        line = float(over_obj.get("handicap", 160.5))
                        over_odds = float(over_obj.get("rate", 1.85))
                        under_odds = float(under_obj.get("rate", 1.85))

                        matches.append({
                            "date": today_str,
                            "time": match_time if match_time else "Dienos mačas",
                            "league": f"🇱🇹 {league.upper()}",
                            "match": f"{home} vs {away}",
                            "home_exp": line / 2 + random.uniform(-1.5, 2.0),
                            "away_exp": line / 2 + random.uniform(-2.0, 1.5),
                            "line": line,
                            "over_odds": over_odds,
                            "under_odds": under_odds
                        })
    except Exception as e:
        print("Klaida skaitant Topsport duomenis:", e)

    return matches

def run_agent():
    today_date = datetime.now().strftime("%Y-%m-%d")
    matches = fetch_topsport_basketball()

    if not matches:
        send_telegram_msg(f"ℹ️ *{today_date}:* TOPSPORT krepšinio pre-match pasiūloje šiuo metu aktyvių totalų nerasta arba serveryje atliekami atnaujinimai.")
        return

    full_report = f"🏀 *TOPSPORT KREPŠINIO PASIŪLA IR PROGNOZĖS ({today_date})*\n"
    full_report += f"Atsiųsta mačų analizei: *{len(matches)}*\n"
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

        if val_over > 0.01:
            full_report += f"✅ *PROGNOZĖ:* OVER {m['line']} (Koef: `{m['over_odds']}`, Vertė: +{val_over*100:.1f}%)\n"
        elif val_under > 0.01:
            full_report += f"✅ *PROGNOZĖ:* UNDER {m['line']} (Koef: `{m['under_odds']}`, Vertė: +{val_under*100:.1f}%)\n"
        else:
            full_report += f"⚖️ *Riba nustatyta tiksliai (vertės nėra).*\n"

        full_report += "\n" + "─"*20 + "\n\n"

    send_telegram_msg(full_report)

if __name__ == "__main__":
    run_agent()
