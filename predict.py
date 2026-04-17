import os
import time
import datetime
import pandas as pd
import pytz
import glob
import numpy as np
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# タイムゾーン設定
TOKYO_TZ = pytz.timezone('Asia/Tokyo')

# Discord Webhook設定 (GitHub Secretsから取得)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
# GASのウェブアプリURL (リトライ停止用)
GAS_WEBAPP_URL = os.environ.get("GAS_WEBAPP_URL")

def send_discord_message(content):
    """Discordにメッセージを送信する"""
    if not DISCORD_WEBHOOK_URL:
        print("Warning: DISCORD_WEBHOOK_URL is not set.")
        return
    
    data = {"content": content}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=data)
        response.raise_for_status()
    except Exception as e:
        print(f"Discord送信エラー: {e}")

def notify_gas_completion(place, race_no):
    """GASに予想完了を通知し、リトライを停止させる"""
    if not GAS_WEBAPP_URL:
        print("Warning: GAS_WEBAPP_URL is not set. Skipping notification.")
        return
    
    data = {
        "action": "complete",
        "place": place,
        "race_no": race_no
    }
    try:
        response = requests.post(GAS_WEBAPP_URL, json=data)
        print(f"GAS完了通知送信: {response.text}")
    except Exception as e:
        print(f"GAS通知エラー: {e}")

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

def calculate_predictions(df, weather_prefix="良5"):
    """
    CSV内の「良5_前1」「湿5_前1」等のセル文字列から数値を抽出し、計算を行う
    """
    def extract_metrics(text):
        if pd.isna(text) or text == "-" or str(text).strip() == "":
            return None, None, None, None
        
        times = re.findall(r"\d+\.\d+", str(text))
        rank_match = re.search(r"(\d+)着", str(text))
        
        race_t = float(times[0]) if len(times) >= 1 else None
        trial_t = float(times[1]) if len(times) >= 2 else None
        st = float(times[2]) if len(times) >= 3 else None
        rank = int(rank_match.group(1)) if rank_match else None
        
        return race_t, trial_t, st, rank

    for i in range(1, 4):
        col_name = f"{weather_prefix}_前{i}"
        if col_name in df.columns:
            metrics = df[col_name].apply(extract_metrics)
            df[f'temp_競走T_{i}'] = metrics.apply(lambda x: x[0])
            df[f'temp_試走T_{i}'] = metrics.apply(lambda x: x[1])
            df[f'temp_ST_{i}'] = metrics.apply(lambda x: x[2])
            df[f'temp_順位_{i}'] = metrics.apply(lambda x: x[3])

    num_cols = ['試走T', 'ハンデ', '偏差', '良5平均順位']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    df['平均競走タイム'] = df[[f'temp_競走T_{i}' for i in range(1, 4)]].mean(axis=1)
    df['平均試走'] = df[[f'temp_試走T_{i}' for i in range(1, 4)]].mean(axis=1)
    df['平均順位'] = df[[f'temp_順位_{i}' for i in range(1, 4)]].mean(axis=1)
    df['平均st'] = df[[f'temp_ST_{i}' for i in range(1, 4)]].mean(axis=1)

    df['直前予想競走T'] = (df['平均競走タイム'] - df['平均試走']) + df['試走T']

    df['上昇度'] = (df['temp_競走T_3'] - df['temp_競走T_2']) + (df['temp_競走T_2'] - df['temp_競走T_1'])
    df['上昇評価'] = df['上昇度'].apply(lambda x: 10 if (not pd.isna(x) and x > 0) else (5 if x == 0 else 0))

    df['100m単価'] = df['直前予想競走T'] / 31.0
    df['追い上げスコア'] = 0
    for i in range(len(df)):
        my_unit = df.loc[i, '100m単価']
        if pd.isna(my_unit): continue
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
        df['偏差評価'] = df['偏差'].apply(lambda x: 10 if (not pd.isna(x) and x <= median_dev) else 0)
    else:
        df['偏差評価'] = 0

    df['ST評価'] = 0
    if 'ハンデ' in df.columns:
        for hd in df['ハンデ'].unique():
            if pd.isna(hd): continue
            mask = df['ハンデ'] == hd
            min_st = df.loc[mask, '平均st'].min()
            if not pd.isna(min_st):
                df.loc[mask & (df['平均st'] == min_st), 'ST評価'] = 10

    df['タイム順位'] = df['直前予想競走T'].rank(method='min')
    df['タイム評価'] = df['タイム順位'].apply(lambda x: max(0, 60 - (x * 10)) if not pd.isna(x) else 0)

    if '良5_平均順位' in df.columns:
        df['実績評価'] = df['良5_平均順位'].rank(method='min').apply(lambda x: max(0, 30 - (x * 5)) if not pd.isna(x) else 0)
    else:
        df['実績評価'] = 0

    df['予想スコア'] = (df['タイム評価'] + df['実績評価'] + df['偏差評価'] + 
                        df['ST評価'] + df['上昇評価'] + df['追い上げスコア'] + df['逃げ評価'])
    df['予想着順'] = df['予想スコア'].rank(ascending=False, method='min')

    target_2f_cols = ['平均競走タイム', '平均試走', '直前予想競走T']
    for col in target_2f_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').map(lambda x: f"{x:.2f}" if pd.notnull(x) else x)

    df['平均st'] = pd.to_numeric(df['平均st'], errors='coerce').map(lambda x: f"{x:.2f}" if pd.notnull(x) else x)
    df['上昇度'] = pd.to_numeric(df['上昇度'].fillna(0), errors='coerce').map(lambda x: f"{x:.3f}" if pd.notnull(x) else x)

    rank_cols = ['平均順位', '予想着順', 'タイム順位']
    for c in rank_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').round(1)

    return df

def print_betting_guide(df, place, race_no, info_dict):
    sdf = df.sort_values('予想スコア', ascending=False).reset_index(drop=True)
    top1 = int(sdf.iloc[0]['車'])
    top2 = int(sdf.iloc[1]['車'])
    top3 = int(sdf.iloc[2]['車'])
    
    ana_candidates = sdf.iloc[3:][(sdf['上昇評価'] >= 10) | (sdf['逃げ評価'] >= 15)]
    ana = int(ana_candidates.iloc[0]['車']) if not ana_candidates.empty else None

    msg = []
    msg.append(f"**【{place} {race_no}R】 直前予想・推奨買い目**")
    msg.append(f"状況: {info_dict['天候']} / 路面:{info_dict['走路状況']}({info_dict['走路温度']}℃) / 気温:{info_dict['気温']} / 湿度:{info_dict['湿度']}")
    msg.append("```")
    
    marks = ["◎", "○", "▲", "△", "注"]
    for i in range(min(5, len(sdf))):
        car = int(sdf.iloc[i]['車'])
        score = float(sdf.iloc[i]['予想スコア'])
        tags = []
        if sdf.iloc[i]['逃げ評価'] > 0: tags.append("逃げ")
        if sdf.iloc[i]['上昇評価'] >= 10: tags.append("上昇")
        if sdf.iloc[i]['ST評価'] > 0: tags.append("ST速")
        tag_str = " ".join([f"[{t}]" for t in tags])
        msg.append(f"{marks[i]} {car}号車 (Score: {score:5.1f}) {tag_str}")
    
    msg.append("-" * 30)
    msg.append(f"■ 本命 (三連単): {top1}-{top2}-{top3}, {top1}-{top3}-{top2}, {top2}-{top1}-{top3}")
    msg.append(f"■ 本命 (二連単): {top1}-{top2}, {top2}-{top1}")
    msg.append(f"■ 本命 (三連複): {top1}={top2}={top3}")
    
    if ana:
        msg.append("-" * 30)
        msg.append(f"■ 穴   (三連単): {ana}-{top1}-{top2}, {top1}-{ana}-{top2}")
        msg.append(f"■ 穴   (二連単): {ana}-{top1}, {ana}-{top2}")
        msg.append(f"■ 穴   (三連複): {ana}={top1}={top2}")
    msg.append("```")
    
    final_msg = "\n".join(msg)
    print("\n" + final_msg)
    send_discord_message(final_msg)

def main():
    now = datetime.datetime.now(TOKYO_TZ)
    today_str = now.strftime("%Y-%m-%d")
    
    print(f"[{now.strftime('%H:%M:%S')}] --- デバッグ開始 ---")
    print(f"実行ディレクトリ: {os.getcwd()}")
    
    csv_files = glob.glob("data/race_data_*.csv")
    if not csv_files:
        print("CSVファイルが data/ フォルダ内に見つかりません。")
        return

    targets = []
    for file in csv_files:
        try:
            df = pd.read_csv(file)
            print(f"\n[ファイル確認: {file}]")
            
            # カラム確認
            if '発走予定' not in df.columns or '車' not in df.columns:
                print(f"-> スキップ: 必須カラム('発走予定' or '車')がありません。 カラム名: {list(df.columns)}")
                continue

            # 予想済みチェック (現在のロジックに合わせる)
            if '予想着順' in df.columns and not pd.isna(df['予想着順'].iloc[0]):
                print(f"-> スキップ: '予想着順'カラムに既に値があります。")
                continue

            start_val = str(df['発走予定'].iloc[0]).strip()
            print(f"-> CSVの発走予定値: '{start_val}'")

            if start_val in ["", "-", "nan"]:
                print(f"-> スキップ: 発走予定時刻が空データです。")
                continue

            # 時刻変換と判定
            try:
                dep_time = TOKYO_TZ.localize(datetime.datetime.strptime(f"{today_str} {start_val}", "%Y-%m-%d %H:%M"))
                print(f"-> 日本時間変換: {dep_time.strftime('%H:%M:%S')}")
                
                if now < dep_time:
                    print(f"-> 判定: OK (現在 {now.strftime('%H:%M')} < 予定 {start_val})")
                    targets.append((file, df))
                else:
                    print(f"-> 判定: スキップ (既に発走時刻を過ぎています)")
            except Exception as time_err:
                print(f"-> 時刻変換エラー: {time_err}")

        except Exception as e:
            print(f"-> ファイル読み込みエラー ({file}): {e}")

    if not targets:
        print(f"\n[{now.strftime('%H:%M:%S')}] 実行対象のレースはありませんでした。終了します。")
        return

    print(f"\n[{now.strftime('%H:%M:%S')}] {len(targets)} 件の処理を開始します。")

    driver = get_driver()
    
    try:
        for file, df in targets:
            try:
                file_name_only = os.path.basename(file).replace(".csv", "")
                parts = file_name_only.split("_")
                
                if len(parts) >= 3:
                    place = parts[-2]
                    race_no = parts[-1].replace("R", "")
                    target_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_{race_no}"
                else:
                    print(f"{file}: ファイル名形式が不正です。")
                    continue

                print(f"取得中: {place} {race_no}R...", end=" ", flush=True)
                
                driver.get(target_url)
                wait = WebDriverWait(driver, 10)

                info_dict = {"天候": "-", "気温": "-", "湿度": "-", "走路温度": "-", "走路状況": "-"}
                try:
                    info_tables = driver.find_elements(By.CLASS_NAME, "race-infoTable")
                    if len(info_tables) >= 2:
                        tds1 = info_tables[0].find_elements(By.TAG_NAME, "td")
                        if len(tds1) >= 4:
                            info_dict["天候"] = tds1[3].text.strip()
                        tds2 = info_tables[1].find_elements(By.TAG_NAME, "td")
                        if len(tds2) >= 4:
                            info_dict["気温"] = tds2[0].text.strip()
                            info_dict["湿度"] = tds2[1].text.strip()
                            info_dict["走路温度"] = tds2[2].text.strip()
                            info_dict["走路状況"] = tds2[3].text.strip()
                except Exception as e:
                    print(f"(情報取得一部失敗: {e})", end=" ")

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
                    prefix = "良5"
                    if any(x in info_dict["走路状況"] for x in ["湿", "ぶち", "濡"]):
                        prefix = "湿5"
                    elif "雨" in info_dict["天候"]:
                        prefix = "湿5"

                    df = calculate_predictions(df, weather_prefix=prefix)
                    df.to_csv(file, index=False, encoding="utf-8-sig")
                    print(f"成功 ({prefix}モード)・予想完了")
                    print_betting_guide(df, place, race_no, info_dict)
                    notify_gas_completion(place, race_no)
                else:
                    print("試走タイム未更新のためスキップ")
                
                time.sleep(1)

            except Exception as e:
                print(f"失敗 ({e})")
                continue

    finally:
        driver.quit()
        print("ブラウザを終了しました。")

if __name__ == "__main__":
    main()
