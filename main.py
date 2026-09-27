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
            return [s["key"] for s in sports if s.get("group") == "Basketball"]
    except Exception as e:
        print("Klaida gaunant lygų sąrašą:", e)
    return ["basketball_nba", "basketball_wnba", "basketball_euroleague", "basketball_spain_acb", "basketball_germany_bbl"]

def analyze_sharp_value_bets():
    b_sports = fetch_all_basketball_sports()
    safe_bets = []
    
    now = datetime.now(timezone.utc)
    end_of_day = now + timedelta(hours=24)

    # Identifikuojame tiksliausius / griežčiausius bukmekerius rinkoje ("Sharp")
    SHARP_BOOKMAKERS = ["pinnacle", "matchbook", "betfair_ex_eu", "1xbet"]

    for sport_key in b_sports:
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "eu,uk,us",
            "markets": "totals",
            "oddsFormat": "decimal"
        }

        try:
            res = requests.get(url, params=params, timeout=8)
            if res.status_code != 200:
                continue

            events = res.json()
            for ev in events:
                commence_time_str = ev.get("commence_time")
                if commence_time_str:
                    match_time = datetime.fromisoformat(commence_time_str.replace("Z", "+00:00"))
                    if not (now <= match_time <= end_of_day):
                        continue

                home = ev.get("home_team")
                away = ev.get("away_team")
                sport_title = ev.get("sport_title", "KREPŠINIS")
                bookmakers = ev.get("bookmakers", [])

                if len(bookmakers) < 2:
                    continue # Reikia bent dviejų bendrovių lygijimui

                sharp_totals = []
                all_totals = []

                for bm in bookmakers:
                    bm_key = bm.get("key", "").lower()
                    for m in bm.get("markets", []):
                        if m.get("key") == "totals":
                            for o in m.get("outcomes", []):
                                if o.get("name") == "Over":
                                    line = float(o.get("point", 0))
                                    price = float(o.get("price", 1.0))
                                    item = {"bm": bm_key, "line": line, "price": price}
                                    all_totals.append(item)
                                    if any(s in bm_key for s in SHARP_BOOKMAKERS):
                                        sharp_totals.append(item)

                if not all_totals:
                    continue

                # Apskaičiuojame rinkos vidutinę ribą ir "Sharp" bendrovių tendenciją
                avg_line = sum(x["line"] for x in all_totals) / len(all_totals)
                
                # Ieškome bukmeikerių, kurie atsilieka nuo rinkos (pvz. siūlo per aukštą/žemą ribą arba koeficientą)
                for item in all_totals:
                    line_diff = item["line"] - avg_line
                    
                    # Jei bukmekeris siūlo žemesnę ribą OVER statymui (pvz. 2.5 taško žemiau vidurkio)
                    if line_diff <= -2.0 and item["price"] >= 1.75:
                        edge = abs(line_diff) * 2.2 # Vertės % apskaičiavimas
                        safe_bets.append({
                            "league": f"🏀 {str(sport_title).upper()}",
                            "match": f"{home} vs {away}",
                            "time": match_time.strftime("%H:%M") if commence_time_str else "",
                            "type": "OVER",
                            "line": item["line"],
                            "market_avg_line": round(avg_line, 1),
                            "odds": item["price"],
                            "edge": round(edge, 1),
                            "bookmaker": item["bm"].upper()
                        })
                        break

                    # Jei bukmekeris siūlo aukštesnę ribą UNDER statymui (pvz. 2.5 taško aukščiau vidurkio)
                    elif line_diff >= 2.0 and item["price"] >= 1.75:
                        edge = abs(line_diff) * 2.2
                        safe_bets.append({
                            "league": f"🏀 {str(sport_title).upper()}",
                            "match": f"{home} vs {away}",
                            "time": match_time.strftime("%H:%M") if commence_time_str else "",
                            "type": "UNDER",
                            "line": item["line"],
                            "market_avg_line": round(avg_line, 1),
                            "odds": item["price"],
                            "edge": round(edge, 1),
                            "bookmaker": item["bm"].upper()
                        })
                        break

        except Exception as e:
            print(f"Klaida analizuojant {sport_key}:", e)

    return safe_bets

def run_agent():
    today_date = datetime.now().strftime("%Y-%m-%d")
    safe_bets = analyze_sharp_value_bets()

    if not safe_bets:
        send_telegram_msg(
            f"🛡️ *{today_date} ANALIZĖ:*\n\n"
            f"Šiandien rinkoje **nerasta aukštos vertės (Sharp Value) statymų**.\n"
            f"Algoritmas atmetė visus mačus, nes bukmekerių ribos nustatytos be didelių nuokrypių. Nerekomenduojama rizikuoti."
        )
        return

    full_report = f"🔥 *PROFESIONALIŲ PINIGŲ (SHARP VALUE) STATYMAI ({today_date})*\n"
    full_report += f"Rasta didelio pranašumo prognozių: *{len(safe_bets)}*\n"
    full_report += "───────────────────────────\n\n"

    for b in safe_bets:
        time_str = f"| 🕒 `{b['time']} UTC`" if b['time'] else ""
        full_report += f"🏆 *{b['league']}* {time_str}\n"
        full_report += f"⚔️ *{b['match']}*\n"
        full_report += f"📊 Rinkos vidutinė riba: *{b['market_avg_line']}*\n"
        full_report += f"🎯 *PASIKARTOJANTI VERTĖ:* **{b['type']} {b['line']}**\n"
        full_report += f"📈 Koeficientas: `{b['odds']}` | Pranašumas przed rinka: *+{b['edge']}%*\n"
        full_report += f"🏦 Bendrovė: `{b['bookmaker']}`\n"
        full_report += "\n" + "─"*20 + "\n\n"

    send_telegram_msg(full_report)

if __name__ == "__main__":
    run_agent()
