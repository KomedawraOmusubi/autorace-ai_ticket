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
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def main():
    now = datetime.datetime.now(TOKYO_TZ)
    today_str = now.strftime("%Y-%m-%d")
    
    # data/ フォルダの中にあるCSVを探す
    csv_files = glob.glob("data/race_data_*.csv")
    
    if not csv_files:
        print("処理対象のCSVが見つかりません。")
        return

    driver = None

    for file in csv_files:
        try:
            df = pd.read_csv(file)
            
            # 発走予定が取得できていない場合はスキップ
            start_val = df['発走予定'].iloc[0]
            if pd.isna(start_val) or str(start_val).strip() in ["", "-", "nan"]:
                continue

            # すでに試走タイムが取得済み（ハイフン以外）ならスキップ
            if str(df['試走T'].iloc[0]) != "-":
                print(f"スキップ: {file} (試走データ取得済み)")
                continue
                
            start_time_str = str(start_val).strip()
            
            # 発走予定時刻をオブジェクト化
            dep_time = TOKYO_TZ.localize(datetime.datetime.strptime(f"{today_str} {start_time_str}", "%Y-%m-%d %H:%M"))
            
            # 【重要】GASから「発走15分前」に叩かれるため、
            # 現在時刻が「発走時刻より前」であれば、そのファイルを処理対象とする
            if now < dep_time:
                print(f"【実行対象】{file} (発走予定: {start_time_str}) の試走タイム確認を開始します。")
                
                # ファイル名からURLを復元 (例: data/race_data_iizuka_1R.csv)
                file_name_only = os.path.basename(file)
                parts = file_name_only.replace(".csv", "").replace("R", "").split("_")
                
                if len(parts) >= 4:
                    place = parts[2]
                    race_no = parts[3]
                    url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_{race_no}"
                else:
                    continue

                if driver is None: driver = get_driver()
                driver.get(f"{url}/program")
                
                # 試走データが出るまで少し待機（最大10秒）
                try:
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
                    time.sleep(2) # 念のための安定待ち
                except:
                    print(f"  => サイト読み込み失敗: {file}")
                    continue
                
                rows = driver.find_elements(By.CSS_SELECTOR, ".liveTable tbody tr")
                trial_results = {}
                found = False
                
                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) >= 4:
                        car_no = cols[0].text.strip()
                        t_time = cols[3].text.strip()
                        # 数値であり、かつ空でない場合のみ採用
                        if car_no.isdigit() and t_time and t_time not in [".", "-", ""]:
                            trial_results[int(car_no)] = t_time
                            found = True
                
                if found:
                    # データを更新して保存
                    df['試走T'] = df['車'].map(trial_results).fillna(df['試走T'])
                    df.to_csv(file, index=False, encoding="utf-8-sig")
                    print(f"  => {file} の試走タイムを更新しました。")
                    
                    # ここで予測ロジックやLINE通知を呼び出すならここに追加
                else:
                    print(f"  => {file}: 試走データがまだ公開されていません。")
                    
        except Exception as e:
            print(f"ファイル処理エラー ({file}): {e}")
            continue

    if driver:
        driver.quit()

if __name__ == "__main__":
    main()
