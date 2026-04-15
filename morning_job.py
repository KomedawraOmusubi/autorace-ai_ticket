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

TOKYO_TZ = pytz.timezone('Asia/Tokyo')
GAS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbyeHqZcoqijEYlaXoNVJs-XevCvP4WaQSQLsMA-_-QUuhyEQY6wJgJWzUroJaEjibEo/exec"

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def fetch_tab_data_by_click(driver, wait, submenu_id, data_map, col_indices, label="", force_click=False):
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
        
        # 確実に要素が表示されるまで待機
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f"#{container_id} table.liveTable")))
        rows = driver.find_elements(By.CSS_SELECTOR, f"#{container_id} table.liveTable tbody tr")
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 2:
                car_no = cols[0].text.strip()
                if car_no.isdigit() and car_no in data_map:
                    for key, idx in col_indices.items():
                        if idx < len(cols):
                            data_map[car_no][key] = cols[idx].text.strip().replace("\n", " ")
        print(f"      [成功] {label} 取得完了。")
    except Exception as e:
        print(f"      [エラー] {label} 取得失敗: {e}")

def add_predictions(df):
    def extract_time(val, pos=-1):
        nums = re.findall(r'\d+\.\d+', str(val))
        return float(nums[pos if len(nums) > 1 else 0]) if nums else None

    for cond in ['良', '湿']:
        arrival_times = []
        for idx, row in df.iterrows():
            car = str(row.get("車", ""))
            if cond == '湿':
                past = [extract_time(row.get(f"湿5_前{i}"), 0) for i in range(1, 4) if extract_time(row.get(f"湿5_前{i}"), 0)]
                agari = sum(past)/len(past) if past else (extract_time(row.get("良5_前1"), 0) or 3.47) + 0.35
            else:
                past = [extract_time(row.get(f"良5_前{i}"), -1) for i in range(1, 4) if extract_time(row.get(f"良5_前{i}"), -1)]
                hensa_raw = re.sub(r'\D', '', str(row.get("偏差", "70")))
                hensa = float(f"0.{hensa_raw.zfill(3)}") if hensa_raw else 0.070
                agari = (sum(past)/len(past) if past else 3.40) + hensa
            if car == "1": agari -= 0.01
            h_str = str(row.get("ハンデ", "0"))
            handi = float(re.sub(r'\D', '', h_str)) if re.sub(r'\D', '', h_str) else 0
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
    now_jst = datetime.datetime.now(TOKYO_TZ)
    today_str = now_jst.strftime("%Y-%m-%d")
    driver = get_driver()
    wait = WebDriverWait(driver, 15)
    target_times = []

    try:
        print(f"--- スクレイピング開始 ({today_str}) ---")
        driver.get("https://autorace.jp/")
        time.sleep(5)
        
        # 開催URLの取得をより確実に
        links = driver.find_elements(By.TAG_NAME, "a")
        urls = []
        for l in links:
            href = l.get_attribute("href")
            if href and "race_info/Program" in href and today_str in href:
                urls.append(href)
        urls = sorted(list(set(urls)))
        
        print(f"発見した開催URL: {len(urls)}件")

        for url in urls:
            p_code = url.split("/")[-2]
            print(f"  >>> 場所: {p_code} 処理開始")
            for r in range(1, 2):
                try:
                    driver.get(f"https://autorace.jp/race_info/Program/{p_code}/{today_str}_{r}/program")
                    time.sleep(4)
                    if "該当するデータがありません" in driver.page_source:
                        print(f"    {r}R: データなし")
                        break

                    # 基本情報
                    info_box = driver.find_element(By.ID, "race-result-race-info")
                    grade_val = info_box.find_element(By.TAG_NAME, "h3").text.strip()
                    tds = info_box.find_elements(By.CSS_SELECTOR, ".race-infoTable td")
                    date_val = tds[0].text.split("天候")[0].strip()
                    race_name = tds[1].text.strip()
                    dist_val = tds[2].text.strip()
                    
                    # 発走時刻と予約
                    start_raw = driver.find_element(By.ID, "race-result-current-race-start").text
                    start_time = re.search(r'\d{2}:\d{2}', start_raw).group()
                    r_dt = TOKYO_TZ.localize(datetime.datetime.strptime(f"{today_str} {start_time}", "%Y-%m-%d %H:%M"))
                    t_dt = r_dt - datetime.timedelta(minutes=15)
                    if t_dt > now_jst:
                        target_times.append(t_dt.strftime("%Y-%m-%dT%H:%M:00"))

                    base_data = {str(i): {} for i in range(1, 9)}
                    fetch_tab_data_by_click(driver, wait, "program", base_data, {"車":0, "ハンデ":2, "試走T":3, "偏差":4}, "出走表")
                    fetch_tab_data_by_click(driver, wait, "recent10", base_data, {f"近10_{i}":i+1 for i in range(10)}, "近10走")
                    for sub, pre in [("good5", "良5"), ("wet5", "湿5")]:
                        fetch_tab_data_by_click(driver, wait, sub, base_data, {f"{pre}_前{i}":i+1 for i in range(1, 6)}, pre)

                    # --- 詳細データ(コメントアウト保持) ---
                    # fetch_tab_data_by_click(driver, wait, "recent90", base_data, {"90平均ST":5}, "90日")

                    df = pd.DataFrame([v for v in base_data.values() if v.get("車")])
                    df = add_predictions(df)
                    meta = {"場所": p_code, "グレード": grade_val, "日付": date_val, "レース": race_name, "距離": dist_val, "発走予定": start_time}
                    for k, v in meta.items(): df.insert(0, k, v)
                    df.to_csv(f"data/race_data_{p_code}_{str(r).zfill(2)}R.csv", index=False, encoding="utf-8-sig")
                    print(f"    {r}R: 保存完了")
                except Exception as e:
                    print(f"    {r}R: エラー {e}")
                    break

        if target_times:
            unique_times = sorted(list(set(target_times)))
            res = requests.post(GAS_WEBAPP_URL, json={"times": unique_times})
            print(f"\nGAS予約送信完了: {res.status_code} ({len(unique_times)}件)")
        else:
            print("\n予約対象のレースがありませんでした（すべて発走済みか取得失敗）。")

    finally:
        driver.quit()
        print("全工程終了。")

if __name__ == "__main__":
    main()
