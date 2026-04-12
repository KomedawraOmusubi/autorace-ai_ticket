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

TOKYO_TZ = pytz.timezone('Asia/Tokyo')

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument('--lang=ja-JP')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def get_safe_text(cols, idx):
    if idx < len(cols):
        val = cols[idx].text.strip().replace("\n", " ")
        return val if val and val != "" and val != "." else "-"
    return "-"

def get_rank_score(race_text, max_score):
    if pd.isna(race_text) or race_text == '-': return 0
    match = re.search(r'(\d+)(?=着)', str(race_text))
    if not match: return 0
    rank = int(match.group(1))
    return max(0, max_score - (rank - 1) * (max_score / 4.0))

def fetch_tab_data_robust(driver, wait, target_url, data_map, col_indices):
    try:
        time.sleep(1.5)
        driver.get(target_url)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table")))
        time.sleep(1.0) 
        t_rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        for t_row in t_rows:
            t_cols = t_row.find_elements(By.TAG_NAME, "td")
            if len(t_cols) >= 2:
                t_no = t_cols[0].text.strip()
                if t_no in data_map:
                    for key, idx in col_indices.items():
                        data_map[t_no][key] = get_safe_text(t_cols, idx)
    except:
        pass

def main():
    if not os.path.exists("data"): os.makedirs("data")
    for f in glob.glob("data/*.csv"):
        try: os.remove(f)
        except: pass

    now_jst = datetime.datetime.now(TOKYO_TZ)
    today_str, today_id = now_jst.strftime("%Y-%m-%d"), now_jst.strftime("%Y%m%d")
    places = ["kawaguchi", "sanyou", "iizuka", "hamamatsu", "isesaki"]
    driver = get_driver()
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    wait = WebDriverWait(driver, 20)

    try:
        for place in places:
            time.sleep(2.0)
            print("\n--- " + place.upper() + " 取得開始 ---")
            check_url = "https://autorace.jp/race_info/Program/" + place + "/" + today_str + "_1/program"
            driver.get(check_url)
            time.sleep(5.0) 

            all_links = driver.find_elements(By.TAG_NAME, "a")
            race_nums = []
            pattern = "/Program/" + place + "/" + today_str + "_"
            for link in all_links:
                href = str(link.get_attribute("href"))
                if pattern in href:
                    match = re.search(r'_(\d+)(/|$)', href)
                    if match:
                        race_nums.append(int(match.group(1)))
            
            if not race_nums:
                print("  => " + place + " は開催データが見つかりませんでした。")
                continue

            max_race = min(max(set(race_nums)), 12)
            print("  => " + place + ": 全 " + str(max_race) + " レースを検出しました。")

            for r in range(1, max_race + 1):
                time.sleep(1.5)
                race_no_str = str(r).zfill(2)
                race_id = today_id + "_" + place + "_" + race_no_str
                base_url = "https://autorace.jp/race_info/Program/" + place + "/" + today_str + "_" + str(r)
                
                try:
                    driver.get(base_url + "/program")
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table")))
                    time.sleep(1.0)
                    
                    # --- レース詳細情報の取得 ---
                    try:
                        race_title = driver.find_element(By.CLASS_NAME, "race_title").text.strip()
                        info_tables = driver.find_elements(By.CLASS_NAME, "race-infoTable")
                        def get_info(t_idx, td_idx):
                            try: return info_tables[t_idx].find_elements(By.TAG_NAME, "td")[td_idx].text.strip()
                            except: return "-"
                        
                        dist = get_info(0, 2)
                        weather = get_info(0, 3)
                        temp = get_info(1, 0)
                        humid = get_info(1, 1)
                        road_temp = get_info(1, 2)
                        road_cond = get_info(1, 3)
                    except:
                        race_title, dist, weather, temp, humid, road_temp, road_cond = "Unknown", "-", "-", "-", "-", "-", "-"

                    base_data = {}
                    target_rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

                    for row in target_rows:
                        cols = row.find_elements(By.TAG_NAME, "td")
                        if len(cols) >= 6:
                            no = cols[0].text.strip()
                            if not no.isdigit(): continue
                            base_data[no] = {
                                "レースID": race_id, "日付": today_str, "場所": place, "レース": str(r) + "R",
                                "開催名": race_title, "距離": dist, "天候": weather, "気温": temp, "湿度": humid,
                                "走路温度": road_temp, "走路状況": road_cond,
                                "車": no, "選手名": cols[1].text.split('\n')[0].strip(),
                                "ハンデ": cols[2].text.strip(), "試走T": get_safe_text(cols, 3),
                                "偏差": cols[4].text.strip(), "出走表_連率": cols[5].text.strip()
                            }

                    if base_data:
                        # 良/湿5走タブ
                        f_map = {"前1":2, "前2":3, "前3":4, "前4":5, "前5":6, "平順":7, "近況":8, "2連":9}
                        for b in [("good5","良"), ("wet5","湿"), ("han5","斑")]:
                            fetch_tab_data_robust(driver, wait, base_url + "/" + b[0], base_data, {b[1] + "5_" + k:v for k,v in f_map.items()})

                        # 近10走タブ
                        recent10_map = {f"近10_前{i}": i+1 for i in range(1, 11)}
                        fetch_tab_data_robust(driver, wait, base_url + "/recent10", base_data, recent10_map)

                        # 近況90日タブ
                        fetch_tab_data_robust(driver, wait, base_url + "/recent90", base_data, {
                            "90出走":2, "90優出":3, "90優勝":4, "90平均ST":5, 
                            "90_1着":6, "90_2連率":7, "90_3連率":8, "90平均試":9, "90平均競":10
                        })

                        df = pd.DataFrame(base_data.values()).sort_values("車")
                        for c in ['ハンデ', '偏差', '90平均ST', '90平均競']:
                            if c in df.columns:
                                df[c] = pd.to_numeric(df[c].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
                        
                        avg_st = df['90平均ST'].mean() if '90平均ST' in df.columns else 0.15
                        times, scores = [], []
                        for _, row in df.iterrows():
                            # 総合スコア計算（良5走の前1, 前2をベースにする例）
                            s = get_rank_score(row.get('良5_前1', '-'), 30) + get_rank_score(row.get('良5_前2', '-'), 20)
                            bt = row.get('90平均競', 0)
                            if bt == 0: 
                                times.append(0.0); scores.append(0.0)
                            else:
                                ft = bt + (row['ハンデ']*0.001) + (row['偏差']*0.1) + ((row['90平均ST']-avg_st)*0.1)
                                times.append(round(ft, 3))
                                scores.append(round(s + (3.600 - ft) * 1000, 2))
                        
                        df['予想タイム'], df['総合スコア'] = times, scores
                        if not df['総合スコア'].empty:
                            df['予想着順'] = df['総合スコア'].rank(ascending=False, method='min').fillna(9).astype(int)

                        df.to_csv("data/race_data_" + place + "_" + race_no_str + "R.csv", index=False, encoding="utf-8-sig")
                        print("  => " + race_id + " 保存完了")
                except Exception as e: 
                    print("  => " + str(r) + "R 取得失敗: " + str(e))

    finally: 
        driver.quit()
        print("\n全ての処理が終了しました。")

if __name__ == "__main__":
    main()
