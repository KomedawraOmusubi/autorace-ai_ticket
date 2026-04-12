import os
import time
import datetime
import pandas as pd
import pytz
import glob
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# タイムゾーン設定
TOKYO_TZ = pytz.timezone('Asia/Tokyo')

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
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
    if not match: return 0
    rank = int(match.group(1))
    score = max_score - (rank - 1) * (max_score / 4.0)
    return max(0, score)

def fetch_tab_data_robust(driver, wait, target_url, data_map, col_indices):
    try:
        driver.get(target_url)
        time.sleep(4.0)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
        t_rows = driver.find_elements(By.CSS_SELECTOR, ".liveTable tbody tr")
        for t_row in t_rows:
            t_cols = t_row.find_elements(By.TAG_NAME, "td")
            if len(t_cols) >= 2:
                t_no = t_cols[0].text.strip()
                if t_no in data_map:
                    for key, idx in col_indices.items():
                        val = get_safe_text(t_cols, idx)
                        if val != "-":
                            data_map[t_no][key] = val
    except Exception as e:
        print(f"      取得エラー ({target_url.split('/')[-1]}): {e}")

def main():
    if not os.path.exists("data"): os.makedirs("data")
    for f in glob.glob("data/*.csv"):
        try: os.remove(f)
        except: pass

    now_jst = datetime.datetime.now(TOKYO_TZ)
    today_str = now_jst.strftime("%Y-%m-%d")
    today_id = now_jst.strftime("%Y%m%d")
    places = ["kawaguchi", "sanyou", "iizuka", "hamamatsu", "isesaki"]
    driver = get_driver()
    wait = WebDriverWait(driver, 20)

    try:
        for place in places:
            print(f"\n--- {place.upper()} 取得開始 ---")
            driver.get(f"https://autorace.jp/race_info/Program/{place}/{today_str}_1")
            try:
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
                nav_elements = driver.find_elements(By.CSS_SELECTOR, ".race_number_nav li a")
                race_nums = [el.text for el in nav_elements if el.text.isdigit()]
                max_race = int(race_nums[-1]) if race_nums else 12
            except:
                print(f"  => {place.upper()} スキップ")
                continue

            for r in range(1, max_race + 1):
                race_no_str = str(r).zfill(2)
                race_id = f"{today_id}_{place}_{race_no_str}"
                base_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_{r}"
                
                try:
                    driver.get(f"{base_url}/program")
                    time.sleep(3.0)
                    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
                    
                    try:
                        race_name = driver.find_element(By.CLASS_NAME, "race_title").text.strip()
                        dist_text = driver.find_element(By.CLASS_NAME, "race_distance").text.strip()
                        weather = driver.find_element(By.ID, "race-result-current-weather").text.strip()
                        temp = driver.find_element(By.ID, "race-result-current-temp").text.strip()
                        humid = driver.find_element(By.ID, "race-result-current-humidity").text.strip()
                        road_temp = driver.find_element(By.ID, "race-result-current-roadtemp").text.strip()
                        road_cond = driver.find_element(By.ID, "race-result-current-roadcondition").text.strip()
                    except:
                        race_name, dist_text, weather, temp, humid, road_temp, road_cond = ["-"] * 7

                    raw_time_text = driver.find_element(By.ID, "race-result-current-race-start").text
                    start_time = re.sub(r'発走予定|\[.*?\]', '', raw_time_text).replace(" ", "").strip()
                    raw_deadline = driver.find_element(By.ID, "race-result-current-race-telvote").text
                    deadline = raw_deadline.replace("投票締切", "").replace(" ", "").strip()

                    base_data = {}
                    rows = driver.find_elements(By.CSS_SELECTOR, ".liveTable tbody tr")
                    for row in rows:
                        cols = row.find_elements(By.TAG_NAME, "td")
                        if len(cols) >= 6:
                            no = cols[0].text.strip()
                            if no.isdigit():
                                name_parts = cols[1].text.split('\n')
                                base_data[no] = {
                                    "レースID": race_id, "日付": today_str, "場所": place, "レース名": race_name,
                                    "距離": dist_text, "天候": weather, "気温": temp, "湿度": humid,
                                    "走路温度": road_temp, "走路状況": road_cond,
                                    "車": no, "選手名": name_parts[0].strip(),
                                    "投票締切": deadline, "発走予定": start_time,
                                    "ハンデ": cols[2].text.strip(), "試走T": get_safe_text(cols, 3),
                                    "偏差": cols[4].text.strip(), "出走表_連率": cols[5].text.strip()
                                }

                    if base_data:
                        # 1. 直近10走
                        fetch_tab_data_robust(driver, wait, f"{base_url}/recent10", base_data, 
                                       {"前1走":2, "前2走":3, "前3走":4, "前4走":5, "前5走":6,
                                        "前6走":7, "前7走":8, "前8走":9, "前9走":10, "前10走":11})
                        
                        # 2, 3, 4. 良/湿/斑5走 (不要な4項目を削除済み)
                        five_run_map = {"前1":1, "前2":2, "前3":3, "前4":4, "前5":5, "平順":6, "近況":7, "2連":8}
                        fetch_tab_data_robust(driver, wait, f"{base_url}/recent5_good", base_data, {f"良5_{k}":v for k,v in five_run_map.items()})
                        fetch_tab_data_robust(driver, wait, f"{base_url}/recent5_wet", base_data, {f"湿5_{k}":v for k,v in five_run_map.items()})
                        fetch_tab_data_robust(driver, wait, f"{base_url}/recent5_patchy", base_data, {f"斑5_{k}":v for k,v in five_run_map.items()})
                        
                        # 5. 近90日
                        fetch_tab_data_robust(driver, wait, f"{base_url}/recent90", base_data, {
                            "90出走": 1, "90優出": 2, "90優勝": 3, "90平均ST": 5,
                            "90_123着外": 6, "90_2連率": 2, "90_3連率": 3,
                            "90良10平競": 10, "90良10平試": 11
                        })
                        
                        # 6. 近180日
                        fetch_tab_data_robust(driver, wait, f"{base_url}/recent180", base_data, {
                            "180良2連": 1, "180良連対回": 2, "180良出走": 3,
                            "180湿2連": 4, "180湿連対回": 5, "180湿出走": 6
                        })
                        
                        # 7. 今年/通算
                        fetch_tab_data_robust(driver, wait, f"{base_url}/total", base_data, {
                            "今年優出": 1, "今年優勝": 2, "通算優勝": 3,
                            "通算1着": 4, "通算2着": 1, "通算3着": 2,
                            "今年単率": 6, "今年2連率": 7, "今年3連率": 8
                        })
                        
                        df = pd.DataFrame(base_data.values()).sort_values("車")
                        
                        # 計算
                        for col in ['ハンデ', '偏差', '90平均ST', '90良10平競']:
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', ''), errors='coerce').fillna(0)

                        HANDI_WEIGHT, ST_WEIGHT, DEV_WEIGHT = 0.0012, 0.1, 0.05
                        race_avg_st = df['90平均ST'].mean()
                        
                        scores, times = [], []
                        for _, row in df.iterrows():
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

                        filename = f"data/race_data_{place}_{race_no_str}R.csv"
                        df.to_csv(filename, index=False, encoding="utf-8-sig")
                        print(f"  => {race_id} 保存完了")
                except Exception as e:
                    print(f"  => {r}R エラー回避: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
