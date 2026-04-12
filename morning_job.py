import os
import time
import datetime
import pandas as pd
import pytz
import glob
import re
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

TOKYO_TZ = pytz.timezone('Asia/Tokyo')

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument('--lang=ja-JP')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def get_safe_text(cols, idx):
    if idx < len(cols):
        val = cols[idx].text.strip().replace("\n", " ")
        return val if val and val != "" and val != "." else "-"
    return "-"

def fetch_tab_data_robust(driver, wait, target_url, data_map, col_indices, label=""):
    """タブごとの取得状況を表示し、失敗時は即スキップ"""
    if label:
        print(f"      -> {label} 取得中...", end="\r")
    try:
        driver.get(target_url)
        wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "table tbody tr")) >= 5)
        time.sleep(random.uniform(1.0, 1.5))

        tables = driver.find_elements(By.CSS_SELECTOR, "table")
        target_table = None

        for table in tables:
            if table.is_displayed():
                rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
                if len(rows) >= 5:
                    target_table = table
                    break

        if target_table is None:
            return

        t_rows = target_table.find_elements(By.CSS_SELECTOR, "tbody tr")
        for t_row in t_rows:
            t_cols = t_row.find_elements(By.TAG_NAME, "td")
            if len(t_cols) >= 2:
                t_no = t_cols[0].text.strip()
                if t_no in data_map:
                    for key, idx in col_indices.items():
                        data_map[t_no][key] = get_safe_text(t_cols, idx)
    except Exception:
        pass

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
    wait = WebDriverWait(driver, 10)

    try:
        for place in places:
            print(f"\n--- {place.upper()} 開催チェック ---")
            
            check_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_1/program"
            driver.get(check_url)
            try:
                WebDriverWait(driver, 7).until(EC.presence_of_element_located((By.CLASS_NAME, "race-infoTable")))
            except TimeoutException:
                print(f"  => {place.upper()} は本日開催がないためスキップ")
                continue

            for r in range(1, 13):
                try:
                    race_no_str = str(r).zfill(2)
                    race_id = f"{today_id}_{place}_{race_no_str}"
                    base_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_{r}"

                    driver.get(base_url + "/program")
                    
                    try:
                        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, "race-infoTable")))
                    except TimeoutException:
                        print(f"  => {place.upper()} {r}R 以降なし。")
                        break 

                    print(f"  [{race_id}] 取得開始")
                    time.sleep(random.uniform(1.0, 1.5))

                    base_data = {str(i): {"車": str(i)} for i in range(1, 9)}
                    
                    # ヘッダー情報
                    try:
                        info_tables = driver.find_elements(By.CLASS_NAME, "race-infoTable")
                        h_data = {"日付": "-", "レース名": "-", "距離": "-", "天候": "-", "気温": "-", "湿度": "-", "走路温度": "-", "走路状況": "-"}
                        if len(info_tables) >= 2:
                            row1 = info_tables[0].find_elements(By.CSS_SELECTOR, "tbody tr td")
                            if len(row1) >= 4:
                                h_data.update({"日付": row1[0].text.strip(), "レース名": row1[1].text.strip(), "距離": row1[2].text.strip(), "天候": row1[3].text.strip()})
                            row2 = info_tables[1].find_elements(By.CSS_SELECTOR, "tbody tr td")
                            if len(row2) >= 4:
                                h_data.update({"気温": row2[0].text.strip(), "湿度": row2[1].text.strip(), "走路温度": row2[2].text.strip(), "走路状況": row2[3].text.strip()})
                        for car_no in base_data:
                            base_data[car_no].update(h_data)
                            base_data[car_no]["場所"] = place
                    except Exception: pass

                    # 各タブ取得
                    fetch_tab_data_robust(driver, wait, base_url + "/program", base_data, {"選手名": 1, "ハンデ": 2, "試走T": 3, "偏差": 4, "連率": 5}, "出走表")
                    fetch_tab_data_robust(driver, wait, base_url + "/recent10", base_data, {f"近10_{i}": i+1 for i in range(1, 11)}, "近10走")
                    
                    f_map = {"前1":2, "前2":3, "前3":4, "前4":5, "前5":6, "平近順":7, "近況":8, "2連対率":9}
                    for b_slug, b_name in [("good5","良"), ("wet5","湿"), ("han5","斑")]:
                        fetch_tab_data_robust(driver, wait, base_url + "/" + b_slug, base_data, {f"{b_name}5_{k}":v for k,v in f_map.items()}, f"{b_name}5")

                    fetch_tab_data_robust(driver, wait, base_url + "/recent90", base_data, {
                        "90出走":2, "90優出":3, "90優勝":4, "90平均ST":5,
                        "90(近10)_各着順":6, "90(近10)_2連対率":7, "90(近10)_3連対率":8, "90(良10)平均試":9, "90(良10)平均競":10, "90(良10)最高競T(場)":11
                    }, "90日")

                    fetch_tab_data_robust(driver, wait, base_url + "/recent180", base_data, {
                        "180良_2連対率":2, "180良_連対回数":3, "180良_出走数":4,
                        "180湿_2連対率":5, "180湿_連対回数":6, "180湿_出走数":7
                    }, "180日")

                    fetch_tab_data_robust(driver, wait, base_url + "/total", base_data, {
                        "今年_優出":2, "今年_優勝":3, "通算_優勝":5,
                        "通算_1着":6, "通算_2着":7, "通算_3着":8, "通算_単勝率":9, "通算_2連対率":10, "通算_3連対率":11
                    }, "年間")

                    # 保存
                    df = pd.DataFrame(base_data.values())
                    df['車'] = pd.to_numeric(df['車'], errors='coerce')
                    df = df.sort_values("車")
                    df = df[df['選手名'].notna() & (df['選手名'] != "-")]
                    df.to_csv(f"data/race_data_{place}_{race_no_str}R.csv", index=False, encoding="utf-8-sig")
                    print(f"  => {race_id} 保存完了          ")

                except Exception as e:
                    print(f"  => {r}R エラー: {e}")

    finally:
        driver.quit()
        print("\n全ての処理が終了しました。")

if __name__ == "__main__":
    main()
