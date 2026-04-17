import os
import time
import datetime
import pandas as pd
import pytz
import glob
import random
import re
import requests
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# タイムゾーン設定
TOKYO_TZ = pytz.timezone('Asia/Tokyo')

# --- GASのURL ---
GAS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbyeHqZcoqijEYlaXoNVJs-XevCvP4WaQSQLsMA-_-QUuhyEQY6wJgJWzUroJaEjibEo/exec"

def get_driver():
    print(">>> [起動] Chromeを起動中...", flush=True)
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument('--lang=ja-JP')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--blink-settings=imagesEnabled=false')
    options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def fetch_tab_data_by_click(driver, wait, submenu_id, data_map, col_indices, label="", force_click=False):
    if label:
        print(f"      [タブ巡回] {label} を取得中...", flush=True)
    try:
        container_id = f"live-program-{submenu_id}-container"
        if submenu_id != "program" or force_click:
            xpath = f"//*[@data-program-submenu='{submenu_id}']//a"
            target_tab = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            driver.execute_script("arguments[0].click();", target_tab)
            wait.until(EC.presence_of_element_located((By.ID, container_id)))
            time.sleep(random.uniform(1.2, 2.0))

        container = driver.find_element(By.ID, container_id)
        target_table = container.find_element(By.CSS_SELECTOR, "table.liveTable")
        if target_table:
            rows = target_table.find_elements(By.CSS_SELECTOR, "tbody tr")
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 2:
                    car_no = cols[0].text.strip()
                    if car_no.isdigit() and car_no in data_map:
                        for key, idx in col_indices.items():
                            if idx < len(cols):
                                val = cols[idx].text.strip()
                                if key != "_raw_info":
                                    val = val.replace("\n", " ")
                                data_map[car_no][key] = val
    except Exception as e:
        if label: print(f"      [警告] {label} スキップ: {str(e)}", flush=True)

def add_predictions(df):
    def extract_race_time(val):
        if pd.isna(val) or val == "-": return None
        nums = re.findall(r'\d+\.\d+', str(val))
        return float(nums[0]) if len(nums) >= 1 else None

    def extract_shiso_time(val):
        if pd.isna(val) or val == "-": return None
        nums = re.findall(r'\d+\.\d+', str(val))
        if len(nums) >= 2: return float(nums[-2])
        elif len(nums) == 1: return float(nums[0])
        return None

    def get_deviation(val):
        if pd.isna(val) or val == "-": return 0.070
        s = re.sub(r'\D', '', str(val))
        if len(s) == 3: return float(f"0.{s}")
        elif len(s) > 0: return float(f"0.{s.zfill(3)}")
        return 0.070

    for condition in ['良', '湿']:
        goal_arrival_times = []
        col_goal = f"前日ゴール時間({condition})"
        col_time = f"前日予想競走T({condition})"
        for idx_row, row in df.iterrows():
            car_no = str(row.get("車", ""))
            dist_text = str(row.get("距離", "3100"))
            dist_num = float(re.sub(r'\D', '', dist_text)) if re.sub(r'\D', '', dist_text) else 3100.0

            if condition == '湿':
                past_race_list = [extract_race_time(row.get(f"湿5_前{i}")) for i in range(1, 4) if extract_race_time(row.get(f"湿5_前{i}"))]
                agari_100m = sum(past_race_list) / len(past_race_list) if past_race_list else (extract_race_time(row.get("良5_前1")) or 3.47) + 0.35
            else:
                past_shiso_list = [extract_shiso_time(row.get(f"良5_前{i}")) for i in range(1, 4) if extract_shiso_time(row.get(f"良5_前{i}"))]
                agari_100m = (sum(past_shiso_list) / len(past_shiso_list) if past_shiso_list else 3.40) + get_deviation(row.get("偏差"))
            
            if car_no == "1": agari_100m -= 0.01
            h_str = str(row.get("ハンデ", "0"))
            handi = float(re.sub(r'\D', '', h_str)) if re.sub(r'\D', '', h_str) else 0
            
            arrival_time = (dist_num + handi) / (100 / agari_100m)
            df.at[idx_row, col_time] = f"{agari_100m:.3f}"
            goal_arrival_times.append(round(arrival_time, 2))
            
        df[col_goal] = goal_arrival_times
        df = df.sort_values(col_goal)
        marks = ["◎", "〇", "▲", "△", "✕", " ", " ", " "]
        df[f'印({condition})'] = marks[:len(df)]
        df[f'予想着順({condition})'] = range(1, len(df) + 1)
    return df.sort_values('車')

def main():
    if not os.path.exists("data"): os.makedirs("data")
    for f in glob.glob("data/*.csv"):
        try: os.remove(f)
        except: pass

    now_jst = datetime.datetime.now(TOKYO_TZ)
    today_str = now_jst.strftime("%Y-%m-%d")
    driver = get_driver()
    wait = WebDriverWait(driver, 20)
    target_times = [] 

    try:
        print(f"\n--- スクレイピング開始 ({today_str}) ---", flush=True)
        driver.get("https://autorace.jp/")
        time.sleep(3)
        
        place_map = {"川口": "kawaguchi", "山陽": "sanyou", "飯塚": "iizuka", "浜松": "hamamatsu", "伊勢崎": "isesaki"}
        active_places = []
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "todayRaceSection")))
            page_text = driver.find_element(By.CLASS_NAME, "todayRaceSection").text
            for jp_name, en_name in place_map.items():
                if jp_name in page_text: active_places.append(en_name)
            active_places = list(dict.fromkeys(active_places))
        except: active_places = []

        for place in active_places:
            first_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_1/program"
            print(f"\n>>> [会場] {place} へ移動", flush=True)
            driver.get(first_url)
            time.sleep(5)

            for r in range(1, 13):
                try:
                    # 1. レースタブのクリック
                    tab_xpath = f"//*[@data-raceno='{r}']"
                    race_tabs = driver.find_elements(By.XPATH, tab_xpath)
                    if not race_tabs: break
                    
                    if r > 1:
                        print(f"  ===[ {place} {r}R 取得開始 ]===", flush=True)
                        driver.execute_script("arguments[0].scrollIntoView(true);", race_tabs[0])
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", race_tabs[0])
                        time.sleep(3) # 表の切り替わり待ち

                    # 2. データの取得（出走表、近10走など）を先に行う
                    # これにより「発走予定」が更新されるまでの時間を稼ぐ
                    base_data = {str(i): {} for i in range(1, 9)}
                    fetch_tab_data_by_click(driver, wait, "program", base_data, {"車": 0, "_raw_info": 1, "ハンデ": 2, "試走T": 3, "偏差": 4, "連率": 5}, "出走表", force_click=(r > 1))
                    
                    # 選手名のパース
                    dist_val = "-"
                    try:
                        info_tables = driver.find_elements(By.CSS_SELECTOR, "table.race-infoTable")
                        if len(info_tables) >= 1:
                            tds1 = info_tables[0].find_elements(By.CSS_SELECTOR, "tbody tr td")
                            if len(tds1) >= 3: dist_val = tds1[2].text.strip()
                    except: pass

                    for car_no, row_data in base_data.items():
                        raw_text = row_data.get("_raw_info", "")
                        p_name, p_car, p_loc, p_gen, p_age, p_class, p_rank = ["-"] * 7
                        if raw_text and raw_text != "-":
                            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
                            if len(lines) >= 1: p_name = lines[0]
                            if len(lines) >= 2: p_car  = lines[1]
                            if len(lines) >= 3:
                                parts = re.split(r'\s+', lines[2]); p_loc, p_gen = (parts + ["-"]*2)[:2]
                            if len(lines) >= 4:
                                parts = re.split(r'\s+', lines[3]); p_age, p_class, p_rank = (parts + ["-"]*3)[:3]
                        row_data.update({"選手名":p_name,"競走車":p_car,"所属":p_loc,"期":p_gen,"年齢":p_age,"車級":p_class,"ランク":p_rank, "距離": dist_val})
                        if "_raw_info" in row_data: del row_data["_raw_info"]

                    fetch_tab_data_by_click(driver, wait, "recent10", base_data, {f"近10_{i-1}": i for i in range(2, 12)}, "近10走")

                    f_map = {"前1": 2, "前2": 3, "前3": 4, "前4": 5, "前5": 6}
                    for sub_id in ["good5", "wet5", "han5"]:
                        l_prefix = "良5" if sub_id == "good5" else "湿5" if sub_id == "wet5" else "斑5"
                        fetch_tab_data_by_click(driver, wait, sub_id, base_data, {f"{l_prefix}_{k}": v for k, v in f_map.items()}, l_prefix)

                    # ★ 3. 最後に「発走予定」を確定させる
                    print(f"      [最終確定] 発走予定時刻を読み取ります...", flush=True)
                    try:
                        raw_time_text = driver.find_element(By.ID, "race-result-current-race-start").text
                        start_time_raw = re.sub(r'発走予定|\[.*?\]', '', raw_time_text).strip()
                        print(f"      [結果] {start_time_raw}", flush=True)
                        
                        if ":" in start_time_raw:
                            race_time_obj = datetime.datetime.strptime(f"{today_str} {start_time_raw}", "%Y-%m-%d %H:%M")
                            race_time = TOKYO_TZ.localize(race_time_obj)
                            if now_jst < race_time:
                                trig = (race_time - datetime.timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:00")
                                target_times.append(trig)
                    except:
                        start_time_raw = "-"

                    # 保存処理
                    df = pd.DataFrame([v for v in base_data.values() if v.get("選手名") and v.get("選手名") != "-"])
                    if not df.empty:
                        df = add_predictions(df)
                        fixed_cols = ["印(良)", "印(湿)", "車", "選手名", "ハンデ", "偏差", "前日ゴール時間(良)", "前日予想競走T(良)", "前日ゴール時間(湿)", "前日予想競走T(湿)"]
                        other_cols = [c for c in df.columns if c not in fixed_cols and c not in ['場所', 'グレード', '日付', 'レース', '発走予定', '距離']]
                        df = df[fixed_cols + other_cols]
                        
                        # 共通ヘッダー取得（念のため直前に再取得）
                        grade_val = driver.find_element(By.CSS_SELECTOR, "#race-result-race-info h3").text.strip()
                        info_tables = driver.find_elements(By.CSS_SELECTOR, "table.race-infoTable")
                        date_val = info_tables[0].find_elements(By.CSS_SELECTOR, "tbody tr td")[0].text.split("\n")[0].strip()
                        race_val = info_tables[0].find_elements(By.CSS_SELECTOR, "tbody tr td")[1].text.strip()

                        df.insert(0, '場所', place); df.insert(1, 'グレード', grade_val); df.insert(2, '日付', date_val)
                        df.insert(3, 'レース', race_val); df.insert(4, '距離', dist_val); df.insert(5, '発走予定', start_time_raw)
                        
                        race_no_str = str(r).zfill(2)
                        df.to_csv(f"data/race_data_{place}_{race_no_str}R.csv", index=False, encoding="utf-8-sig")
                        print(f"      [完了] {place} {r}R を保存しました。", flush=True)
                except Exception as e:
                    print(f"      [エラー] {r}R スキップ: {e}", flush=True)
                    continue

        if target_times:
            try:
                payload = json.dumps({"times": list(set(target_times))})
                requests.post(GAS_WEBAPP_URL, data=payload, headers={'Content-Type': 'application/json'}, timeout=15)
            except: pass

    finally:
        driver.quit()
        print("\n--- 全工程終了 ---", flush=True)

if __name__ == "__main__":
    main()
