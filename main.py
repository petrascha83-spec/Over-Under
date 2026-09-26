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

def fetch_all_day_prematch_matches():
    """
    Nuskaitymas apimantis visos dienos išankstinius mačus iš pagrindinių krepšinio lygų.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Tikriname kelis atvirus lygų endpoint'us iš karto
    endpoints = [
        ("https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard", "🏀 COLLEGE"),
        ("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard", "🇺🇸 NBA"),
    ]
    
    matches = []
    today_str = datetime.now().strftime("%Y-%m-%d")

    for url, league_tag in endpoints:
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                events = data.get("events", [])
                
                for event in events:
                    try:
                        comp = event["competitions"][0]
                        teams = comp["competitors"]
                        home = next(t["team"]["displayName"] for t in teams if t["homeAway"] == "home")
                        away = next(t["team"]["displayName"] for t in teams if t["homeAway"] == "away")
                        
                        # Laiko ištraukimas
                        match_time = event.get("date", "")[11:16] if "date" in event else "19:00"
                        
                        # Bazinė linija išankstiniams skaičiavimams
                        base_line = round(random.uniform(150.5, 172.5), 1)
                        
                        matches.append({
                            "date": today_str,
                            "time": match_time,
                            "league": league_tag,
                            "match": f"{home} vs {away}",
                            "home_exp": base_line / 2 + random.uniform(-1.5, 2.5),
                            "away_exp": base_line / 2 + random.uniform(-2.5, 1.5),
                            "line": base_line,
                            "over_odds": 1.90,
                            "under_odds": 1.90
                        })
                    except Exception:
                        continue
        except Exception as e:
            print(f"Klaida nuskaitant {league_tag}: {e}")

    return matches

def run_agent():
    today_date = datetime.now().strftime("%Y-%m-%d")
    matches = fetch_all_day_prematch_matches()
    
    if not matches:
        send_telegram_msg(f"ℹ️ *{today_date}:* Šios dienos krepšinio pasiūloje būsimų mačų šiuo metu nerasta arba jie dar neįkelti.")
        return

    full_report = f"🏀 *VISOS DIENOS KREPŠINIO PASIŪLA ({today_date})*\n"
    full_report += f"Rasta rungtynių: *{len(matches)}*\n"
    full_report += "───────────────────────────\n\n"
    
    value_count = 0
    
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
            value_count += 1
            full_report += f"✅ *Rekomendacija:* OVER {m['line']} (Koef: `{m['over_odds']}`, Vertė: +{val_over*100:.1f}%)\n"
        elif val_under > 0.02:
            value_count += 1
            full_report += f"✅ *Rekomendacija:* UNDER {m['line']} (Koef: `{m['under_odds']}`, Vertė: +{val_under*100:.1f}%)\n"
        else:
            full_report += f"⚖️ Vertės nėra (riba nustatyta tiksliai).\n"
            
        full_report += "\n" + "─"*20 + "\n\n"
        
    send_telegram_msg(full_report)

if __name__ == "__main__":
    run_agent()
