import os
import time
import datetime
import pandas as pd
import pytz
import glob
import re
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
    options.add_argument("--window-size=1920,1080")
    # ユーザーエージェントを設定してボット判定を回避
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def get_safe_text(cols, idx):
    if idx < len(cols):
        val = cols[idx].text.strip().replace("\n", " ")
        return val if val and val != "" and val != "." else "-"
    return "-"

def get_rank_score(race_text, max_score):
    if pd.isna(race_text) or race_text == '-': return 0
    match = re.search(r'(\d+)(?=着)', str(race_text))
    if not match: return 0
    rank = int(match.group(1))
    return max(0, max_score - (rank - 1) * (max_score / 4.0))

def fetch_tab_data_robust(driver, wait, target_url, data_map, col_indices):
    """タブ切り替え後のテーブルデータを取得"""
    try:
        driver.get(target_url)
        # テンプレート読み込み待ち
        time.sleep(3.5)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".liveTable tbody tr")))
        
        t_rows = driver.find_elements(By.CSS_SELECTOR, ".liveTable tbody tr")
        for t_row in t_rows:
            t_cols = t_row.find_elements(By.TAG_NAME, "td")
            if len(t_cols) >= 2:
                # 車番の取得（クラス名にraceNumが含まれることが多い）
                t_no = t_cols[0].text.strip()
                if t_no in data_map:
                    for key, idx in col_indices.items():
                        data_map[t_no][key] = get_safe_text(t_cols, idx)
    except Exception as e:
        print(f"      取得エラー ({target_url.split('/')[-1]}): {e}")

def main():
    if not os.path.exists("data"): os.makedirs("data")
    for f in glob.glob("data/*.csv"):
        try: os.remove(f)
        except: pass

    now_jst = datetime.datetime.now(TOKYO_TZ)
    today_str, today_id = now_jst.strftime("%Y-%m-%d"), now_jst.strftime("%Y%m%d")
    places = ["kawaguchi", "sanyou", "iizuka", "hamamatsu", "isesaki"]
    driver = get_driver()
    wait = WebDriverWait(driver, 15)

    try:
        for place in places:
            print(f"\n--- {place.upper()} 取得開始 ---")
            # 開催確認
            driver.get(f"https://autorace.jp/race_info/Program/{place}/{today_str}_1")
            time.sleep(2)
            
            try:
                race_nums = [el.text for el in driver.find_elements(By.CSS_SELECTOR, ".race_number_nav li a") if el.text.isdigit()]
                if not race_nums: 
                    print(f"  => {place} は開催されていないか、番組がありません。")
                    continue
                max_race = int(race_nums[-1])
            except: continue

            for r in range(1, max_race + 1):
                race_no_str = str(r).zfill(2)
                race_id = f"{today_id}_{place}_{race_no_str}"
                base_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_{r}"
                
                try:
                    driver.get(f"{base_url}/program")
                    time.sleep(3.0)
                    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "race-infoTable")))
                    
                    # 画像1000029146.jpgに基づくレースコンディション取得
                    # テーブルが複数あるため、indexで指定
                    info_tables = driver.find_elements(By.CLASS_NAME, "race-infoTable")
                    
                    def get_info_val(table_idx, col_idx):
                        try:
                            return info_tables[table_idx].find_elements(By.TAG_NAME, "td")[col_idx].text.strip()
                        except: return "-"

                    info = {
                        "name": driver.find_element(By.CLASS_NAME, "race_title").text.strip(),
                        "dist": get_info_val(0, 2), # 距離
                        "weather": get_info_val(0, 3), # 天候
                        "temp": get_info_val(1, 0), # 気温
                        "humid": get_info_val(1, 1), # 湿度
                        "road_t": get_info_val(1, 2), # 走路温度
                        "road_c": get_info_val(1, 3), # 走路状況
                        "start": driver.find_element(By.CSS_SELECTOR, ".race_start_time, #race-result-race-period-time").text.replace("発走予定", "").strip()
                    }

                    base_data = {}
                    # 出走表（基本情報）
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".liveTable tbody tr")))
                    for row in driver.find_elements(By.CSS_SELECTOR, ".liveTable tbody tr"):
                        cols = row.find_elements(By.TAG_NAME, "td")
                        if len(cols) >= 6:
                            no = cols[0].text.strip()
                            if not no.isdigit(): continue
                            base_data[no] = {
                                "レースID": race_id, "日付": today_str, "場所": place, "レース名": info["name"],
                                "距離": info["dist"], "天候": info["weather"], "気温": info["temp"], "湿度": info["humid"],
                                "走路温度": info["road_t"], "走路状況": info["road_c"],
                                "車": no, "選手名": cols[1].text.split('\n')[0].strip(),
                                "発走予定": info["start"],
                                "ハンデ": cols[2].text.strip(), "試走T": get_safe_text(cols, 3),
                                "偏差": cols[4].text.strip(), "出走表_連率": cols[5].text.strip()
                            }

                    if base_data:
                        # 画像1000029147.jpgに基づく「良/湿/斑5走」
                        # 0:車, 1:選手, 2:前1, 3:前2, 4:前3, 5:前4, 6:前5, 7:平順, 8:近況, 9:2連
                        f_map = {"前1":2, "前2":3, "前3":4, "前4":5, "前5":6, "平順":7, "近況":8, "2連":9}
                        for b in [("good","良"), ("wet","湿"), ("patchy","斑")]:
                            fetch_tab_data_robust(driver, wait, f"{base_url}/recent5_{b[0]}", base_data, {f"{b[1]}5_{k}":v for k,v in f_map.items()})

                        # 画像1000029148.jpgに基づく「近90日」
                        # 0:車, 1:選手, 2:出走, 3:優出, 4:優勝, 5:平均ST, 6:1着, 7:2連, 8:3連, 9:平均試, 10:平均競, 11:最高競
                        fetch_tab_data_robust(driver, wait, f"{base_url}/recent90", base_data, {
                            "90出走":2, "90優出":3, "90優勝":4, "90平均ST":5, 
                            "90_1着":6, "90_2連率":7, "90_3連率":8, "90平均試":9, "90平均競":10
                        })

                        # 画像1000029149.jpgに基づく「近180日」
                        # 2:良2連, 3:良連対, 4:良出走, 5:湿2連, 6:湿連対, 7:湿出走
                        fetch_tab_data_robust(driver, wait, f"{base_url}/recent180", base_data, {
                            "180良_2連率":2, "180良_連対回数":3, "180良_出走数":4,
                            "180湿_2連率":5, "180湿_連対回数":6, "180湿_出走数":7
                        })

                        # 画像1000029150.jpgに基づく「今年/通算」
                        # 今年(2,3), 通算優勝(4,5), 1着(6), 2着(7), 3着(8), 単勝(9), 2連(10), 3連(11)
                        fetch_tab_data_robust(driver, wait, f"{base_url}/total", base_data, {
                            "今年_優出":2, "今年_優勝":3, "通算_優勝":5, 
                            "通算_1着":6, "通算_2着":7, "通算_3着":8, "通算_2連率":10
                        })

                        df = pd.DataFrame(base_data.values()).sort_values("車")
                        
                        # 数値変換と計算
                        for c in ['ハンデ', '偏差', '90平均ST', '90平均競']:
                            if c in df.columns:
                                df[c] = pd.to_numeric(df[c].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
                        
                        avg_st = df['90平均ST'].mean() if '90平均ST' in df.columns else 0.15
                        times, scores = [], []
                        for _, row in df.iterrows():
                            # スコア計算（前2走の着順を重視）
                            s = get_rank_score(row.get('良5_前1', '-'), 30) + get_rank_score(row.get('良5_前2', '-'), 20)
                            bt = row.get('90平均競', 0)
                            if bt == 0: 
                                times.append(0.0); scores.append(0.0)
                            else:
                                # 簡易予想タイム：平均競走タイム + ハンデ補正 + 偏差補正 + ST補正
                                ft = bt + (row['ハンデ']*0.001) + (row['偏差']*0.1) + ((row['90平均ST']-avg_st)*0.1)
                                times.append(round(ft, 3))
                                scores.append(round(s + (3.600 - ft) * 1000, 2))
                        
                        df['予想タイム'], df['総合スコア'] = times, scores
                        df['予想着順'] = df['総合スコア'].rank(ascending=False, method='min').fillna(9).astype(int)

                        # 保存
                        df.to_csv(f"data/race_data_{place}_{race_no_str}R.csv", index=False, encoding="utf-8-sig")
                        print(f"  => {race_id} 保存完了")
                except Exception as e: 
                    print(f"  => {r}R 取得失敗: {e}")
    finally: 
        driver.quit()
        print("\n全ての処理が終了しました。")

if __name__ == "__main__":
    main()
