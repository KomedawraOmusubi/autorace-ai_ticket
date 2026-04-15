import os
import time
import datetime
import pandas as pd
import pytz
import glob
import random
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

# --- GASのURL (GAS側のdoPostで古いトリガーを消去する運用を推奨) ---
GAS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbyeHqZcoqijEYlaXoNVJs-XevCvP4WaQSQLsMA-_-QUuhyEQY6wJgJWzUroJaEjibEo/exec"

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument('--lang=ja-JP')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
    
    options.add_argument('--disable-blink-features=AutomationControlled')
    # 【エラー修正】experimental_option ではなく add_experimental_option を使用
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    options.add_argument('--blink-settings=imagesEnabled=false')
    options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def fetch_tab_data_by_click(driver, wait, submenu_id, data_map, col_indices, label="", force_click=False):
    if label:
        print(f"      >>> [処理開始] {label} (ID: {submenu_id})", flush=True)
    try:
        container_id = f"live-program-{submenu_id}-container"
        if submenu_id != "program" or force_click:
            xpath = f"//*[@data-program-submenu='{submenu_id}']//a"
            try:
                target_tab = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                driver.execute_script("arguments[0].click();", target_tab)
            except:
                target_tab = driver.find_element(By.XPATH, f"//*[@data-program-submenu='{submenu_id}']")
                driver.execute_script("arguments[0].click();", target_tab)
            time.sleep(3.0)

        rows = driver.find_elements(By.CSS_SELECTOR, f"#{container_id} table.liveTable tbody tr")
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 2:
                car_no = cols[0].text.strip()
                if car_no.isdigit() and car_no in data_map:
                    for key, idx in col_indices.items():
                        if idx < len(cols):
                            val = cols[idx].text.strip().replace("\n", " ")
                            data_map[car_no][key] = val
    except Exception as e:
        if label: print(f"      [エラー] {label} 取得失敗: {str(e)}", flush=True)

def add_predictions(df):
    """
    3100m追い抜き計算ロジック:
    良走路: 試走平均(前1-3) + 個別偏差
    湿走路: 競走タイム平均(前1-3) をそのまま採用
    共通: 1号車補正 (-0.01)
    """
    def extract_time(val, pos=-1):
        if pd.isna(val) or val == "-": return None
        nums = re.findall(r'\d+\.\d+', str(val))
        if not nums: return None
        # 競走/試走が並んでいる場合、pos=0で左(競走)、pos=-1で右(試走)を取得
        return float(nums[pos if len(nums) > 1 else 0])

    for cond in ['良', '湿']:
        arrival_times = []
        for idx, row in df.iterrows():
            car = str(row.get("車", ""))
            
            if cond == '湿':
                # 湿の場合: 過去3走の「競走タイム」の平均
                past = [extract_time(row.get(f"湿5_前{i}"), 0) for i in range(1, 4) if extract_time(row.get(f"湿5_前{i}"), 0)]
                agari = sum(past)/len(past) if past else (extract_time(row.get("良5_前1"), 0) or 3.47) + 0.35
            else:
                # 良の場合: 過去3走の「試走タイム」平均 + 偏差
                past = [extract_time(row.get(f"良5_前{i}"), -1) for i in range(1, 4) if extract_time(row.get(f"良5_前{i}"), -1)]
                hensa_raw = re.sub(r'\D', '', str(row.get("偏差", "70")))
                hensa = float(f"0.{hensa_raw.zfill(3)}") if hensa_raw else 0.070
                agari = (sum(past)/len(past) if past else 3.40) + hensa

            # 1号車補正
            if car == "1":
                agari -= 0.01
            
            h_str = str(row.get("ハンデ", "0"))
            handi = float(re.sub(r'\D', '', h_str)) if re.sub(r'\D', '', h_str) else 0
            # 3100m到達時間計算
            arrival = (3100 + handi) / (100 / agari)
            
            df.at[idx, f"前日予想競走T({cond})"] = f"{agari:.3f}"
            arrival_times.append(round(arrival, 2))

        df[f"前日ゴール時間({cond})"] = arrival_times
        df = df.sort_values(f"前日ゴール時間({cond})")
        df[f'印({cond})'] = (["◎", "〇", "▲", "△", "✕"] + [""] * 3)[:len(df)]
        df = df.sort_values('車')
        
    return df

def main():
    if not os.path.exists("data"): os.makedirs("data")
    for f in glob.glob("data/*.csv"):
        try: os.remove(f)
        except: pass

    now_jst = datetime.datetime.now(TOKYO_TZ)
    today_str = now_jst.strftime("%Y-%m-%d")
    driver = get_driver()
    wait = WebDriverWait(driver, 15)
    target_times = []

    try:
        print(f"\n--- スクレイピング開始 ({today_str}) ---", flush=True)
        driver.get("https://autorace.jp/")
        time.sleep(3)
        
        place_links = driver.find_elements(By.CSS_SELECTOR, ".todayRaceSection .racePlaceName a")
        urls = [link.get_attribute("href") for link in place_links if "Program" in link.get_attribute("href")]

        for url in urls:
            p_code = url.split("/")[-2]
            for r in range(1, 2):
                try:
                    driver.get(f"https://autorace.jp/race_info/Program/{p_code}/{today_str}_{r}/program")
                    time.sleep(3)
                    if "該当するデータがありません" in driver.page_source: break

                    # 開催情報取得 (画像1000029267のズレ対策)
                    info_box = driver.find_element(By.ID, "race-result-race-info")
                    grade_val = info_box.find_element(By.TAG_NAME, "h3").text.strip()
                    tds = info_box.find_elements(By.CSS_SELECTOR, ".race-infoTable td")
                    date_val = tds[0].text.split("天候")[0].strip()
                    race_name = tds[1].text.strip()
                    dist_val = tds[2].text.strip()
                    
                    # 発走時刻取得とGAS予約リスト追加
                    start_raw = driver.find_element(By.ID, "race-result-current-race-start").text
                    start_time = re.search(r'\d{2}:\d{2}', start_raw).group()
                    
                    r_dt = TOKYO_TZ.localize(datetime.datetime.strptime(f"{today_str} {start_time}", "%Y-%m-%d %H:%M"))
                    t_dt = r_dt - datetime.timedelta(minutes=15)
                    if t_dt > now_jst:
                        target_times.append(t_dt.strftime("%Y-%m-%dT%H:%M:00"))

                    base_data = {str(i): {} for i in range(1, 9)}
                    fetch_tab_data_by_click(driver, wait, "program", base_data, {"車":0, "ハンデ":2, "試走T":3, "偏差":4}, "出走表", force_click=(r>1))
                    fetch_tab_data_by_click(driver, wait, "recent10", base_data, {f"近10_{i}":i+1 for i in range(10)}, "近10走")
                    for sub, pre in [("good5", "良5"), ("wet5", "湿5")]:
                        fetch_tab_data_by_click(driver, wait, sub, base_data, {f"{pre}_前{i}":i+1 for i in range(1, 6)}, pre)

                    # --- 詳細データ(将来的な拡張用コメントアウト) ---
                    """
                    fetch_tab_data_by_click(driver, wait, "recent90", base_data, {
                        "90出走":2, "90優出":3, "90優勝":4, "90平均ST":5, "90平均競":10
                    }, "近90日")
                    fetch_tab_data_by_click(driver, wait, "recent180", base_data, {
                        "180良2連":2, "180湿2連":5
                    }, "近180日")
                    fetch_tab_data_by_click(driver, wait, "recent365", base_data, {
                        "通算優勝":4, "通算2連":9
                    }, "今年/通算")
                    """

                    df_temp = pd.DataFrame([v for v in base_data.values() if v.get("車")])
                    df = add_predictions(df_temp)

                    # メタ情報の挿入
                    meta = {"場所": p_code, "グレード": grade_val, "日付": date_val, "レース": race_name, "距離": dist_val, "発走予定時刻": start_time}
                    for k, v in meta.items():
                        df.insert(0, k, v)
                    
                    df.to_csv(f"data/race_data_{p_code}_{str(r).zfill(2)}R.csv", index=False, encoding="utf-8-sig")
                    print(f"  => {p_code} {r}R 完了", flush=True)

                except Exception as e:
                    print(f"  => {r}R 失敗: {e}", flush=True)
                    break

        # 全レース終了後にGASへ一括送信
        if target_times:
            unique_times = sorted(list(set(target_times)))
            try:
                res = requests.post(GAS_WEBAPP_URL, json={"times": unique_times}, timeout=20)
                print(f"\nGAS送信完了: {res.status_code} ({len(unique_times)}件の予約)", flush=True)
            except Exception as e:
                print(f"\nGAS送信エラー: {e}", flush=True)

    finally:
        driver.quit()
        print("\n全工程終了。", flush=True)

if __name__ == "__main__":
    main()
