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

# タイムゾーン設定
TOKYO_TZ = pytz.timezone('Asia/Tokyo')

def get_driver():
    """
    最速設定のWebDriverを生成
    """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # 【高速化】DOMが読み込まれたら次に進む（画像などは待たない）
    options.page_load_strategy = 'eager'
    # ユーザーエージェント設定
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def main():
    # 現在時刻をJSTで取得
    now = datetime.datetime.now(TOKYO_TZ)
    today_str = now.strftime("%Y-%m-%d")
    
    # 1. 処理対象のCSVファイルをリストアップ
    csv_files = glob.glob("data/race_data_*.csv")
    if not csv_files:
        print("CSVファイルが見つかりません。")
        return

    # 2. 事前に「実行が必要なレース」をフィルタリング（サイト負荷軽減）
    targets = []
    for file in csv_files:
        try:
            df = pd.read_csv(file)
            # 必須列チェック
            if '発走予定' not in df.columns or '車' not in df.columns:
                continue
                
            # 取得済み（試走Tが既にある）ならスキップ
            if '試走T' in df.columns and str(df['試走T'].iloc[0]) != "-":
                continue

            # 時刻判定
            start_val = str(df['発走予定'].iloc[0]).strip()
            if start_val in ["", "-", "nan"]:
                continue

            dep_time = TOKYO_TZ.localize(datetime.datetime.strptime(f"{today_str} {start_val}", "%Y-%m-%d %H:%M"))
            
            # 発走予定時刻より前ならリストに追加
            if now < dep_time:
                targets.append((file, df))
        except Exception as e:
            print(f"ファイル確認エラー ({file}): {e}")

    if not targets:
        print(f"[{now.strftime('%H:%M:%S')}] 実行対象のレースはありません。終了します。")
        return

    print(f"[{now.strftime('%H:%M:%S')}] {len(targets)} 件の試走タイム取得を開始します。")

    # 3. 対象がある場合のみブラウザを1回だけ起動
    driver = get_driver()
    
    try:
        for file, df in targets:
            try:
                # ファイル名から場所とレース番号を抽出
                file_name_only = os.path.basename(file).replace(".csv", "")
                parts = file_name_only.split("_")
                
                if len(parts) >= 4:
                    place = parts[2]
                    race_no = parts[3].replace("R", "")
                    target_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_{race_no}"
                else:
                    continue

                print(f"取得中: {place} {race_no}R...", end=" ", flush=True)
                driver.get(target_url)
                
                # 要素が出るまで最大10秒待機
                wait = WebDriverWait(driver, 10)
                table = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
                
                # テーブル解析
                rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
                trial_results = {}
                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) >= 4:
                        car_no = cols[0].text.strip()
                        t_time = cols[3].text.strip()
                        if car_no.isdigit() and t_time not in [".", "-", ""]:
                            trial_results[int(car_no)] = t_time
                
                if trial_results:
                    # データ更新
                    df['試走T'] = df['車'].apply(lambda x: trial_results.get(int(x), "-"))
                    df.to_csv(file, index=False, encoding="utf-8-sig")
                    print("成功")
                else:
                    print("未更新")
                
                # サイトへの配慮として最小限の待機
                time.sleep(1)

            except Exception as e:
                print(f"失敗 ({e})")
                continue

    finally:
        driver.quit()
        print("ブラウザを終了しました。")

if __name__ == "__main__":
    main()
