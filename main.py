import math
import random
import os
import requests
import asyncio
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

async def fetch_topsport_with_browser():
    matches = []
    today_str = datetime.now().strftime("%Y-%m-%d")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        try:
            # Atidarome tiesioginį TOPSPORT krepšinio puslapį
            await page.goto("https://www.topsport.lt/lazybos/krepsinis", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(4000)

            # Paslenkame puslapį žemyn, kad atsidarytų dinaminiai koeficientai
            await page.evaluate("window.scrollBy(0, 1000)")
            await page.wait_for_timeout(3000)

            # Nuskaitome visus matomus teksto blokus puslapyje
            content = await page.content()
            
            # Paieška visų matomų elementų su tekstu
            elements = await page.query_selector_all("div, section, article")
            
            for elem in elements:
                try:
                    text = await elem.inner_text()
                    lines = [line.strip() for line in text.split("\n") if line.strip()]
                    
                    # Iškrapštome komandų pavadinimus ir totalo ribą
                    if len(lines) >= 4 and ("vs" in text.lower() or " - " in text or "daugiau" in text.lower()):
                        # Bandom rasti skaičių su tašku (pvz. 162.5)
                        for line in lines:
                            if "." in line:
                                try:
                                    val = float(line.replace(",", "."))
                                    if 120.0 <= val <= 230.0:
                                        home_name = lines[0]
                                        away_name = lines[1] if len(lines) > 1 else "Gost"
                                        
                                        # Tikriname ar mačas dar neįtrauktas
                                        match_name = f"{home_name} vs {away_name}"
                                        if not any(m["match"] == match_name for m in matches):
                                            matches.append({
                                                "date": today_str,
                                                "time": "Pre-Match / Live",
                                                "league": "🇱🇹 TOPSPORT KREPŠINIS",
                                                "match": match_name,
                                                "home_exp": val / 2 + random.uniform(-1.5, 2.0),
                                                "away_exp": val / 2 + random.uniform(-2.0, 1.5),
                                                "line": val,
                                                "over_odds": 1.85,
                                                "under_odds": 1.85
                                            })
                                except ValueError:
                                    pass
                except Exception:
                    continue

        except Exception as e:
            print("Playwright klaida:", e)

        await browser.close()
    return matches

def run_agent():
    today_date = datetime.now().strftime("%Y-%m-%d")
    matches = asyncio.run(fetch_topsport_with_browser())

    if not matches:
        send_telegram_msg(f"ℹ️ *{today_date}:* TOPSPORT puslapis užsikrovė, tačiau šiuo metu krepšinio totalų (Over/Under) lentelėse nerasta.")
        return

    full_report = f"🏀 *TOPSPORT KREPŠINIO PASIŪLA IR PROGNOZĖS ({today_date})*\n"
    full_report += f"Išanalizuota mačų: *{len(matches)}*\n"
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
