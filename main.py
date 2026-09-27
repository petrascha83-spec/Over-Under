import math
import random
import os
import requests
import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright

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

async def fetch_topsport_with_network_capture():
    matches = []
    today_str = datetime.now().strftime("%Y-%m-%d")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        page = await context.new_page()

        # Pagavimo funkcija: klausomės visų TOPSPORT vidinių tinklo atsakymų
        async def handle_response(response):
            if "events" in response.url or "outcomes" in response.url or "sports" in response.url:
                try:
                    data = await response.json()
                    events = data.get("data", []) or data.get("events", []) or []
                    if isinstance(data, list):
                        events = data

                    for ev in events:
                        if not isinstance(ev, dict):
                            continue
                        
                        # Ištraukiame komandas
                        home = ev.get("home_team_name") or ev.get("homeTeam", {}).get("name") or ev.get("title", "").split(" - ")[0]
                        away = ev.get("away_team_name") or ev.get("awayTeam", {}).get("name") or "Svečiai"
                        league = ev.get("competition_name") or "TOPSPORT KREPŠINIS"

                        if not home or home == "Svečiai":
                            continue

                        # Paieška tarp rinkų (markets)
                        markets = ev.get("markets", []) or []
                        for m in markets:
                            m_name = str(m.get("name", "")).lower()
                            if "total" in m_name or "suminis" in m_name or "daugiau/mažiau" in m_name or "points" in m_name:
                                outcomes = m.get("outcomes", []) or []
                                over_obj = next((o for o in outcomes if "daugiau" in str(o.get("name", "")).lower() or "over" in str(o.get("name", "")).lower()), None)
                                under_obj = next((o for o in outcomes if "mažiau" in str(o.get("name", "")).lower() or "under" in str(o.get("name", "")).lower()), None)

                                if over_obj:
                                    line = float(over_obj.get("handicap") or over_obj.get("point") or 160.5)
                                    over_odds = float(over_obj.get("rate") or over_obj.get("price") or 1.85)
                                    under_odds = float(under_obj.get("rate") or under_obj.get("price") or 1.85) if under_obj else 1.85

                                    match_key = f"{home} vs {away}"
                                    if not any(x["match"] == match_key for x in matches):
                                        matches.append({
                                            "date": today_str,
                                            "time": "Gyvai / Artėjančios",
                                            "league": f"🇱🇹 {str(league).upper()}",
                                            "match": match_key,
                                            "home_exp": line / 2 + random.uniform(-1.5, 2.0),
                                            "away_exp": line / 2 + random.uniform(-2.0, 1.5),
                                            "line": line,
                                            "over_odds": over_odds,
                                            "under_odds": under_odds
                                        })
                except Exception:
                    pass

        # Pririšame tinklo klausymąsi
        page.on("response", handle_response)

        try:
            # 1. Užkrauname krepšinio puslapį
            await page.goto("https://www.topsport.lt/lazybos/krepsinis", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)

            # 2. Automatiškai pravažiuojame žemyn, kad suveiktų visi API užklausimai
            for i in range(5):
                await page.evaluate(f"window.scrollBy(0, {800 * (i + 1)})")
                await page.wait_for_timeout(1000)

            # 3. Jei turime "Live" skiltį, aplankome ir ją
            await page.goto("https://www.topsport.lt/lazybos/gyvai/krepsinis", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)

        except Exception as e:
            print("Klaida užkraunant puslapį:", e)

        await browser.close()
    return matches

def run_agent():
    today_date = datetime.now().strftime("%Y-%m-%d")
    matches = asyncio.run(fetch_topsport_with_network_capture())

    if not matches:
        send_telegram_msg(f"ℹ️ *{today_date}:* TOPSPORT puslapis užsikrovė, tačiau šiuo metu krepšinio totalų (Over/Under) lentelėse nerasta.")
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
