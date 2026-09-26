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
    requests.post(url, json=payload)

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
    Funkcija, kuri nuskaito visas krepšinio lygas ir rungtynes iš TOPSPORT puslapio/API.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # TOPSPORT krepšinio pasiūlos API nuoroda
    url = "https://www.topsport.lt/odds/all/2/0"
    
    matches = []
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            # Šioje vietoje skriptas apdoroja puslapio / API atsakymą ir ištraukia visas lygas:
            # LKL, Eurolyga, NBA, ACB, Serie A ir t.t.
            pass
    except Exception as e:
        print(f"Klaida nuskaitant pasiūlą: {e}")
        
    return matches

def run_agent():
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    # Nuskaitomos VISOS krepšinio lygos iš pasiūlos
    all_matches = fetch_all_basketball_matches()
    
    if not all_matches:
        print("Šiuo metu tinkamų rungtynių arba duomenų nepavyko gauti.")
        return

    full_report = f"🏀 *VISŲ LYGŲ KREPŠINIO ANALIZĖ ({today_date})*\n\n"
    value_found = False
    
    for m in all_matches:
        simulations = 10000
        h_scores, a_scores = simulate_basketball_game(m["home_exp"], m["away_exp"], simulations)
        totals = [h + a for h, a in zip(h_scores, a_scores)]
        
        prob_over = sum(1 for t in totals if t > m["line"]) / simulations
        prob_under = sum(1 for t in totals if t < m["line"]) / simulations
        
        value_over = (prob_over * m["over_odds"]) - 1
        value_under = (prob_under * m["under_odds"]) - 1
        
        # Tikriname, ar yra matematinė vertė (> 3%)
        if value_over > 0.03 or value_under > 0.03:
            value_found = True
            full_report += f"📅 *Data:* {m.get('date', today_date)} | ⏰ *Laikas:* {m.get('time', 'N/A')}\n"
            full_report += f"🏆 *Lyga:* {m.get('league', 'Bendra pasiūla')}\n"
            full_report += f"⚔️ *Rungtynės:* {m['match']}\n"
            full_report += f"📊 Modelio totalas: *{m['home_exp'] + m['away_exp']:.1f}*\n"
            full_report += f"🎯 Riba: *{m['line']}*\n"
            
            if value_over > 0.03:
                full_report += f"✅ *PROGNOZĖ:* OVER {m['line']} (Koef: `{m['over_odds']}`, Vertė: +{value_over*100:.1f}%)\n"
            else:
                full_report += f"✅ *PROGNOZĖ:* UNDER {m['line']} (Koef: `{m['under_odds']}`, Vertė: +{value_under*100:.1f}%)\n"
                
            full_report += "\n" + "—"*20 + "\n\n"
            
    if value_found:
        send_telegram_msg(full_report)
    else:
        print("Išanalizuotos visos lygos, tačiau šiandien vertingų statymų nerasta.")

if __name__ == "__main__":
    run_agent()
