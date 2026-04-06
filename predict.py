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

TOKYO_TZ = pytz.timezone('Asia/Tokyo')

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # ユーザーエージェントを設定してブロックを回避
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def main():
    # 現在時刻をJSTで取得
    now = datetime.datetime.now(TOKYO_TZ)
    today_str = now.strftime("%Y-%m-%d")
    
    # data/ フォルダの中にあるCSVをすべて取得
    csv_files = glob.glob("data/race_data_*.csv")
    
    if not csv_files:
        print("処理対象のCSVファイル（data/*.csv）が見つかりません。")
        return

    driver = None

    for file in csv_files:
        try:
            # データの読み込み
            df = pd.read_csv(file)
            
            # 1. 発走予定時刻のチェック
            if '発走予定' not in df.columns:
                continue
                
            start_val = df['発走予定'].iloc[0]
            if pd.isna(start_val) or str(start_val).strip() in ["", "-", "nan"]:
                continue

            # 2. すでに試走タイムが取得済み（ハイフン以外）ならスキップ
            if '試走T' in df.columns and str(df['試走T'].iloc[0]) != "-":
                # print(f"スキップ: {file} (取得済み)")
                continue
                
            start_time_str = str(start_val).strip()
            # 時刻文字列をdatetimeオブジェクトに変換
            try:
                dep_time = TOKYO_TZ.localize(datetime.datetime.strptime(f"{today_str} {start_time_str}", "%Y-%m-%d %H:%M"))
            except ValueError:
                continue
            
            # 3. 【判定】現在が発走予定時刻より「前」であれば処理対象とする
            if now < dep_time:
                print(f"【実行】{file} の試走タイム確認を開始（発走予定: {start_time_str}）")
                
                # ファイル名から場所とレース番号を抽出
                file_name_only = os.path.basename(file).replace(".csv", "")
                parts = file_name_only.split("_")
                
                if len(parts) >= 4:
                    place = parts[2]
                    race_no = parts[3].replace("R", "")
                    target_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_{race_no}"
                else:
                    print(f"  => ファイル名形式エラー: {file}")
                    continue

                # WebDriverの起動
                if driver is None: 
                    driver = get_driver()
                
                driver.get(target_url)
                
                # 負荷軽減のためのランダム待機 (1.0〜3.0秒)
                time.sleep(random.uniform(1.0, 3.0))
                
                # 試走表が出るまで待機
                try:
                    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
                    # 読み込み安定待ち (1.0〜3.0秒)
                    time.sleep(random.uniform(1.0, 3.0))
                except:
                    print(f"  => サイトの読み込みに失敗しました: {target_url}")
                    continue
                
                # テーブルから試走タイム（4番目の列）を抽出
                rows = driver.find_elements(By.CSS_SELECTOR, ".liveTable tbody tr")
                trial_results = {}
                found_count = 0
                
                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) >= 4:
                        car_no_str = cols[0].text.strip()
                        trial_time_str = cols[3].text.strip() # 4列目が試走タイム
                        
                        if car_no_str.isdigit() and trial_time_str and trial_time_str not in [".", "-", ""]:
                            trial_results[int(car_no_str)] = trial_time_str
                            found_count += 1
                
                if found_count >= 1:
                    # CSVの「試走T」列を更新
                    df['試走T'] = df['車'].apply(lambda x: trial_results.get(int(x), "-"))
                    
                    # 上書き保存
                    df.to_csv(file, index=False, encoding="utf-8-sig")
                    print(f"  => 更新完了: {found_count}車分の試走タイムを保存しました。")
                else:
                    print(f"  => 試走タイムはまだ更新されていませんでした。")
                    
                # 次のファイル処理前に少し休止
                time.sleep(random.uniform(1.0, 3.0))
            
        except Exception as e:
            print(f"エラー発生 ({file}): {e}")
            continue

    if driver:
        driver.quit()
        print("ブラウザを終了しました。")

if __name__ == "__main__":
    main()
