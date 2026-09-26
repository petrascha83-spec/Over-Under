import math
import random
import os
import requests
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram duomenys nerasti. Žinutė konsolėje:")
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload, timeout=10)
        print("Telegram atsakas:", res.status_code)
    except Exception as e:
        print("Klaida siunčiant žinutę į Telegram:", e)

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

def fetch_all_basketball_matches():
    """
    Rungtynių sąrašas apimantis skirtingas lygas (Eurolyga, LKL, NBA, Ispanija ACB).
    Kiekvienoms rungtynėms nurodyta data, laikas, lyga, prognozuojami taškai ir lažybų riba.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    matches = [
        {
            "date": today_str,
            "time": "19:00",
            "league": "🇪🇺 Eurolyga",
            "match": "Žalgiris vs Monaco",
            "home_exp": 80.5,
            "away_exp": 77.0,
            "line": 154.5,
            "over_odds": 1.90,
            "under_odds": 1.90
        },
        {
            "date": today_str,
            "time": "17:20",
            "league": "🇱🇹 LKL",
            "match": "Rytas vs Lietkabelis",
            "home_exp": 88.5,
            "away_exp": 82.0,
            "line": 166.5,
            "over_odds": 1.85,
            "under_odds": 1.95
        },
        {
            "date": today_str,
            "time": "21:30",
            "league": "🇪🇸 Ispanija ACB",
            "match": "Real Madrid vs Barcelona",
            "home_exp": 85.0,
            "away_exp": 81.5,
            "line": 169.5,
            "over_odds": 1.92,
            "under_odds": 1.88
        },
        {
            "date": today_str,
            "time": "02:30",
            "league": "🇺🇸 NBA",
            "match": "Boston Celtics vs Los Angeles Lakers",
            "home_exp": 116.5,
            "away_exp": 110.0,
            "line": 222.5,
            "over_odds": 1.90,
            "under_odds": 1.90
        }
    ]
    return matches

def run_agent():
    today_date = datetime.now().strftime("%Y-%m-%d")
    all_matches = fetch_all_basketball_matches()
    
    if not all_matches:
        print("Šiuo metu rungtynių sąrašas tuščias.")
        return

    full_report = f"🏀 *KREPŠINIO ANALIZĖ IR PROGNOZĖS ({today_date})*\n"
    full_report += "───────────────────────────\n\n"
    
    value_count = 0
    
    for m in all_matches:
        simulations = 10000
        h_scores, a_scores = simulate_basketball_game(m["home_exp"], m["away_exp"], simulations)
        totals = [h + a for h, a in zip(h_scores, a_scores)]
        
        prob_over = sum(1 for t in totals if t > m["line"]) / simulations
        prob_under = sum(1 for t in totals if t < m["line"]) / simulations
        
        value_over = (prob_over * m["over_odds"]) - 1
        value_under = (prob_under * m["under_odds"]) - 1
        
        full_report += f"📅 *Data:* {m['date']} | ⏰ *Laikas:* {m['time']}\n"
        full_report += f"🏆 *Lyga:* {m['league']}\n"
        full_report += f"⚔️ *Rungtynės:* {m['match']}\n"
        full_report += f"📊 Modelio prognozė: *{m['home_exp'] + m['away_exp']:.1f}* taškų\n"
        full_report += f"🎯 TOPsport Riba: *{m['line']}*\n"
        
        if value_over > 0.02:
            value_count += 1
            full_report += f"✅ *REKOMENDACIJA:* OVER {m['line']} (Koef: `{m['over_odds']}`, Vertė: +{value_over*100:.1f}%)\n"
        elif value_under > 0.02:
            value_count += 1
            full_report += f"✅ *REKOMENDACIJA:* UNDER {m['line']} (Koef: `{m['under_odds']}`, Vertė: +{value_under*100:.1f}%)\n"
        else:
            full_report += "⚖️ *Riba nustatyta tiksliai (matematinės vertės nėra).*\n"
            
        full_report += "\n" + "─"*25 + "\n\n"
        
    print(f"Išanalizuota {len(all_matches)} rungtynių. Rasta vertingų statymų: {value_count}")
    send_telegram_msg(full_report)

if __name__ == "__main__":
    run_agent()
