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

# タイムゾーン設定
TOKYO_TZ = pytz.timezone('Asia/Tokyo')

# --- GASのURL (適宜書き換えてください) ---
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
    """リストの範囲内であればテキストを返し、それ以外は'-'を返す安全な関数"""
    if idx < len(cols):
        val = cols[idx].text.strip().replace("\n", " ")
        return val if val and val != "." else "-"
    return "-"

def get_rank_score(rank_text, max_score):
    """着順文字列からスコアを計算"""
    if pd.isna(rank_text) or rank_text == '-':
        return 0
    match = re.search(r'(\d+)着', str(rank_text))
    if not match:
        return 0
    rank = int(match.group(1))
    score = max_score - (rank - 1) * (max_score / 4.0)
    return max(0, score)

def fetch_tab_data(driver, wait, target_url, data_map, col_indices):
    """各タブ（近10走など）のデータを取得してdata_mapに格納"""
    driver.get(target_url)
    time.sleep(1) # サーバー負荷軽減と読み込み待ち
    try:
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
        t_rows = driver.find_elements(By.CSS_SELECTOR, ".liveTable tbody tr")
        for t_row in t_rows:
            t_cols = t_row.find_elements(By.TAG_NAME, "td")
            if len(t_cols) >= 2:
                # リストの0番目（車番）を取得
                t_no = t_cols[0].text.strip()
                if t_no in data_map:
                    for key, idx in col_indices.items():
                        data_map[t_no][key] = get_safe_text(t_cols, idx)
    except Exception as e:
        print(f"      タブ取得エラー ({target_url.split('/')[-1]}): {e}")

def main():
    target_times = []
    if not os.path.exists("data"):
        os.makedirs("data")
    
    # 既存データのクリア
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
            print(f"\n--- {place.upper()} 取得開始 ---")
            # 開催確認
            check_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_1"
            driver.get(check_url)
            try:
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
            except TimeoutException:
                print(f"  => {place.upper()} スキップ: 本日の開催がないかデータ未公開")
                continue

            for r in range(1, 13):
                race_no = str(r)
                base_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_{race_no}"
                
                try:
                    driver.get(f"{base_url}/program")
                    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
                    
                    # 発走時刻と締切の取得
                    raw_time_text = driver.find_element(By.ID, "race-result-current-race-start").text
                    start_time_raw = re.sub(r'発走予定|\[.*?\]', '', raw_time_text).strip()
                    voting_deadline = driver.find_element(By.ID, "race-result-current-race-telvote").text.strip()

                    # 発走済みチェック
                    if ":" in start_time_raw:
                        race_time_obj = datetime.datetime.strptime(f"{today_str} {start_time_raw}", "%Y-%m-%d %H:%M")
                        race_time = TOKYO_TZ.localize(race_time_obj)
                        
                        if now_jst > race_time:
                            print(f"  => {race_no}R スキップ: 既に発走済み({start_time_raw})")
                            continue

                        # GAS用トリガー時刻（15分前）
                        trigger_time = race_time - datetime.timedelta(minutes=15)
                        if trigger_time > now_jst:
                            target_times.append(trigger_time.strftime("%Y-%m-%dT%H:%M:00"))

                    print(f"   [{race_no}R] データ取得中...")

                    # 基本データ(出走表)取得
                    base_data = {}
                    rows = driver.find_elements(By.CSS_SELECTOR, ".liveTable tbody tr")
                    for row in rows:
                        cols = row.find_elements(By.TAG_NAME, "td")
                        if len(cols) >= 6:
                            no = cols[0].text.strip()
                            if no.isdigit():
                                name_parts = cols[1].text.split('\n')
                                name = name_parts[0].strip() if name_parts else "-"
                                
                                base_data[no] = {
                                    "車": no, "選手名": name,
                                    "投票締切": voting_deadline, "発走予定": start_time_raw,
                                    "ハンデ": cols[2].text.strip(), "試走T": get_safe_text(cols, 3),
                                    "偏差": cols[4].text.strip(), "出走表_連率": cols[5].text.strip()
                                }

                    if base_data:
                        # --- 各詳細タブからのデータ取得 ---
                        
                        # 1. 近10走 (1〜10走)
                        fetch_tab_data(driver, wait, f"{base_url}/recent10", base_data, 
                                       {"前1走":2, "前2走":3, "前3走":4, "前4走":5, "前5走":6, "前6走":7, "前7走":8, "前8走":9, "前9走":10, "前10走":11})
                        
                        # 2. 走路別（良/湿/斑）
                        for mode in ["good5", "wet5", "han5"]:
                            fetch_tab_data(driver, wait, f"{base_url}/{mode}", base_data, {
                                f"{mode}平順": 7, f"{mode}近況": 8, f"{mode}2連率": 9
                            })

                        # 3. 90日/180日/365日データ
                        fetch_tab_data(driver, wait, f"{base_url}/recent90", base_data, 
                                       {"90平均ST":5, "90良10平競":10, "90良10平試":9})
                        fetch_tab_data(driver, wait, f"{base_url}/recent180", base_data, 
                                       {"180良2連":2, "180湿2連":5})
                        fetch_tab_data(driver, wait, f"{base_url}/recent365", base_data, 
                                       {"通算優勝":4, "通算2連":9})

                        # --- 分析とスコアリング ---
                        df = pd.DataFrame(base_data.values()).sort_values("車")

                        # 数値変換
                        for col in ['ハンデ', '偏差', '90平均ST', '90良10平競']:
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

                        HANDI_WEIGHT, ST_WEIGHT, DEV_WEIGHT = 0.0012, 0.1, 0.05
                        race_avg_st = df['90平均ST'].mean() if '90平均ST' in df.columns else 0
                        
                        scores, times = [], []
                        for _, row in df.iterrows():
                            # 着順スコア（前1走・前2走）
                            s = get_rank_score(row.get('前1走', '-'), 30) + get_rank_score(row.get('前2走', '-'), 20)
                            
                            base_time = row.get('90良10平競', 0)
                            if base_time == 0:
                                times.append(0.0); scores.append(0.0)
                                continue
                            
                            # 予想タイム計算
                            f_time = base_time + (row['ハンデ'] * HANDI_WEIGHT) + \
                                     ((row['偏差'] / 1000) * DEV_WEIGHT) + \
                                     ((row['90平均ST'] - race_avg_st) * ST_WEIGHT)
                            
                            times.append(round(f_time, 3))
                            scores.append(round(s + (3.600 - f_time) * 1000, 2))

                        df['前日予想タイム'] = times
                        df['総合スコア'] = scores
                        df['前日予想着順'] = df['総合スコア'].rank(ascending=False, method='min').fillna(9).astype(int)

                        # CSV保存
                        filename = f"data/race_data_{place}_{race_no}R.csv"
                        df.to_csv(filename, index=False, encoding="utf-8-sig")
                        print(f"  => {filename} 保存完了")
                        time.sleep(1)

                except Exception as e:
                    print(f"  => {race_no}R 処理エラー: {e}")
                    continue 

        # GASへのトリガー送信
        if target_times:
            unique_times = sorted(list(set(target_times)))[:20]
            try:
                res = requests.post(GAS_WEBAPP_URL, json={"times": unique_times}, timeout=20)
                print(f"\nGAS送信完了: {res.status_code}")
            except Exception as e:
                print(f"\nGAS送信エラー: {e}")

    finally:
        driver.quit()
        print("\n全ての処理が終了しました。")

if __name__ == "__main__":
    main()
