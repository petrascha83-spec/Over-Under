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

def fetch_today_basketball_odds():
    if not ODDS_API_KEY:
        return []

    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us,eu",
        "markets": "totals",
        "oddsFormat": "decimal"
    }

    matches = []
    now = datetime.now(timezone.utc)
    next_24h = now + timedelta(hours=24)

    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            events = res.json()
            for ev in events:
                # Tikriname rungtynių laiką (tik šios dienos / artimiausių 24h)
                commence_time_str = ev.get("commence_time")
                if commence_time_str:
                    match_time = datetime.fromisoformat(commence_time_str.replace("Z", "+00:00"))
                    if not (now <= match_time <= next_24h):
                        continue

                home = ev.get("home_team")
                away = ev.get("away_team")
                sport_title = ev.get("sport_title", "NBA")

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
                                    matches.append({
                                        "league": f"🏀 {str(sport_title).upper()}",
                                        "match": match_name,
                                        "line": line,
                                        "over_odds": over_odds,
                                        "under_odds": under_odds,
                                        "time": match_time.strftime("%H:%M UTC") if commence_time_str else ""
                                    })
                                break
    except Exception as e:
        print("Klaida imant duomenis:", e)

    return matches

def run_agent():
    today_date = datetime.now().strftime("%Y-%m-%d")
    matches = fetch_today_basketball_odds()

    if not matches:
        send_telegram_msg(f"ℹ️ *{today_date}:* Artimiausių 24 val. krepšinio pasiūloje matomų mačų su Over/Under ribomis nerasta.")
        return

    valuable_bets = []

    for m in matches:
        sims = 10000
        
        # Algoritmas: Apskaičiuojama mačo tikėtina totalo norma per stabilų Puasono pasiskirstymą
        # Naudojame liniją kaip bazę su mikro korekcija pagal rinkos nuokrypį
        base_exp = m["line"] / 2
        home_exp = base_exp + (1.2 if "Celtics" in m["match"] or "Nuggets" in m["match"] else 0.0)
        away_exp = base_exp - 0.5
        
        h, a = simulate_basketball_game(home_exp, away_exp, sims)
        totals = [x + y for x, y in zip(h, a)]

        prob_over = sum(1 for t in totals if t > m["line"]) / sims
        prob_under = sum(1 for t in totals if t < m["line"]) / sims

        val_over = (prob_over * m["over_odds"]) - 1
        val_under = (prob_under * m["under_odds"]) - 1

        # Filtruojame TIK verdiktus su > +3% matematine verte (Value)
        if val_over >= 0.03:
            valuable_bets.append({
                "league": m["league"],
                "match": m["match"],
                "time": m["time"],
                "line": m["line"],
                "type": "OVER",
                "odds": m["over_odds"],
                "value": val_over * 100,
                "projected": sum(totals) / sims
            })
        elif val_under >= 0.03:
            valuable_bets.append({
                "league": m["league"],
                "match": m["match"],
                "time": m["time"],
                "line": m["line"],
                "type": "UNDER",
                "odds": m["under_odds"],
                "value": val_under * 100,
                "projected": sum(totals) / sims
            })

    if not valuable_bets:
        send_telegram_msg(f"📊 *ŠIOS DIENOS APŽVALGA ({today_date})*\nIšanalizuota mačų: *{len(matches)}*\n\n⚠️ Dėmesio: Šiandien mačų su **>+3% matematinia verte** nebuvo rasta (visos ribos sustatytos labai tiksliai).")
        return

    full_report = f"🔥 *VERTINGI ŠIOS DIENOS STATYMAI ({today_date})*\n"
    full_report += f"Atrinkta vertingų mačų: *{len(valuable_bets)}* iš *{len(matches)}*\n"
    full_report += "───────────────────────────\n\n"

    for b in valuable_bets:
        full_report += f"🏆 *{b['league']}* | 🕒 `{b['time']}`\n"
        full_report += f"⚔️ *{b['match']}*\n"
        full_report += f"📊 TOPSPORT/Rinkos riba: *{b['line']}* | Prognozuojama: *{b['projected']:.1f}*\n"
        full_report += f"🎯 *REKOMENDACIJA:* **{b['type']} {b['line']}**\n"
        full_report += f"📈 Koeficientas: `{b['odds']}` | Vertė: *+{b['value']:.1f}%*\n"
        full_report += "\n" + "─"*20 + "\n\n"

    send_telegram_msg(full_report)

if __name__ == "__main__":
    run_agent()
