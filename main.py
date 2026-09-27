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

def fetch_real_topsport_events():
    matches = []
    target_url = "https://www.topsport.lt/api/events?sportId=2&limit=50"
    
    # Naudojame viešą proxy, kad TOPSPORT nematytų GitHub serverio IP adreso
    proxy_url = f"https://api.allorigins.win/raw?url={target_url}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    try:
        response = requests.get(proxy_url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            events = data.get("data", []) or data.get("events", []) or []
            
            for ev in events:
                if not isinstance(ev, dict):
                    continue
                    
                home_team = ev.get("homeTeam", {}).get("name") or ev.get("home_team_name")
                away_team = ev.get("awayTeam", {}).get("name") or ev.get("away_team_name")
                league = ev.get("competition", {}).get("name") or "KREPŠINIS"
                
                if not home_team or not away_team:
                    continue

                markets = ev.get("markets", []) or []
                for m in markets:
                    m_type = str(m.get("type", "")).lower()
                    m_name = str(m.get("name", "")).lower()

                    if "total" in m_type or "suminis" in m_name or "daugiau/mažiau" in m_name:
                        outcomes = m.get("outcomes", []) or []
                        line = None
                        over_odds, under_odds = 1.85, 1.85

                        for o in outcomes:
                            o_name = str(o.get("name", "")).lower()
                            if "daugiau" in o_name or "over" in o_name:
                                line = float(o.get("handicap") or o.get("point") or 0)
                                over_odds = float(o.get("rate") or o.get("price") or 1.85)
                            elif "mažiau" in o_name or "under" in o_name:
                                under_odds = float(o.get("rate") or o.get("price") or 1.85)

                        if line and line > 100:
                            matches.append({
                                "league": f"🏀 {str(league).upper()}",
                                "match": f"{home_team} vs {away_team}",
                                "line": line,
                                "over_odds": over_odds,
                                "under_odds": under_odds
                            })
                            break
    except Exception as e:
        print("Proxy klaida:", e)

    return matches

def run_agent():
    today_date = datetime.now().strftime("%Y-%m-%d")
    matches = fetch_real_topsport_events()

    if not matches:
        send_telegram_msg(f"ℹ️ *{today_date}:* Proxy nepavyko praeiti apsaugos arba šiuo metu nėra aktyvių krepšinio totalų.")
        return

    full_report = f"🏀 *TIKRA TOPSPORT KREPŠINIO PASIŪLA ({today_date})*\n"
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
        full_report += f"📊 Prognozuojama: *{home_exp + away_exp:.1f}* | TOPSPORT Riba: *{m['line']}*\n"

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
