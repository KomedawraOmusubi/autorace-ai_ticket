import os
import time
import datetime
import pandas as pd
import pytz
import glob
import requests
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
GAS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbz5lHeaHU1-oVjJ70CLNAdSMJaUQpzMvbne2bbhshdfCBYNqLjIwhgdX9hVcR2pKfn/exec"

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

def fetch_tab_data(driver, wait, target_url, data_map, col_indices):
    driver.get(target_url)
    try:
        WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
        t_rows = driver.find_elements(By.CSS_SELECTOR, ".liveTable tbody tr")
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
    target_times = []

    print("古いデータを削除しています...")
    if not os.path.exists("data"):
        os.makedirs("data")
    old_files = glob.glob("data/*.csv")
    for f in old_files:
        try:
            os.remove(f)
            print(f"  => 削除完了: {f}")
        except Exception as e:
            print(f"  => 削除失敗: {f} ({e})")

    now_jst = datetime.datetime.now(TOKYO_TZ)
    today_str = now_jst.strftime("%Y-%m-%d")
    places = ["kawaguchi", "sanyou", "iizuka", "hamamatsu", "isesaki"]
    driver = get_driver()
    wait = WebDriverWait(driver, 5)

    try:
        for place in places:
            print(f"--- {place.upper()} 取得開始 ---")
            
            check_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_1"
            driver.get(check_url)
            try:
                WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
            except TimeoutException:
                print(f"  => {place.upper()} は本日の開催がないか、データが未公開です。")
                continue

            for r in range(1, 13):
                race_no = str(r)
                base_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_{race_no}"
                driver.get(f"{base_url}/program")
                
                try:
                    # テーブルと発走時刻の要素を待機
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
                    wait.until(lambda d: d.find_element(By.ID, "race-result-current-race-start").text.strip() != "")
                    
                    start_time_raw = driver.find_element(By.ID, "race-result-current-race-start").text.replace("発走予定", "").strip()
                    voting_deadline = driver.find_element(By.ID, "race-result-current-race-telvote").text.strip()

                    # 発走時刻の15分前を計算して予約リストに追加
                    if ":" in start_time_raw:
                        race_time_str = f"{today_str} {start_time_raw}"
                        race_time = datetime.datetime.strptime(race_time_str, "%Y-%m-%d %H:%M")
                        # タイムゾーンを付与して現在時刻と比較可能にする
                        race_time = TOKYO_TZ.localize(race_time)
                        
                        trigger_time = race_time - datetime.timedelta(minutes=15)
                        target_datetime_str = trigger_time.strftime("%Y-%m-%dT%H:%M:00")
                        
                        # 未来の時刻のみリストに追加
                        if trigger_time > now_jst:
                            if target_datetime_str not in target_times:
                                target_times.append(target_datetime_str)
                                print(f"  => {race_no}R 予約追加: {target_datetime_str} (発走: {start_time_raw})")
                        else:
                            print(f"  => {race_no}R スキップ: 既に発走15分前を過ぎています ({target_datetime_str})")

                except Exception as e:
                    print(f"  => {race_no}R 取得失敗または終了。次の会場へ。")
                    break

                # --- データ取得処理 ---
                base_data = {}
                rows = driver.find_elements(By.CSS_SELECTOR, ".liveTable tbody tr")
                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) >= 6:
                        no = cols[0].text.strip()
                        if no.isdigit():
                            base_data[no] = {
                                "車": no, "選手名": cols[1].text.split('\n')[0].strip(),
                                "投票締切": voting_deadline, "発走予定": start_time_raw,
                                "ハンデ": cols[2].text.strip(), "試走T": "-",
                                "偏差": cols[4].text.strip(), "出走表_連率": cols[5].text.strip()
                            }

                if base_data:
                    urls = {
                        "recent10": f"{base_url}/recent10", "good5": f"{base_url}/good5", 
                        "wet5": f"{base_url}/wet5", "han5": f"{base_url}/han5", 
                        "recent90": f"{base_url}/recent90", "recent180": f"{base_url}/recent180", 
                        "recent365": f"{base_url}/recent365"
                    }

                    fetch_tab_data(driver, wait, urls["recent10"], base_data, {"前1走":2, "前2走":3, "前3走":4, "前4走":5, "前5走":6, "前6走":7, "前7走":8, "前8走":9, "前9走":10, "前10走":11})
                    for mode in ["good5", "wet5", "han5"]:
                        fetch_tab_data(driver, wait, urls[mode], base_data, {f"{mode}前1走":2, f"{mode}前2走":3, f"{mode}前3走":4, f"{mode}前4走":5, f"{mode}前5走":6, f"{mode}平順":7, f"{mode}近況":8, f"{mode}2連率":9})
                    fetch_tab_data(driver, wait, urls["recent90"], base_data, {"90出走":2, "90優出":3, "90優勝":4, "90平均ST":5, "90近10_着外":6, "90近10_2連":7, "90近10_3連":8, "90良10平試":9, "90良10平競":10, "90良10最競":11})
                    fetch_tab_data(driver, wait, urls["recent180"], base_data, {"180良2連":2, "180良連対":3, "180良出走":4, "180湿2連":5, "180湿連対":6, "180湿出走":7})
                    fetch_tab_data(driver, wait, urls["recent365"], base_data, {"今年優出":2, "今年優勝":3, "通算優勝":4, "通算1着":5, "通算2着":6, "通算3着":7, "通算単率":8, "通算2連":9, "通算3連":10})

                    df = pd.DataFrame(base_data.values()).sort_values("車")
                    filename = f"data/race_data_{place}_{race_no}R.csv"
                    df.to_csv(filename, index=False, encoding="utf-8-sig")
                    print(f"  => {filename} 保存完了")
                    time.sleep(1)

        # --- GASへスケジュール送信 ---
        if target_times:
            # 重複を排除してソート
            final_schedule = sorted(list(set(target_times)))
            # 直近の20件に絞る（必要に応じて調整）
            final_schedule = final_schedule[:20]
            
            print(f"GASへ {len(final_schedule)} 件の予約を送信しています...")
            try:
                resp = requests.post(GAS_WEBAPP_URL, json={"times": final_schedule}, timeout=10)
                print(f"GAS応答: {resp.status_code} - {resp.text}")
            except Exception as e:
                print(f"GAS送信エラー: {e}")
        else:
            print("送信対象の未来のレース予約は見つかりませんでした。")

    finally:
        driver.quit()
        print("全ての処理が終了しました。")

if __name__ == "__main__":
    main()
