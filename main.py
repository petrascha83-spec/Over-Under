import math
import random
import os
import requests
import json
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
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "lt-LT,lt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": "https://www.topsport.lt",
        "Referer": "https://www.topsport.lt/labybos/krepsinis"
    })

    # Skirtingi galimi TOPSPORT vidiniai maršrutai
    urls = [
        "https://www.topsport.lt/api/v1/sports/basketball/events",
        "https://www.topsport.lt/api/v1/events/highlights?sport=basketball"
    ]

    for url in urls:
        try:
            res = session.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                events = data.get("data", []) or data.get("events", []) or []
                
                for ev in events:
                    home = ev.get("home_team_name") or ev.get("homeTeam", {}).get("name") or "Komanda A"
                    away = ev.get("away_team_name") or ev.get("awayTeam", {}).get("name") or "Komanda B"
                    league = ev.get("competition_name") or ev.get("category", {}).get("name") or "TOPSPORT Krepšinis"
                    
                    # Tikriname maršrute esančias rinkas (markets)
                    markets = ev.get("markets", [])
                    for m in markets:
                        m_name = m.get("name", "").lower()
                        if "total" in m_name or "suminis" in m_name or "pranašumas" in m_name:
                            outcomes = m.get("outcomes", [])
                            over_obj = next((o for o in outcomes if "daugiau" in o.get("name", "").lower() or "over" in o.get("name", "").lower()), None)
                            under_obj = next((o for o in outcomes if "mažiau" in o.get("name", "").lower() or "under" in o.get("name", "").lower()), None)
                            
                            if over_obj and under_obj:
                                line = float(over_obj.get("handicap") or over_obj.get("point") or 160.5)
                                over_odds = float(over_obj.get("rate") or over_obj.get("price") or 1.85)
                                under_odds = float(under_obj.get("rate") or under_obj.get("price") or 1.85)

                                matches.append({
                                    "date": today_str,
                                    "time": "Pre-Match / Live",
                                    "league": f"🇱🇹 {league.upper()}",
                                    "match": f"{home} vs {away}",
                                    "home_exp": line / 2 + random.uniform(-1.5, 2.0),
                                    "away_exp": line / 2 + random.uniform(-2.0, 1.5),
                                    "line": line,
                                    "over_odds": over_odds,
                                    "under_odds": under_odds
                                })
                                break
                if matches:
                    break
        except Exception as e:
            print(f"Klaida skaitant {url}: {e}")

    return matches

def run_agent():
    today_date = datetime.now().strftime("%Y-%m-%d")
    matches = fetch_topsport_basketball()

    if not matches:
        send_telegram_msg(f"ℹ️ *{today_date}:* TOPSPORT apsauga užblokavo GitHub Cloud užklausą arba šią akimirką pasiūloje nėra krepšinio suminių (Over/Under) ribų.")
        return

    full_report = f"🏀 *TOPSPORT KREPŠINIO PASIŪLA IR PROGNOZĖS ({today_date})*\n"
    full_report += f"Rasta ir išanalizuota mačų: *{len(matches)}*\n"
    full_report += "───────────────────────────\n\n"

    for m in matches:
        sims = 10000
        h, a = simulate_basketball_game(m["home_exp"], m["away_exp"], sims)
        totals = [x + y for x, y in zip(h, a)]

        prob_over = sum(1 for t in totals if t > m["line"]) / sims
        prob_under = sum(1 for t in totals if t < m["line"]) / sims

        val_over = (prob_over * m["over_odds"]) - 1
        val_under = (prob_under * m["under_odds"]) - 1

        full_report += f"⏰ *Būsena:* {m['time']} | 🏆 *Lyga:* {m['league']}\n"
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
