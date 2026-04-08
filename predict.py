import os
import time
import datetime
import pandas as pd
import pytz
import glob
import numpy as np
import re
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

def print_betting_guide(df, place, race_no):
    sdf = df.sort_values('予想スコア', ascending=False).reset_index(drop=True)
    top1 = int(sdf.iloc[0]['車'])
    top2 = int(sdf.iloc[1]['車'])
    top3 = int(sdf.iloc[2]['車'])
    
    ana_candidates = sdf.iloc[3:][(sdf['上昇評価'] >= 10) | (sdf['逃げ評価'] >= 15)]
    ana = int(ana_candidates.iloc[0]['車']) if not ana_candidates.empty else None

    print("\n" + "="*50)
    print(f" 【{place} {race_no}R】 直前予想・推奨買い目 ")
    print("="*50)
    
    marks = ["◎", "○", "▲", "△", "注"]
    for i in range(min(5, len(sdf))):
        car = int(sdf.iloc[i]['車'])
        score = float(sdf.iloc[i]['予想スコア'])
        tags = []
        if sdf.iloc[i]['逃げ評価'] > 0: tags.append("逃げ")
        if sdf.iloc[i]['上昇評価'] >= 10: tags.append("上昇")
        if sdf.iloc[i]['ST評価'] > 0: tags.append("ST速")
        tag_str = " ".join([f"[{t}]" for t in tags])
        print(f"{marks[i]} {car}号車 (Score: {score:5.1f}) {tag_str}")
    
    print("-" * 50)
    print(f"■ 本命 (三連単): {top1}-{top2}-{top3}, {top1}-{top3}-{top2}, {top2}-{top1}-{top3}")
    print(f"■ 本命 (二連単): {top1}-{top2}, {top2}-{top1}")
    print(f"■ 本命 (三連複): {top1}={top2}={top3}")
    
    if ana:
        print("-" * 50)
        print(f"■ 穴   (三連単): {ana}-{top1}-{top2}, {top1}-{ana}-{top2}")
        print(f"■ 穴   (二連単): {ana}-{top1}, {ana}-{top2}")
        print(f"■ 穴   (三連複): {ana}={top1}={top2}")
    print("=" * 50 + "\n")

def calculate_predictions(df):
    cols_to_fix = ['前一競走T', '前一試走', '前二競走T', '前二試走', '前三競走T', '前三試走', 
                   '前一順', '前二順', '前三順', '前一ST', '前二ST', '前三ST', '試走T', 'ハンデ', '良5順位', '偏差']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    df['平均競走タイム'] = df[['前一競走T', '前二競走T', '前三競走T']].mean(axis=1)
    df['平均試走'] = df[['前一試走', '前二試走', '前三試走']].mean(axis=1)
    df['平均順位'] = df[['前一順', '前二順', '前三順']].mean(axis=1)
    df['平均st'] = df[['前一ST', '前二ST', '前三ST']].mean(axis=1)

    df['直前予想競走タイム'] = (df['平均競走タイム'] / df['平均試走']) * df['試走T']

    df['上昇度'] = (df['前三競走T'] - df['前二競走T']) + (df['前二競走T'] - df['前一競走T'])
    df['上昇評価'] = df['上昇度'].apply(lambda x: 10 if x > 0 else (5 if x == 0 else 0))

    df['100m単価'] = df['直前予想競走タイム'] / 31.0
    df['追い上げスコア'] = 0
    for i in range(len(df)):
        my_unit = df.loc[i, '100m単価']
        followers = df.iloc[i+1:]
        if not followers.empty:
            faster_followers = followers[followers['100m単価'] < (my_unit - 0.01)]
            if not faster_followers.empty:
                df.loc[i, '追い上げスコア'] = -10

    df['逃げ評価'] = 0
    for i in [0, 1, 2]: 
        if i < len(df):
            trial_rank = df['試走T'].rank(method='min').iloc[i]
            if trial_rank <= 2 and df.loc[i, '平均st'] <= 0.15:
                df.loc[i, '逃げ評価'] = 15

    if '偏差' in df.columns:
        median_dev = df['偏差'].median()
        df['偏差評価'] = df['偏差'].apply(lambda x: 10 if x <= median_dev else 0)
    else:
        df['偏差評価'] = 0

    df['ST評価'] = 0
    if 'ハンデ' in df.columns:
        for hd in df['ハンデ'].unique():
            if pd.isna(hd): continue
            mask = df['ハンデ'] == hd
            min_st = df.loc[mask, '平均st'].min()
            df.loc[mask & (df['平均st'] == min_st), 'ST評価'] = 10

    df['タイム順位'] = df['直前予想競走タイム'].rank(method='min')
    df['タイム評価'] = df['タイム順位'].apply(lambda x: max(0, 60 - (x * 10)))

    if '良5順位' in df.columns:
        df['実績評価'] = df['良5順位'].rank(method='min').apply(lambda x: max(0, 30 - (x * 5)))
    else:
        df['実績評価'] = 0

    df['予想スコア'] = (df['タイム評価'] + df['実績評価'] + df['偏差評価'] + 
                        df['ST評価'] + df['上昇評価'] + df['追い上げスコア'] + df['逃げ評価'])
    df['予想着順'] = df['予想スコア'].rank(ascending=False, method='min')

    # --- 数値の丸め処理（タイム第2位、着順第1位） ---
    time_cols = ['平均競走タイム', '平均試走', '直前予想競走タイム', '100m単価', '試走T']
    for c in time_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').round(2)

    rank_cols = ['平均順位', '予想着順', 'タイム順位', '平均st']
    for c in rank_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').round(1)

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
                required_cols = ['前一競走T', '前二競走T', '前三競走T', '前一試走', '前二試走', '前三試走']
                missing_cols = [c for c in required_cols if c not in df.columns]
                if missing_cols:
                    continue

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
                        if car_no.isdigit() and t_time not in [".", "-", "", "0.00"]:
                            trial_results[int(car_no)] = t_time
                
                if len(trial_results) >= 6:
                    df['試走T'] = df['車'].apply(lambda x: trial_results.get(int(x), "-"))
                    df = calculate_predictions(df)
                    
                    # 最終保存前の念押し丸め
                    if '予想着順' in df.columns:
                        df['予想着順'] = pd.to_numeric(df['予想着順'], errors='coerce').round(1)
                    if '直前予想競走タイム' in df.columns:
                        df['直前予想競走タイム'] = pd.to_numeric(df['直前予想競走タイム'], errors='coerce').round(2)

                    df.to_csv(file, index=False, encoding="utf-8-sig")
                    print("成功・予想完了")
                    print_betting_guide(df, place, race_no)
                else:
                    print("未更新のためスキップ")
                
                time.sleep(1)

            except Exception as e:
                print(f"失敗 ({e})")
                continue

    finally:
        driver.quit()
        print("ブラウザを終了しました。")

if __name__ == "__main__":
    main()
