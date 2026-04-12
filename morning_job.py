import os
import time
import datetime
import pandas as pd
import pytz
import glob
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
    if label:
        print(f"      [取得中] {label}...", flush=True)
    try:
        driver.get(target_url)
        time.sleep(2.5) 
        
        wait_short = WebDriverWait(driver, 10)
        wait_short.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "table tbody tr td")) >= 2)

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
        if label:
            print(f"      [スキップ] {label} (データなし)", flush=True)

def main():
    if not os.path.exists("data"): os.makedirs("data")
    for f in glob.glob("data/*.csv"):
        try: os.remove(f)
        except: pass

    now_jst = datetime.datetime.now(TOKYO_TZ)
    today_str = now_jst.strftime("%Y-%m-%d")
    today_id = now_jst.strftime("%Y%m%d")

    driver = get_driver()
    wait = WebDriverWait(driver, 15)

    try:
        print(f"--- 本日の開催場を確認中 ---", flush=True)
        driver.get("https://autorace.jp/")
        time.sleep(3.0)
        
        active_places = []
        place_map = {
            "川口": "kawaguchi",
            "山陽": "sanyou",
            "飯塚": "iizuka",
            "浜松": "hamamatsu",
            "伊勢崎": "isesaki"
        }

        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "todayRaceSection")))
            page_text = driver.find_element(By.CLASS_NAME, "todayRaceSection").text
            
            for jp_name, en_name in place_map.items():
                if jp_name in page_text:
                    active_places.append(en_name)
            
            active_places = list(dict.fromkeys(active_places))
            print(f"  => 検知された開催場: {active_places}", flush=True)
        except Exception as e:
            print(f"  => 開催場の自動判定に失敗しました。全会場チェックに切り替えます。")
            active_places = ["kawaguchi", "sanyou", "iizuka", "hamamatsu", "isesaki"]

        if not active_places:
            print("本日の開催場が見つかりませんでした。終了します。")
            return

        for place in active_places:
            print(f"\n--- {place.upper()} 取得開始 ---", flush=True)
            
            for r in range(1, 13):
                try:
                    race_no_str = str(r).zfill(2)
                    race_id = f"{today_id}_{place}_{race_no_str}"
                    base_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_{r}"

                    driver.get(base_url + "/program")
                    time.sleep(3.0)

                    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                    if len(rows) < 5:
                        print(f"  => {place.upper()} {r}R 以降の番組なし。終了。", flush=True)
                        break 

                    print(f"\n  [{race_id}] 処理開始...", flush=True)
                    base_data = {str(i): {} for i in range(1, 9)}
                    
                    # ヘッダー情報の取得
                    try:
                        info_tables = driver.find_elements(By.CLASS_NAME, "race-infoTable")
                        # 順序を考慮して辞書を初期化
                        h_data = {
                            "日付": "-", "グレード": "-", "レース名": "-", "距離": "-", "天候": "-", 
                            "気温": "-", "湿度": "-", "走路温度": "-", "走路状況": "-", 
                            "投票締切": "-", "発走予定": "-"
                        }
                        
                        # グレード情報の取得（h3タグなどから）
                        try:
                            grade_elem = driver.find_element(By.CSS_SELECTOR, ".race-infoWrap h3")
                            h_data["グレード"] = grade_elem.text.strip().replace("\n", " ")
                        except: pass

                        if len(info_tables) >= 2:
                            row1 = info_tables[0].find_elements(By.CSS_SELECTOR, "tbody tr td")
                            if len(row1) >= 4:
                                h_data["日付"] = row1[0].text.strip()
                                h_data["レース名"] = row1[1].text.strip()
                                h_data["距離"] = row1[2].text.strip()
                                h_data["天候"] = row1[3].text.strip()
                            row2 = info_tables[1].find_elements(By.CSS_SELECTOR, "tbody tr td")
                            if len(row2) >= 4:
                                h_data["気温"] = row2[0].text.strip()
                                h_data["湿度"] = row2[1].text.strip()
                                h_data["走路温度"] = row2[2].text.strip()
                                h_data["走路状況"] = row2[3].text.strip()

                        # 投票締切・発走予定の取得
                        try:
                            # 締切と発走時刻が並んでいる要素を特定
                            time_elements = driver.find_elements(By.CSS_SELECTOR, ".race-infoWrap .d-block.d-md-flex div")
                            # もしくはより直接的な構成から抽出
                            deadline = driver.find_element(By.XPATH, "//*[contains(text(), '投票締切')]/following-sibling::* | //*[contains(text(), '投票締切')]/parent::*/following-sibling::*").text
                            plan = driver.find_element(By.XPATH, "//*[contains(text(), '発走予定')]/following-sibling::* | //*[contains(text(), '発走予定')]/parent::*/following-sibling::*").text
                            h_data["投票締切"] = deadline.strip()
                            h_data["発走予定"] = plan.strip()
                        except:
                            # 万が一上記で失敗した場合の予備
                            try:
                                h_data["投票締切"] = driver.find_element(By.CSS_SELECTOR, ".race-infoWrap .row .col-6:nth-child(1) div:last-child").text.strip()
                                h_data["発走予定"] = driver.find_element(By.CSS_SELECTOR, ".race-infoWrap .row .col-6:nth-child(2) div:last-child").text.strip()
                            except: pass
                        
                        for car_no in base_data:
                            base_data[car_no]["場所"] = place
                            base_data[car_no]["車"] = car_no
                            base_data[car_no].update(h_data)
                    except Exception: pass

                    # 各タブ取得
                    fetch_tab_data_robust(driver, wait, base_url + "/program", base_data, {"選手名": 1, "ハンデ": 2, "試走T": 3, "偏差": 4, "連率": 5}, "出走表")
                    fetch_tab_data_robust(driver, wait, base_url + "/recent10", base_data, {f"近10_{i}": i+1 for i in range(1, 11)}, "近10走")
                    
                    f_map = {"前1":2, "前2":3, "前3":4, "前4":5, "前5":6, "平近順":7, "近況":8, "2連対率":9}
                    for b_slug, b_name in [("good5","良"), ("wet5","湿"), ("han5","斑")]:
                        fetch_tab_data_robust(driver, wait, f"{base_url}/{b_slug}", base_data, {f"{b_name}5_{k}":v for k,v in f_map.items()}, f"{b_name}5")

                    fetch_tab_data_robust(driver, wait, base_url + "/recent90", base_data, {"90出走":2, "90優出":3, "90優勝":4, "90平均ST":5, "90(近10)_各着順":6, "90(近10)_2連対率":7, "90(近10)_3連対率":8, "90(良10)平均試":9, "90(良10)平均競":10, "90(良10)最高競T(場)":11}, "90日")
                    fetch_tab_data_robust(driver, wait, base_url + "/recent180", base_data, {"180良_2連対率":2, "180良_連対回数":3, "180良_出走数":4, "180湿_2連対率":5, "180湿_連対回数":6, "180湿_出走数":7}, "180日")
                    fetch_tab_data_robust(driver, wait, base_url + "/recent365", base_data, {"今年_優出":2, "今年_優勝":3, "通算_優勝":4, "通算_1着":5, "通算_2着":6, "通算_3着":7, "通算_単勝率":8, "通算_2連対率":9, "通算_3連対率":10}, "年間")

                    # 保存
                    df = pd.DataFrame(base_data.values())
                    df['車'] = pd.to_numeric(df['車'], errors='coerce')
                    df = df.sort_values("車")
                    df = df[df['選手名'].notna() & (df['選手名'] != "-")]
                    df.to_csv(f"data/race_data_{place}_{race_no_str}R.csv", index=False, encoding="utf-8-sig")
                    print(f"  => {race_id} 保存完了", flush=True)

                except Exception as e:
                    print(f"  => {r}R 取得失敗: {e}", flush=True)

    finally:
        driver.quit()
        print("\n全ての処理が終了しました。", flush=True)

if __name__ == "__main__":
    main()
