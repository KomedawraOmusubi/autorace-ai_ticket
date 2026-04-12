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
    options.add_argument('--lang=ja-JP')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
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
    try:
        time.sleep(1.5)
        driver.get(target_url)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".liveTable, table")))
        time.sleep(1.0) 
        t_rows = driver.find_elements(By.CSS_SELECTOR, ".liveTable tbody tr, table tbody tr")
        for t_row in t_rows:
            t_cols = t_row.find_elements(By.TAG_NAME, "td")
            if len(t_cols) >= 2:
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
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    wait = WebDriverWait(driver, 20)

    try:
        for place in places:
            time.sleep(2.0)
            print(f"\n--- {place.upper()} 取得開始 ---")
            check_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_1/program"
            driver.get(check_url)
            
            # --- デバッグログ出力（安全な形式に修正） ---
            time.sleep(5.0) 
            print("DEBUG: Current URL: " + str(driver.current_url))
            print("DEBUG: Page Title: " + str(driver.title))
            # f-stringを使わずに連結することでバックスラッシュ問題を回避
            raw_html = driver.page_source[:300].replace("\n", " ")
            print("DEBUG: Page Source (Top 300): " + raw_html)
            driver.save_screenshot(f"debug_{place}.png")
            # ---------------------------------------

            try:
                # 開催確認：リンクの有無をチェック
                race_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='Program/" + place + "/" + today_str + "']")
                
                if not race_links: 
                    print(f"  => {place} は開催されていないか、要素が見つかりません。")
                    continue
                
                race_nums = []
                for l in race_links:
                    href = l.get_attribute("href")
                    match = re.search(r'_(\d+)(/|$)', href)
                    if match:
                        race_nums.append(int(match.group(1)))
                
                if not race_nums:
                    print(f"  => {place} のレース番号を取得できませんでした。")
                    continue

                max_race = min(max(race_nums), 12)
                print(f"  => {place}: 全 {max_race} レースを検出しました。")

                for r in range(1, max_race + 1):
                    time.sleep(1.5)
                    race_no_str = str(r).zfill(2)
                    race_id = f"{today_id}_{place}_{race_no_str}"
                    base_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_{r}"
                    
                    try:
                        driver.get(f"{base_url}/program")
                        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".race-infoTable, table")))
                        time.sleep(1.0)
                        
                        info_tables = driver.find_elements(By.CLASS_NAME, "race-infoTable")
                        def get_info_val(t_idx, c_idx):
                            try: return info_tables[t_idx].find_elements(By.TAG_NAME, "td")[c_idx].text.strip()
                            except: return "-"

                        try:
                            race_title = driver.find
