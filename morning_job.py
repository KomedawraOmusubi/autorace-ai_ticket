import os
import time
import datetime
import pandas as pd
import pytz
import glob
import requests
import re
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# タイムゾーン設定
TOKYO_TZ = pytz.timezone('Asia/Tokyo')
GAS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbyeHqZcoqijEYlaXoNVJs-XevCvP4WaQSQLsMA-_-QUuhyEQY6wJgJWzUroJaEjibEo/exec"

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def get_safe_text(cols, idx):
    if idx < len(cols):
        val = cols[idx].text.strip().replace("\n", " ")
        return val if val and val != "." else "-"
    return "-"

def get_rank_score(race_text, max_score):
    if pd.isna(race_text) or race_text == '-':
        return 0
    match = re.search(r'(\d+)(?=着)', str(race_text))
    if not match:
        return 0
    rank = int(match.group(1))
    score = max_score - (rank - 1) * (max_score / 4.0)
    return max(0, score)

def fetch_tab_data(driver, wait, target_url, data_map, col_indices):
    driver.get(target_url)
    time.sleep(random.uniform(1.0, 2.0))
    try:
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
        t_rows = driver.find_elements(By.CSS_SELECTOR, ".liveTable tbody tr")
        for t_row in t_rows:
            t_cols = t_row.find_elements(By.TAG_NAME, "td")
            if len(t_cols) >= 2:
                t_no = t_cols[0].text.strip()
                if t_no in data_map:
                    for key, idx in col_indices.items():
                        data_map[t_no][key] = get_safe_text(t_cols, idx)
    except Exception as e:
        print(f"      タブ取得エラー ({target_url.split('/')[-1]}): {e}")

def main():
    if not os.path.exists("data"): os.makedirs("data")
    for f in glob.glob("data/*.csv"):
        try: os.remove(f)
        except: pass

    now_jst = datetime.datetime.now(TOKYO_TZ)
    today_str = now_jst.strftime("%Y-%m-%d")
    places = ["kawaguchi", "sanyou", "iizuka", "hamamatsu", "isesaki"]
    driver = get_driver()
    wait = WebDriverWait(driver, 10)

    try:
        for place in places:
            print(f"\n--- {place.upper()} 取得開始 ---")
            driver.get(f"https://autorace.jp/race_info/Program/{place}/{today_str}_1")
            try:
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
            except:
                print(f"  => {place.upper()} スキップ")
                continue

            for r in range(1, 13):
                race_no = str(r)
                base_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_{race_no}"
                
                try:
                    driver.get(f"{base_url}/program")
                    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
                    
                    raw_time_text = driver.find_element(By.ID, "race-result-current-race-start").text
                    start_time_raw = re.sub(r'発走予定|\[.*?\]', '', raw_time_text).strip()
                    voting_deadline = driver.find_element(By.ID, "race-result-current-race-telvote").text.strip()

                    base_data = {}
                    rows = driver.find_elements(By.CSS_SELECTOR, ".liveTable tbody tr")
                    for row in rows:
                        cols = row.find_elements(By.TAG_NAME, "td")
                        if len(cols) >= 6:
                            no = cols[0].text.strip()
                            if no.isdigit():
                                name_parts = cols[1].text.split('\n')
                                base_data[no] = {
                                    "車": no, "選手名": name_parts[0].strip() if name_parts else "-",
                                    "投票締切": voting_deadline, "発走予定": start_time_raw,
                                    "ハンデ": cols[2].text.strip(), "試走T": get_safe_text(cols, 3),
                                    "偏差": cols[4].text.strip(), "出走表_連率": cols[5].text.strip()
                                }

                    if base_data:
                        # --- 近10走 ---
                        fetch_tab_data(driver, wait, f"{base_url}/recent10", base_data, 
                                       {"前1走":2, "前2走":3, "前3走":4, "前4走":5, "前5走":6, "前6走":7, "前7走":8, "前8走":9, "前9走":10, "前10走":11})
                        
                        # --- 良5走(good5) ---
                        fetch_tab_data(driver, wait, f"{base_url}/good5", base_data, 
                                       {"良5前1":2, "良5前2":3, "良5前3":4, "良5前4":5, "良5前5":6})

                        # --- 湿5走(wet5) ---
                        fetch_tab_data(driver, wait, f"{base_url}/wet5", base_data, 
                                       {"湿5前1":2, "湿5前2":3, "湿5前3":4, "湿5前4":5, "湿5前5":6})

                        # --- 斑5走(han5) ---
                        fetch_tab_data(driver, wait, f"{base_url}/han5", base_data, 
                                       {"斑5前1":2, "斑5前2":3, "斑5前3":4, "斑5前4":5, "斑5前5":6})

                        # --- 期間別データ取得 ---
                        fetch_tab_data(driver, wait, f"{base_url}/recent90", base_data, {"90平均ST":5, "90良10平競":10})
                        
                        df = pd.DataFrame(base_data.values()).sort_values("車")

                        # 数値変換とスコア計算
                        for col in ['ハンデ', '偏差', '90平均ST', '90良10平競']:
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

                        HANDI_WEIGHT, ST_WEIGHT, DEV_WEIGHT = 0.0012, 0.1, 0.05
                        race_avg_st = df['90平均ST'].mean() if '90平均ST' in df.columns else 0
                        
                        scores, times = [], []
                        for _, row in df.iterrows():
                            # 近10走のデータを使ってスコア化
                            s = get_rank_score(row.get('前1走', '-'), 30) + get_rank_score(row.get('前2走', '-'), 20)
                            
                            base_time = row.get('90良10平競', 0)
                            if base_time == 0:
                                times.append(0.0); scores.append(0.0)
                                continue
                            
                            f_time = base_time + (row['ハンデ'] * HANDI_WEIGHT) + \
                                     ((row['偏差'] / 1000) * DEV_WEIGHT) + \
                                     ((row['90平均ST'] - race_avg_st) * ST_WEIGHT)
                            
                            times.append(round(f_time, 3))
                            scores.append(round(s + (3.600 - f_time) * 1000, 2))

                        df['前日予想タイム'] = times
                        df['総合スコア'] = scores
                        df['前日予想着順'] = df['総合スコア'].rank(ascending=False, method='min').fillna(9).astype(int)

                        filename = f"data/race_data_{place}_{race_no}R.csv"
                        df.to_csv(filename, index=False, encoding="utf-8-sig")
                        print(f"  => {filename} 保存完了")

                except Exception as e:
                    print(f"  => {race_no}R エラー: {e}")

    finally:
        driver.quit()
        print("\n全ての処理が終了しました。")

if __name__ == "__main__":
    main()
