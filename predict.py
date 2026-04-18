import os
import time
import datetime
import pandas as pd
import pytz
import glob
import numpy as np
import re
import requests
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# タイムゾーン設定
TOKYO_TZ = pytz.timezone('Asia/Tokyo')

# Discord Webhook設定
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
GAS_WEBAPP_URL = os.environ.get("GAS_WEBAPP_URL")

def send_discord_message(content):
    if not DISCORD_WEBHOOK_URL: return
    data = {"content": content}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data).raise_for_status()
    except Exception as e:
        print(f"Discord送信エラー: {e}")

def notify_gas_completion(place, race_no):
    if not GAS_WEBAPP_URL: return
    data = {"action": "complete", "place": place, "race_no": race_no}
    try:
        requests.post(GAS_WEBAPP_URL, json=data)
    except: pass

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.page_load_strategy = 'normal'
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def calculate_predictions(df, place, info_dict, weather_prefix="良5"):
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

    # 過去5走データの展開
    for i in range(1, 6):
        col_name = f"{weather_prefix}_前{i}"
        if col_name in df.columns:
            metrics = df[col_name].apply(extract_metrics)
            df[f'前競走T_{i}'] = metrics.apply(lambda x: x[0])
            df[f'前試走T_{i}'] = metrics.apply(lambda x: x[1])
            df[f'前ST_{i}'] = metrics.apply(lambda x: x[2])
            df[f'前順位_{i}'] = metrics.apply(lambda x: x[3])

    num_cols = ['試走T', 'ハンデ', '偏差']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 中央値による基本指標の算出
    df['平均競走タイム'] = df[[f'前競走T_{i}' for i in range(1, 6)]].median(axis=1)
    df['平均試走'] = df[[f'前試走T_{i}' for i in range(1, 6)]].median(axis=1)
    df['平均順位'] = df[[f'前順位_{i}' for i in range(1, 6)]].median(axis=1)
    df['平均st'] = df[[f'前ST_{i}' for i in range(1, 6)]].median(axis=1)

    # 1. 基本予想タイム計算
    df['直前予想競走T'] = (df['平均競走タイム'] - df['平均試走']) + df['試走T']

    # 2. 【1号車補正】インコース最短走行の利点を加味
    df.loc[df['車'] == 1, '直前予想競走T'] = df.loc[df['車'] == 1, '直前予想競走T'].apply(lambda x: x - 0.01 if pd.notnull(x) else x)

    # 各種評価フラグ・スコアの初期化
    df['地元評価'] = 0
    df['ランク評価'] = 0
    df['激変評価'] = 0
    df['走路温度補正'] = 0
    df['ST評価'] = 0
    df['夜間補正'] = 0

    # 環境データの解析
    try:
        temp_val = float(re.search(r'\d+', info_dict.get("走路温度", "0")).group())
        hum_val = float(re.search(r'\d+', info_dict.get("湿度", "0")).group())
    except:
        temp_val, hum_val = 0, 0
    
    current_hour = datetime.datetime.now(TOKYO_TZ).hour

    for i in range(len(df)):
        # 3. 【地元評価】福岡エリア（飯塚含む）などの地元勢優遇
        if '所属' in df.columns and str(df.loc[i, '所属']) == place:
            df.loc[i, '地元評価'] = 8
        
        # 4. 【精密ランク評価】S級TOP10を頂点とする実力格付け
        if 'ランク' in df.columns:
            r = str(df.loc[i, 'ランク'])
            match = re.search(r'([SA])\-(\d+)', r)
            if match:
                grade, num = match.group(1), int(match.group(2))
                if grade == 'S':
                    df.loc[i, 'ランク評価'] = 20 if num <= 10 else 15
                elif grade == 'A':
                    df.loc[i, 'ランク評価'] = 10 if num <= 100 else 5
            elif r.startswith('B'):
                df.loc[i, 'ランク評価'] = 0

        # 5. 【試走激変評価】本人の中央値より明らかに速い場合の気配上昇をキャッチ
        if pd.notnull(df.loc[i, '試走T']) and pd.notnull(df.loc[i, '平均試走']):
            if df.loc[i, '平均試走'] - df.loc[i, '試走T'] >= 0.03:
                df.loc[i, '激変評価'] = 10

        # 6. 【走路温度補正】夏場などの熱い走路でタイヤ・コース管理に長ける実力者を優遇
        if temp_val >= 40:
            if 'ランク' in df.columns:
                r_str = str(df.loc[i, 'ランク'])
                if r_str.startswith('S') or (r_str.startswith('A') and re.search(r'A\-(\d+)', r_str) and int(re.search(r'A\-(\d+)', r_str).group(1)) <= 100):
                    df.loc[i, '走路温度補正'] = 5

        # 7. 【夜間・湿度補正】ナイター時間帯のエンジン出力向上を実力勢に反映
        if current_hour >= 18 and hum_val >= 60:
            if df.loc[i, 'ランク評価'] >= 10:
                df.loc[i, '夜間補正'] = 5

    # 8. 【ST評価：同ハン・イン有利】同ハン内での位置取りとスタート力を数値化
    if 'ハンデ' in df.columns:
        for hd in df['ハンデ'].unique():
            if pd.isna(hd): continue
            mask = df['ハンデ'] == hd
            subset = df[mask].sort_values('車')
            if subset.empty: continue
            
            # 同ハン最速加点
            min_st = subset['平均st'].min()
            if not pd.isna(min_st):
                df.loc[mask & (df['平均st'] == min_st), 'ST評価'] += 10
            
            # インの主張（外側より極端に遅くなければコース死守）
            for j in range(len(subset) - 1):
                curr_idx, out_idx = subset.index[j], subset.index[j+1]
                if pd.notnull(subset.loc[curr_idx, '平均st']) and pd.notnull(subset.loc[out_idx, '平均st']):
                    if subset.loc[curr_idx, '平均st'] <= (subset.loc[out_idx, '平均st'] + 0.01):
                        df.loc[curr_idx, 'ST評価'] += 7

    # 9. 【試走落差（詐欺）警戒】試走は速いがスタートが遅い、包まれリスクのある選手を減点
    avg_st_rank = df['平均st'].rank(ascending=False) # 遅いほどランクが高い
    best_trial_car = df['試走T'].idxmin()
    if avg_st_rank.loc[best_trial_car] >= (len(df) - 1): # ワースト2位以内のスタート力
        df.loc[best_trial_car, 'ST評価'] -= 8

    # 10. 【重ハン救済・追い上げ性能】前の車を抜けるスピード差（100m単価）を評価
    df['100m単価'] = df['直前予想競走T'] / 31.0
    df['追い上げスコア'] = 0
    for i in range(len(df)):
        my_unit = df.loc[i, '100m単価']
        if pd.isna(my_unit): continue
        
        # スピード差による「捌き」加点
        predecessors = df.iloc[:i]
        if not predecessors.empty and all(predecessors['100m単価'] > (my_unit + 0.015)):
            df.loc[i, '追い上げスコア'] = 15
        
        # 後方からの圧倒的スピード勢に対するマイナス
        followers = df.iloc[i+1:]
        if not followers.empty and any(followers['100m単価'] < (my_unit - 0.02)):
            df.loc[i, '追い上げスコア'] -= 10

    # 上昇度・逃げ・偏差・タイム・実績評価
    df['上昇度'] = (df['前競走T_3'] - df['前競走T_2']) + (df['前競走T_2'] - df['前競走T_1'])
    df['上昇評価'] = df['上昇度'].apply(lambda x: 10 if (not pd.isna(x) and x > 0) else (5 if x == 0 else 0))
    df['逃げ評価'] = 0
    for i in [0, 1, 2]: 
        if i < len(df):
            trial_rank = df['試走T'].rank(method='min').iloc[i]
            if trial_rank <= 2 and df.loc[i, '平均st'] <= 0.15: df.loc[i, '逃げ評価'] = 15
    if '偏差' in df.columns:
        m_dev = df['偏差'].median()
        df['偏差評価'] = df['偏差'].apply(lambda x: 10 if (not pd.isna(x) and x <= m_dev) else 0)
    else: df['偏差評価'] = 0
    df['タイム順位'] = df['直前予想競走T'].rank(method='min')
    df['タイム評価'] = df['タイム順位'].apply(lambda x: max(0, 60 - (x * 10)) if not pd.isna(x) else 0)
    perf_col = f'{weather_prefix}_平均順位'
    df['実績評価'] = df[perf_col].rank(method='min').apply(lambda x: max(0, 30 - (x * 5))) if perf_col in df.columns else 0

    # 11. 【最終集計】
    df['予想スコア'] = (df['タイム評価'] + df['実績評価'] + df['偏差評価'] + 
                        df['ST評価'] + df['上昇評価'] + df['追い上げスコア'] + 
                        df['逃げ評価'] + df['地元評価'] + df['ランク評価'] +
                        df['激変評価'] + df['走路温度補正'] + df['夜間補正'])
    
    return df

def print_betting_guide(df, place, race_no, info_dict):
    sdf = df.sort_values('予想スコア', ascending=False).reset_index(drop=True)
    cars = [int(sdf.iloc[i]['車']) for i in range(len(sdf))]
    scores = [float(sdf.iloc[i]['予想スコア']) for i in range(len(sdf))]
    
    # 穴候補の抽出
    ana_candidates = sdf.iloc[3:][(sdf['上昇評価'] >= 10) | (sdf['激変評価'] >= 10) | (sdf['追い上げスコア'] >= 15)]
    ana = int(ana_candidates.iloc[0]['車']) if not ana_candidates.empty else None

    msg = [f"**【{place} {race_no}R】 直前予想（プロ仕様・全補正統合版）**"]
    msg.append(f"状況: {info_dict['天候']} / 路面:{info_dict['走路状況']}({info_dict['走路温度']}℃)")
    msg.append("```")
    marks = ["◎", "○", "▲", "△", "注"]
    for i in range(min(5, len(sdf))):
        car = int(sdf.iloc[i]['車'])
        name = sdf.iloc[i]['選手名'] if '選手名' in sdf.columns else "不明"
        rank = sdf.iloc[i]['ランク'] if 'ランク' in sdf.columns else "-"
        score = scores[i]
        tags = []
        if sdf.iloc[i]['逃げ評価'] > 0: tags.append("逃げ")
        if sdf.iloc[i]['激変評価'] > 0: tags.append("激変")
        if sdf.iloc[i]['追い上げスコア'] >= 15: tags.append("捌き")
        if sdf.iloc[i]['走路温度補正'] > 0: tags.append("夏場")
        if sdf.iloc[i]['夜間補正'] > 0: tags.append("夜力")
        tag_str = " ".join([f"[{t}]" for t in tags])
        msg.append(f"{marks[i]} {car}号車 {name: <6} ({rank}) Score:{score:5.1f} {tag_str}")
    
    msg.append("-" * 30)

    # 12. 【買い目最適化ロジック】本命の信頼度と接戦度合いで推奨を切り替え
    diff_top = scores[0] - scores[1]
    diff_box = scores[0] - scores[2]
    
    if diff_top >= 20:
        recommend = f"◎頭固定（信頼）: {cars[0]}-{cars[1]}{cars[2]}-{cars[1]}{cars[2]}{cars[3]}"
    elif diff_box <= 5:
        recommend = f"三連単BOX推奨（激戦）: {cars[0]}, {cars[1]}, {cars[2]} (6点)"
    else:
        recommend = f"三連単通常: {cars[0]}-{cars[1]}-{cars[2]}, {cars[0]}-{cars[2]}-{cars[1]}, {cars[1]}-{cars[0]}-{cars[2]}"

    msg.append(f"■ {recommend}")
    msg.append(f"■ 二連単: {cars[0]}-{cars[1]}, {cars[1]}-{cars[0]}")
    msg.append(f"■ 三連複BOX: {cars[0]}, {cars[1]}, {cars[2]}, {cars[3]} (4点)")
    
    if ana:
        ana_name = sdf[sdf['車'] == ana]['選手名'].iloc[0] if '選手名' in sdf.columns else "穴候補"
        msg.append("-" * 30)
        msg.append(f"■ 穴候補: {ana}号車 ({ana_name})")
        msg.append(f"■ 穴三連単: {ana}-{cars[0]}-{cars[1]}, {cars[0]}-{ana}-{cars[1]}")
    msg.append("```")
    
    final_msg = "\n".join(msg)
    print(final_msg)
    send_discord_message(final_msg)

def main():
    now = datetime.datetime.now(TOKYO_TZ)
    today_str = now.strftime("%Y-%m-%d")
    csv_files = glob.glob("data/race_data_*.csv")
    if not csv_files: return

    targets = []
    for file in csv_files:
        try:
            df = pd.read_csv(file)
            start_val = str(df['発走予定'].iloc[0]).strip()
            if start_val in ["", "-", "nan"]: continue
            dep_time = TOKYO_TZ.localize(datetime.datetime.strptime(f"{today_str} {start_val}", "%Y-%m-%d %H:%M"))
            if now < dep_time < (now + datetime.timedelta(minutes=30)):
                targets.append((file, df, dep_time))
        except: continue

    if not targets: return
    driver = get_driver()
    try:
        for file, df, dep_time in targets:
            try:
                fname = os.path.basename(file).replace(".csv", "")
                parts = fname.split("_")
                place, race_no = parts[-2], parts[-1].replace("R", "")
                driver.get(f"https://autorace.jp/race_info/Program/{place}/{today_str}_{race_no}")
                time.sleep(3)
                wait = WebDriverWait(driver, 15)
                
                info_dict = {"天候": "-", "走路状況": "-", "走路温度": "-", "気温": "-", "湿度": "-"}
                try:
                    info_tables = driver.find_elements(By.CLASS_NAME, "race-infoTable")
                    if len(info_tables) >= 2:
                        tds1, tds2 = info_tables[0].find_elements(By.TAG_NAME, "td"), info_tables[1].find_elements(By.TAG_NAME, "td")
                        info_dict.update({
                            "天候": tds1[3].text, 
                            "気温": tds2[0].text, 
                            "湿度": tds2[1].text, # 湿度取得追加
                            "走路温度": tds2[2].text, 
                            "走路状況": tds2[3].text
                        })
                except: pass

                table = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "liveTable")))
                rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
                trial_results = {int(cols[0].text.strip()): cols[3].text.strip() for row in rows if len(cols := row.find_elements(By.TAG_NAME, "td")) >= 4 if cols[0].text.strip().isdigit() and cols[3].text.strip() not in [".", "-", "0.00"]}
                
                if len(trial_results) >= 6:
                    df['試走T'] = df['車'].apply(lambda x: trial_results.get(int(x), "-"))
                    prefix = "湿5" if any(x in info_dict["走路状況"] for x in ["湿", "ぶち", "濡"]) or "雨" in info_dict["天候"] else "良5"
                    df = calculate_predictions(df, place, info_dict, weather_prefix=prefix)
                    df.to_csv(file, index=False, encoding="utf-8-sig")
                    print_betting_guide(df, place, race_no, info_dict)
                    notify_gas_completion(place, race_no)
                else:
                    if now < dep_time + datetime.timedelta(minutes=15) and GAS_WEBAPP_URL:
                        r_time = (datetime.datetime.now(TOKYO_TZ) + datetime.timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
                        requests.post(GAS_WEBAPP_URL, json={"times": [r_time], "is_retry": True})
            except: pass
    finally: driver.quit()

if __name__ == "__main__":
    main()
