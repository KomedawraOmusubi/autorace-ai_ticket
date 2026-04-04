import os
import time
import datetime
import pandas as pd
import pytz
import glob
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

TOKYO_TZ = pytz.timezone('Asia/Tokyo')

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def main():
    now = datetime.datetime.now(TOKYO_TZ)
    today_str = now.strftime("%Y-%m-%d")
    csv_files = glob.glob("race_data_*.csv")
    
    if not csv_files:
        print("処理対象のCSVが見つかりません。")
        return

    driver = None

    for file in csv_files:
        df = pd.read_csv(file)
        # すでに試走タイムが取得済みならスキップ
        if str(df['試走T'].iloc[0]) != "-":
            continue
            
        start_time_str = df['発走予定'].iloc[0]
        url = df['URL'].iloc[0]
        
        # 時刻判定
        dep_time = TOKYO_TZ.localize(datetime.datetime.strptime(f"{today_str} {start_time_str}", "%Y-%m-%d %H:%M"))
        
        # 判定条件: 発送10分前 以降 かつ 発送35分後 以内
        start_trigger = dep_time - datetime.timedelta(minutes=10)
        end_trigger = dep_time + datetime.timedelta(minutes=35)
        
        if start_trigger <= now <= end_trigger:
            print(f"【実行対象】{file} (発送: {start_time_str}) の取得を開始します。")
            
            if driver is None: driver = get_driver()
            driver.get(f"{url}/program")
            time.sleep(2)
            
            rows = driver.find_elements(By.CSS_SELECTOR, ".liveTable tbody tr")
            trial_results = {}
            found = False
            
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 4:
                    car_no = cols[0].text.strip()
                    t_time = cols[3].text.strip()
                    if car_no.isdigit() and t_time and t_time not in [".", "-", ""]:
                        trial_results[int(car_no)] = t_time
                        found = True
            
            if found:
                df['試走T'] = df['車'].map(trial_results).fillna(df['試走T'])
                df.to_csv(file, index=False, encoding="utf-8-sig")
                print(f"  => {file} の試走タイムを更新しました。")
            else:
                print(f"  => 試走データがまだありません。次回の実行(5分後)に期待します。")

    if driver:
        driver.quit()

if __name__ == "__main__":
    main()
