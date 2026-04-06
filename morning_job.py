
import os
import time
import datetime
import pandas as pd
import pytz
import glob
import requests
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

TOKYO_TZ = pytz.timezone('Asia/Tokyo')

# --- GASのURL ---
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

def get_rank_score(rank_text, max_score):
    if pd.isna(rank_text) or rank_text == '-':
        return 0
    match = re.search(r'(\d+)着', str(rank_text))
    if not match:
        return 0
    rank = int(match.group(1))
    score = max_score - (rank - 1) * (max_score / 4.0)
    return max(0, score)

def fetch_tab_data(driver, wait, target_url, data_map, col_indices):
    driver.get(target_url)
    time.sleep(3) # 負荷軽減
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
        t_rows = driver.find_elements(By.CSS_SELECTOR, ".liveTable tbody tr")
        for t_row in t_rows:
            t_cols = t_row.find_elements(By.TAG_NAME, "td")
            if len(t_cols) >= 2:
                t_no = t_cols.text.strip()
                if t_no in data_map:
                    for key, idx in col_indices.items():
                        data_map[t_no][key] = get_safe_text(t_cols, idx)
    except Exception as e:
        print(f"      タブ取得エラー ({target_url.split('/')[-1]}): {e}")

def main():
    target_times = []
    if not os.path.exists("data"):
        os.makedirs("data")
    
    # 実行のたびに古いデータをクリア
    old_files = glob.glob("data/*.csv")
    for f in old_files:
        try: os.remove(f)
        except: pass

    now_jst = datetime.datetime.now(TOKYO_TZ)
    today_str = now_jst.strftime("%Y-%m-%d")
    places = ["kawaguchi", "sanyou", "iizuka", "hamamatsu", "isesaki"]
    driver = get_driver()
    wait = WebDriverWait(driver, 10)

    try:
        for place in places:
            print(f"--- {place.upper()} 取得開始 ---")
            check_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_1"
            driver.get(check_url)
            try:
                WebDriverWait(driver, 7).until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
            except TimeoutException:
                print(f"  => {place.upper()} スキップ: 本日の開催がないかデータ未公開")
                continue

            for r in range(1, 13):
                race_no = str(r)
                filename = f"data/race_data_{place}_{race_no}R.csv"
                
                if os.path.exists(filename):
                    continue

                base_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_{race_no}"
                try:
                    driver.get(f"{base_url}/program")
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
                    
                    # 発走時刻の取得とクレンジング
                    raw_time_text = driver.find_element(By.ID, "race-result-current-race-start").text
                    # [1] ソースにある「[変更]」などの余計な文字を正規表現で除去
                    start_time_raw = re.sub(r'発走予定|\[.*?\]', '', raw_time_text).strip()
                    
                    voting_deadline = driver.find_element(By.ID, "race-result-current-race-telvote").text.strip()

                    if ":" in start_time_raw:
                        race_time_obj = datetime.datetime.strptime(f"{today_str} {start_time_raw}", "%Y-%m-%d %H:%M")
                        race_time = TOKYO_TZ.localize(race_time_obj)
                        
                        if now_jst > race_time:
                            print(f"  => {race_no}R スキップ: 既に発走済みです")
                            continue

                        trigger_time = race_time - datetime.timedelta(minutes=15)
                        if trigger_time > now_jst:
                            target_times.append(trigger_time.strftime("%Y-%m-%dT%H:%M:00"))

                    # 基本データ取得
                    base_data = {}
                    rows = driver.find_elements(By.CSS_SELECTOR, ".liveTable tbody tr")
                    for row in rows:
                        cols = row.find_elements(By.TAG_NAME, "td")
                        if len(cols) >= 6:
                            no = cols.text.strip()
                            if no.isdigit():
                                # 選手名取得の修正：改行で分割して1件目を取得
                                name_parts = cols.text.split('\n')
                                name = name_parts.strip() if name_parts else "-"
                                
                                base_data[no] = {
                                    "車": no, "選手名": name,
                                    "投票締切": voting_deadline, "発走予定": start_time_raw,
                                    "ハンデ": cols.text.strip(), "試走T": "-",
                                    "偏差": cols.text.strip(), "出走表_連率": cols.text.strip()
                                }

                    if base_data:
                        # タブデータの取得
                        fetch_tab_data(driver, wait, f"{base_url}/recent10", base_data, {"前1走":2, "前2走":3, "前3走":4})
                        fetch_tab_data(driver, wait, f"{base_url}/recent90", base_data, {"90平均ST":5, "90良10平競":10})

                        df = pd.DataFrame(base_data.values()).sort_values("車")

                        # 数値変換
                        for col in ['ハンデ', '偏差', '90平均ST', '90良10平競']:
                            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

                        HANDI_WEIGHT, ST_WEIGHT, DEV_WEIGHT = 0.0012, 0.1, 0.05
                        race_avg_st = df['90平均ST'].mean()
                        scores, times = [], []

                        for _, row in df.iterrows():
                            s = get_rank_score(row.get('前1走', '-'), 30) + get_rank_score(row.get('前2走', '-'), 20)
                            base_time = row['90良10平競']
                            if base_time == 0:
                                times.append(0.0); scores.append(0.0)
                                continue
                            
                            f_time = base_time + (row['ハンデ'] * HANDI_WEIGHT) + ((row['偏差'] / 1000) * DEV_WEIGHT) + ((row['90平均ST'] - race_avg_st) * ST_WEIGHT)
                            times.append(round(f_time, 3))
                            scores.append(round(s + (3.600 - f_time) * 1000, 2))

                        df['前日予想タイム'] = times
                        df['総合スコア'] = scores
                        df['前日予想着順'] = df['総合スコア'].rank(ascending=False, method='min').fillna(9).astype(int)

                        df.to_csv(filename, index=False, encoding="utf-8-sig")
                        print(f"  => {filename} 保存完了")
                        time.sleep(2)

                except Exception as e:
                    print(f"  => {race_no}R 処理エラー: {e}")
                    continue 

        if target_times:
            # 重複削除とソートをしてGASへ送信
            unique_times = sorted(list(set(target_times)))[:20]
            requests.post(GAS_WEBAPP_URL, json={"times": unique_times}, timeout=15)

    finally:
        driver.quit()
        print("全ての処理が終了しました。")

if __name__ == "__main__":
    main()


