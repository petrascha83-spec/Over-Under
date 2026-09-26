import math
import random
import os
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def simulate_basketball_game(expected_home_pts, expected_away_pts, simulations=10000):
    """
    Monte Karlo simuliacija su Puasono pasiskirstymu (Poisson distribution)
    """
    home_scores = []
    away_scores = []
    
    # 10 000 rungtynių simuliacija
    for _ in range(simulations):
        # Naudojamas Knuth algoritmas Puasono atsitiktiniams dydžiams generuoti
        home_pts = generate_poisson(expected_home_pts)
        away_pts = generate_poisson(expected_away_pts)
        home_scores.append(home_pts)
        away_scores.append(away_pts)
        
    return home_scores, away_scores

def generate_poisson(lam):
    """Generuoja Puasono atsitiktinį skaičių pagal lambda (tikėtinus taškus)"""
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1

def analyze_over_under(match_name, home_exp_pts, away_exp_pts, total_line, over_odds, under_odds):
    simulations = 10000
    home_scores, away_scores = simulate_basketball_game(home_exp_pts, away_exp_pts, simulations)
    
    totals = [h + a for h, a in zip(home_scores, away_scores)]
    
    over_count = sum(1 for t in totals if t > total_line)
    under_count = sum(1 for t in totals if t < total_line)
    
    prob_over = over_count / simulations
    prob_under = under_count / simulations
    
    # Tikriname matematinę vertę (Value = Tikimybė * Koeficientas - 1)
    value_over = (prob_over * over_odds) - 1
    value_under = (prob_under * under_odds) - 1
    
    exp_total = home_exp_pts + away_exp_pts
    
    report = f"🏀 *{match_name}*\n"
    report += f"📊 Modelio prognozuojami taškai: *{exp_total:.1f}* ({home_exp_pts:.1f} - {away_exp_pts:.1f})\n"
    report += f"🎯 TOPsport Riba: *{total_line}*\n\n"
    
    found_value = False
    
    if value_over > 0.03: # Jei matematinis pranašumas > 3%
        found_value = True
        report += f"✅ *VERTYBĖ: DAUGIAU (OVER {total_line})*\n"
        report += f"📈 Simuliacijos tikimybė: `{prob_over*100:.1f}%` (Bukmekerio: `{100/over_odds:.1f}%`)\n"
        report += f"💰 TOPsport Koeficientas: `{over_odds}` (Pranašumas: +{value_over*100:.1f}%)\n"
        
    elif value_under > 0.03:
        found_value = True
        report += f"✅ *VERTYBĖ: MAŽIAU (UNDER {total_line})*\n"
        report += f"📈 Simuliacijos tikimybė: `{prob_under*100:.1f}%` (Bukmekerio: `{100/under_odds:.1f}%`)\n"
        report += f"💰 TOPsport Koeficientas: `{under_odds}` (Pranašumas: +{value_under*100:.1f}%)\n"
    else:
        report += "⚖️ *Vertės nerasta* (Riba nustatyta labai tiksliai).\n"
        
    return report, found_value

# PRABANDYMAS SU PAVYZDINIU RUNGTYNIŲ SĄRAŠU
if __name__ == "__main__":
    # Pavyzdys: Žalgiris (prognozuojama 82.5) vs Monaco (prognozuojama 79.0)
    # TOPsport siūlo Over/Under 158.5 su koeficientais 1.90 / 1.90
    
    matches_to_check = [
        {
            "match": "Žalgiris vs Monaco",
            "home_exp": 83.4,
            "away_exp": 80.1,
            "line": 158.5,
            "over_odds": 1.95,
            "under_odds": 1.85
        },
        {
            "match": "Rytas vs Neptūnas",
            "home_exp": 89.0,
            "away_exp": 81.5,
            "line": 174.5,
            "over_odds": 1.85,
            "under_odds": 1.95
        }
    ]
    
    full_report = "🎲 *MONTE CARLO / POISSON OVER-UNDER ANALIZĖ*\n\n"
    
    for m in matches_to_check:
        rep, _ = analyze_over_under(
            m["match"], m["home_exp"], m["away_exp"], 
            m["line"], m["over_odds"], m["under_odds"]
        )
        full_report += rep + "\n" + "—"*20 + "\n\n"
        
    send_telegram_msg(full_report)
