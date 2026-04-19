import os
import time
import datetime
import pandas as pd
import pytz
import glob
import numpy as np
import re
import requests
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# 自作モジュールのインポート
import test_send
import engine

# タイムゾーン設定
TOKYO_TZ = pytz.timezone('Asia/Tokyo')

# 環境変数設定
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
GAS_WEBAPP_URL = os.environ.get("GAS_WEBAPP_URL")

def send_discord_message(content):
    if not DISCORD_WEBHOOK_URL: return
    data = {"content": content}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data).raise_for_status()
    except Exception as e:
        print(f"Discord送信エラー: {e}")

def notify_gas_completion(place, race_no):
    if not GAS_WEBAPP_URL: return
    data = {"action": "complete", "place": place, "race_no": race_no}
    try:
        requests.post(GAS_WEBAPP_URL, json=data)
    except: pass

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.page_load_strategy = 'normal'
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def print_betting_guide(df, place, race_no, info_dict):
    sdf = df.sort_values('予想スコア', ascending=False).reset_index(drop=True)
    cars = [int(sdf.iloc[i]['車']) for i in range(len(sdf))]
    scores = [float(sdf.iloc[i]['予想スコア']) for i in range(len(sdf))]
    
    ana_candidates = sdf.iloc[3:][(sdf['上昇評価'] >= 10) | (sdf['激変評価'] >= 10) | (sdf['追い上げスコア'] >= 15)]
    ana = int(ana_candidates.iloc[0]['車']) if not ana_candidates.empty else None

    msg = [f"**【{place} {race_no}R】 直前予想（プロ仕様・全補正統合版）**"]
    msg.append(f"状況: {info_dict['天候']} / 路面:{info_dict['走路状況']}({info_dict['走路温度']}℃)")
    msg.append("```")
    marks = ["◎", "○", "▲", "△", "注"]
    for i in range(min(5, len(sdf))):
        car = int(sdf.iloc[i]['車'])
        name = sdf.iloc[i]['選手名'] if '選手名' in sdf.columns else "不明"
        rank = sdf.iloc[i]['ランク'] if 'ランク' in sdf.columns else "-"
        score = scores[i]
        tags = []
        if sdf.iloc[i]['逃げ評価'] > 0: tags.append("逃げ")
        if sdf.iloc[i]['激変評価'] > 0: tags.append("激変")
        if sdf.iloc[i]['追い上げスコア'] >= 15: tags.append("捌き")
        if sdf.iloc[i]['走路温度補正'] > 0: tags.append("夏場")
        if sdf.iloc[i]['夜間補正'] > 0: tags.append("夜力")
        tag_str = " ".join([f"[{t}]" for t in tags])
        msg.append(f"{marks[i]} {car}号車 {name: <6} ({rank}) Score:{score:5.1f} {tag_str}")
    
    msg.append("-" * 30)

    diff_top = scores[0] - scores[1]
    diff_box = scores[0] - scores[2]
    
    if diff_top >= 20:
        recommend = f"◎頭固定（信頼）: {cars[0]}-{cars[1]}{cars[2]}-{cars[1]}{cars[2]}{cars[3]}"
    elif diff_box <= 5:
        recommend = f"三連単BOX推奨（激戦）: {cars[0]}, {cars[1]}, {cars[2]} (6点)"
    else:
        # 車番を動的に挿入
        c0, c1, c2 = cars[0], cars[1], cars[2]
        recommend = f"三連単通常: {c0}-{c1}-{c2}, {c0}-{c2}-{c1}, {c1}-{c0}-{c2}"

    msg.append(f"■ {recommend}")
    msg.append(f"■ 二連単: {cars[0]}-{cars[1]}, {cars[1]}-{cars[0]}")
    msg.append(f"■ 三連複BOX: {cars[0]}, {cars[1]}, {cars[2]}, {cars[3]} (4点)")
    
    if ana:
        ana_name = sdf[sdf['車'] == ana]['選手名'].iloc[0] if '選手名' in sdf.columns else "穴候補"
        msg.append("-" * 30)
        msg.append(f"■ 穴候補: {ana}号車 ({ana_name})")
        msg.append(f"■ 穴三連単: {ana}-{cars[0]}-{cars[1]}, {cars[0]}-{ana}-{cars[1]}")
    msg.append("```")
    
    final_msg = "\n".join(msg)
    print(final_msg)
    send_discord_message(final_msg)
    
    test_send.generate_and_send(df, DISCORD_WEBHOOK_URL)

def main():
    now = datetime.datetime.now(TOKYO_TZ)
    today_str = now.strftime("%Y-%m-%d")
    csv_files = glob.glob("data/race_data_*.csv")
    if not csv_files: return

    targets = []
    for file in csv_files:
        try:
            df = pd.read_csv(file)
            start_val = str(df['発走予定'].iloc[0]).strip()
            if start_val in ["", "-", "nan"]: continue
            dep_time = TOKYO_TZ.localize(datetime.datetime.strptime(f"{today_str} {start_val}", "%Y-%m-%d %H:%M"))
            if now < dep_time < (now + datetime.timedelta(minutes=30)):
                targets.append((file, df, dep_time))
        except: continue

    if not targets: return
    driver = get_driver()
    try:
        for file, df, dep_time in targets:
            try:
                fname = os.path.basename(file).replace(".csv", "")
                parts = fname.split("_")
                place, race_no = parts[-2], parts[-1].replace("R", "")
                driver.get(f"https://autorace.jp/race_info/Program/{place}/{today_str}_{race_no}")
                time.sleep(3)
                wait = WebDriverWait(driver, 15)
                
                info_dict = {"天候": "-", "走路状況": "-", "走路温度": "-", "気温": "-", "湿度": "-"}
                try:
                    info_tables = driver.find_elements(By.CLASS_NAME, "race-infoTable")
                    if len(info_tables) >= 2:
                        tds1, tds2 = info_tables[0].find_elements(By.TAG_NAME, "td"), info_tables[1].find_elements(By.TAG_NAME, "td")
                        info_dict.update({
                            "天候": tds1[3].text, 
                            "気温": tds2[0].text, 
                            "湿度": tds2[1].text,
                            "走路温度": tds2[2].text, 
                            "走路状況": tds2[3].text
                        })
                except: pass

                table = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
                rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
                trial_results = {int(cols[0].text.strip()): cols[3].text.strip() for row in rows if len(cols := row.find_elements(By.TAG_NAME, "td")) >= 4 if cols[0].text.strip().isdigit() and cols[3].text.strip() not in [".", "-", "0.00"]}
                
                if len(trial_results) >= 6:
                    df['試走T'] = df['車'].apply(lambda x: trial_results.get(int(x), "-"))
                    prefix = "湿5" if any(x in info_dict["走路状況"] for x in ["湿", "ぶち", "濡"]) or "雨" in info_dict["天候"] else "良5"
                    
                    # ★ engine.py のロジックを呼び出す
                    df = engine.calculate_predictions(df, place, info_dict, weather_prefix=prefix)
                    
                    df.to_csv(file, index=False, encoding="utf-8-sig")
                    print_betting_guide(df, place, race_no, info_dict)
                    notify_gas_completion(place, race_no)
                else:
                    if now < dep_time + datetime.timedelta(minutes=15) and GAS_WEBAPP_URL:
                        r_time = (datetime.datetime.now(TOKYO_TZ) + datetime.timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
                        requests.post(GAS_WEBAPP_URL, json={"times": [r_time], "is_retry": True})
            except Exception:
                print(traceback.format_exc())
    finally: driver.quit()

if __name__ == "__main__":
    main()
