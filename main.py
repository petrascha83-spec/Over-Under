import math
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

def fetch_all_basketball_sports():
    if not ODDS_API_KEY:
        return []
    url = f"https://api.the-odds-api.com/v4/sports/?apiKey={ODDS_API_KEY}"
    try:
        res = requests.get(url, timeout=8)
        if res.status_code == 200:
            sports = res.json()
            # Dinamiškai paimame VISAS krepšinio lygas iš API
            return [s["key"] for s in sports if s.get("group") == "Basketball"]
    except Exception as e:
        print("Klaida gaunant lygų sąrašą:", e)
    return ["basketball_nba", "basketball_wnba", "basketball_euroleague", "basketball_spain_acb", "basketball_germany_bbl"]

def fetch_today_odds():
    b_sports = fetch_all_basketball_sports()
    matches = []
    
    # Tikriname šios dienos mačus (20 valandų langas nuo dabar)
    now = datetime.now(timezone.utc)
    end_of_day = now + timedelta(hours=20)

    for sport_key in b_sports:
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "eu,uk,us", # Skaityti visų regionų bukmeikerius
            "markets": "totals",
            "oddsFormat": "decimal"
        }

        try:
            res = requests.get(url, params=params, timeout=8)
            if res.status_code == 200:
                events = res.json()
                for ev in events:
                    commence_time_str = ev.get("commence_time")
                    if commence_time_str:
                        match_time = datetime.fromisoformat(commence_time_str.replace("Z", "+00:00"))
                        if not (now <= match_time <= end_of_day):
                            continue # Praleidžiame kitų dienų mačus

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

def analyze_match(line, over_odds, under_odds):
    # Deterministinė/stabili vertės apskaičiavimo metodika be atsitiktinių nuokrypių
    fair_prob_over = 1 / over_odds
    fair_prob_under = 1 / under_odds
    total_margin = fair_prob_over + fair_prob_under
    
    no_margin_over = fair_prob_over / total_margin
    no_margin_under = fair_prob_under / total_margin

    val_over = (no_margin_over * over_odds) - 1
    val_under = (no_margin_under * under_odds) - 1

    return val_over, val_under

def run_agent():
    today_date = datetime.now().strftime("%Y-%m-%d")
    matches = fetch_today_odds()

    if not matches:
        send_telegram_msg(f"ℹ️ *{today_date}:* Šios dienos pasiūloje aktyvių mačų su Over/Under ribomis visose lygose nerasta.")
        return

    full_report = f"🔥 *ŠIOS DIENOS KREPŠINIO PROGNOZĖS ({today_date})*\n"
    full_report += f"Surasta šios dienos mačų (visos lygos): *{len(matches)}*\n"
    full_report += "───────────────────────────\n\n"

    for m in matches:
        val_over, val_under = analyze_match(m["line"], m["over_odds"], m["under_odds"])
        time_str = f"| 🕒 `{m['time']} UTC`" if m['time'] else ""

        full_report += f"🏆 *{m['league']}* {time_str}\n"
        full_report += f"⚔️ *{m['match']}*\n"
        full_report += f"📊 Total Riba: *{m['line']}*\n"
        full_report += f"🔹 Over `{m['line']}`: *{m['over_odds']}* | Under `{m['line']}`: *{m['under_odds']}*\n"

        if m['over_odds'] < m['under_odds']:
            full_report += f"🎯 *RINKOS TENDENCIJA:* **OVER {m['line']}**\n"
        elif m['under_odds'] < m['over_odds']:
            full_report += f"🎯 *RINKOS TENDENCIJA:* **UNDER {m['line']}**\n"
        else:
            full_report += f"⚖️ *Riba padalinta lygiai (50/50)*\n"

        full_report += "\n" + "─"*20 + "\n\n"

    send_telegram_msg(full_report)

if __name__ == "__main__":
    run_agent()
