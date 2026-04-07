import os
import time
import datetime
import pandas as pd
import pytz
import glob
import numpy as np
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
    options.page_load_strategy = 'eager'
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def calculate_predictions(df):
    """
    直前予想ロジックの実装
    """
    # 1. 数値変換（計算不能な文字列をNaNにする）
    cols_to_fix = ['前一競走T', '前一試走', '前二競走T', '前二試走', '前三競走T', '前三試走', 
                   '前一順', '前二順', '前三順', '前一ST', '前二ST', '前三ST', '試走T']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 2. 平均値の算出
    df['平均競走タイム'] = df[['前一競走T', '前二競走T', '前三競走T']].mean(axis=1)
    df['平均試走'] = df[['前一試走', '前二試走', '前三試走']].mean(axis=1)
    df['平均順位'] = df[['前一順', '前二順', '前三順']].mean(axis=1)
    df['平均st'] = df[['前一ST', '前二ST', '前三ST']].mean(axis=1)

    # 3. 直前予想競走タイムの算出
    # 式: (平均競走タイム ÷ 平均試走) × 試走タイム
    df['直前予想競走タイム'] = (df['平均競走タイム'] / df['平均試走']) * df['試走T']

    # 4. 偏差判定（出場選手の中央値と比較）
    # 偏差(ここでは良5走などの順位やタイムのバラツキを想定)
    if '偏差' in df.columns:
        median_dev = df['偏差'].median()
        df['偏差評価'] = df['偏差'].apply(lambda x: 10 if x <= median_dev else 0)
    else:
        df['偏差評価'] = 0

    # 5. ST評価（同ハンの選手間での比較）
    df['ST評価'] = 0
    if 'ハンデ' in df.columns:
        for hd in df['ハンデ'].unique():
            mask = df['ハンデ'] == hd
            if mask.any():
                min_st = df.loc[mask, '平均st'].min()
                # 同ハン内で最も平均STが速い選手に加点
                df.loc[mask & (df['平均st'] == min_st), 'ST評価'] = 10

    # 6. 配点式によるスコアリング
    # 予想タイムが速い順にスコア（1位:50点、2位:40点...）
    df['タイム順位'] = df['直前予想競走タイム'].rank(method='min')
    df['タイム評価'] = df['タイム順位'].apply(lambda x: max(0, 60 - (x * 10)))

    # 良5順位の評価（小さいほど良い）
    if '良5順位' in df.columns:
        df['良5順位'] = pd.to_numeric(df['良5順位'], errors='coerce')
        df['実績評価'] = df['良5順位'].rank(method='min').apply(lambda x: max(0, 30 - (x * 5)))
    else:
        df['実績評価'] = 0

    # 7. 最終予想スコアと着順
    df['予想スコア'] = df['タイム評価'] + df['実績評価'] + df['偏差評価'] + df['ST評価']
    # スコアが高い順に予想着順をつける
    df['予想着順'] = df['予想スコア'].rank(ascending=False, method='min')

    return df

def main():
    now = datetime.datetime.now(TOKYO_TZ)
    today_str = now.strftime("%Y-%m-%d")
    
    csv_files = glob.glob("data/race_data_*.csv")
    if not csv_files:
        print("CSVファイルが見つかりません。")
        return

    targets = []
    for file in csv_files:
        try:
            df = pd.read_csv(file)
            if '発走予定' not in df.columns or '車' not in df.columns:
                continue
                
            # 既に予想着順まで計算済みならスキップ（必要に応じて調整）
            if '予想着順' in df.columns and not pd.isna(df['予想着順'].iloc[0]):
                continue

            start_val = str(df['発走予定'].iloc[0]).strip()
            if start_val in ["", "-", "nan"]:
                continue

            dep_time = TOKYO_TZ.localize(datetime.datetime.strptime(f"{today_str} {start_val}", "%Y-%m-%d %H:%M"))
            
            if now < dep_time:
                targets.append((file, df))
        except Exception as e:
            print(f"ファイル確認エラー ({file}): {e}")

    if not targets:
        print(f"[{now.strftime('%H:%M:%S')}] 実行対象のレースはありません。終了します。")
        return

    print(f"[{now.strftime('%H:%M:%S')}] {len(targets)} 件の処理を開始します。")

    driver = get_driver()
    
    try:
        for file, df in targets:
            try:
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
                
                wait = WebDriverWait(driver, 10)
                table = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
                
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
                    # 試走タイム更新
                    df['試走T'] = df['車'].apply(lambda x: trial_results.get(int(x), "-"))
                    
                    # --- ここで予想ロジックを実行 ---
                    df = calculate_predictions(df)
                    # ----------------------------
                    
                    df.to_csv(file, index=False, encoding="utf-8-sig")
                    print("成功・予想完了")
                else:
                    print("試走未更新のため待機")
                
                time.sleep(1)

            except Exception as e:
                print(f"失敗 ({e})")
                continue

    finally:
        driver.quit()
        print("ブラウザを終了しました。")

if __name__ == "__main__":
    main()
