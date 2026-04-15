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

# --- GASのURL (予約リスト送信用) ---
GAS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbyeHqZcoqijEYlaXoNVJs-XevCvP4WaQSQLsMA-_-QUuhyEQY6wJgJWzUroJaEjibEo/exec"

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument('--lang=ja-JP')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
    
    options.add_argument('--disable-blink-features=AutomationControlled')
    # GitHub ActionsでのAttributeError回避
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
        # 初期化
        for car_no in data_map:
            for key in col_indices.keys():
                data_map[car_no][key] = "-"

        container_id = f"live-program-{submenu_id}-container"

        # タブの切り替え
        if submenu_id != "program" or force_click:
            xpath = f"//*[@data-program-submenu='{submenu_id}']//a"
            try:
                target_tab = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                driver.execute_script("arguments[0].click();", target_tab)
            except:
                target_tab = driver.find_element(By.XPATH, f"//*[@data-program-submenu='{submenu_id}']")
                driver.execute_script("arguments[0].click();", target_tab)
            
            wait.until(EC.presence_of_element_located((By.ID, container_id)))
            time.sleep(random.uniform(2.0, 4.0))

        container = driver.find_element(By.ID, container_id)
        target_table = container.find_element(By.CSS_SELECTOR, "table.liveTable")

        if target_table:
            rows = target_table.find_elements(By.CSS_SELECTOR, "tbody tr")
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 2:
                    car_no = cols[0].text.strip()
                    if car_no.isdigit() and car_no in data_map:
                        for key, idx in col_indices.items():
                            if idx < len(cols):
                                val = cols[idx].text.strip()
                                if key != "_raw_info":
                                    val = val.replace("\n", " ")
                                data_map[car_no][key] = val
            print(f"      [成功] {label} 取得完了。", flush=True)
    except Exception as e:
        if label: print(f"      [エラー] {label} 取得失敗: {str(e)}", flush=True)

def add_predictions(df):
    """
    3100m追い抜き計算ロジック
    良走路: 試走平均 + 偏差 / 湿走路: 競走タイム平均
    """
    def extract_race_time(val):
        if pd.isna(val) or val == "-": return None
        nums = re.findall(r'\d+\.\d+', str(val))
        return float(nums[0]) if len(nums) >= 1 else None

    def extract_shiso_time(val):
        if pd.isna(val) or val == "-": return None
        nums = re.findall(r'\d+\.\d+', str(val))
        if len(nums) >= 2: return float(nums[-2])
        elif len(nums) == 1: return float(nums[0])
        return None

    def get_deviation(val):
        if pd.isna(val) or val == "-": return 0.070
        s = re.sub(r'\D', '', str(val))
        if len(s) == 3: return float(f"0.{s}")
        elif len(s) > 0: return float(f"0.{s.zfill(3)}")
        return 0.070

    for condition in ['良', '湿']:
        goal_arrival_times = []
        col_goal = f"前日ゴール時間({condition})"
        col_time = f"前日予想競走T({condition})"

        for idx_row, row in df.iterrows():
            car_no = str(row.get("車", ""))
            
            if condition == '湿':
                past_race_list = [extract_race_time(row.get(f"湿5_前{i}")) for i in range(1, 4) if extract_race_time(row.get(f"湿5_前{i}"))]
                agari_100m = sum(past_race_list) / len(past_race_list) if past_race_list else (extract_race_time(row.get("良5_前1")) or 3.47) + 0.35
            else:
                past_shiso_list = [extract_shiso_time(row.get(f"良5_前{i}")) for i in range(1, 4) if extract_shiso_time(row.get(f"良5_前{i}"))]
                agari_100m = (sum(past_shiso_list) / len(past_shiso_list) if past_shiso_list else 3.40) + get_deviation(row.get("偏差"))

            if car_no == "1": agari_100m -= 0.01
            
            h_str = str(row.get("ハンデ", "0"))
            handi = float(re.sub(r'\D', '', h_str)) if re.sub(r'\D', '', h_str) else 0
            arrival_time = (3100 + handi) / (100 / agari_100m)
            
            df.at[idx_row, col_time] = f"{agari_100m:.3f}"
            goal_arrival_times.append(round(arrival_time, 2))

        df[col_goal] = goal_arrival_times
        df = df.sort_values(col_goal)
        marks = ["◎", "〇", "▲", "△", "✕", " ", " ", " "]
        df[f'印({condition})'] = marks[:len(df)]
        df[f'予想着順({condition})'] = range(1, len(df) + 1)
        
    return df.sort_values('車')

def main():
    if not os.path.exists("data"): os.makedirs("data")
    for f in glob.glob("data/*.csv"):
        try: os.remove(f)
        except: pass

    now_jst = datetime.datetime.now(TOKYO_TZ)
    today_str = now_jst.strftime("%Y-%m-%d")
    today_id = now_jst.strftime("%Y%m%d")

    driver = get_driver()
    wait = WebDriverWait(driver, 20)
    target_times = [] # GAS予約時刻リスト

    try:
        print(f"\n--- スクレイピング開始 ({today_str}) ---", flush=True)
        driver.get("https://autorace.jp/")
        time.sleep(3)
        
        place_map = {"川口": "kawaguchi", "山陽": "sanyou", "飯塚": "iizuka", "浜松": "hamamatsu", "伊勢崎": "isesaki"}
        active_places = []
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "todayRaceSection")))
            page_text = driver.find_element(By.CLASS_NAME, "todayRaceSection").text
            for jp_name, en_name in place_map.items():
                if jp_name in page_text: active_places.append(en_name)
            active_places = list(dict.fromkeys(active_places))
        except:
            active_places = []

        for place in active_places:
            first_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_1/program"
            driver.get(first_url)
            time.sleep(4)

            for r in range(1, 2 ):
                try:
                    race_tabs = driver.find_elements(By.XPATH, f"//*[@data-raceno='{r}']")
                    if not race_tabs: break

                    if r > 1:
                        driver.execute_script("arguments[0].click();", race_tabs[0])
                        time.sleep(random.uniform(3.5, 6.0))

                    race_no_str = str(r).zfill(2)
                    print(f"\n  ===[ {place} {r}R ]===", flush=True)

                    # メタ情報と「発走時刻」の取得
                    grade_val, date_val, race_val, dist_val, start_time = ["-"] * 5
                    try:
                        title_elem = driver.find_element(By.CSS_SELECTOR, "#race-result-race-info h3")
                        grade_val = title_elem.text.strip()
                        info_tables = driver.find_elements(By.CSS_SELECTOR, "table.race-infoTable")
                        if len(info_tables) >= 1:
                            tds1 = info_tables[0].find_elements(By.CSS_SELECTOR, "tbody tr td")
                            if len(tds1) >= 3:
                                date_val = tds1[0].text.split("\n")[0].strip()
                                race_val = tds1[1].text.strip()
                                dist_val = tds1[2].text.strip()
                        
                        # 発走予定時刻を取得してGAS予約リストへ
                        start_raw = driver.find_element(By.ID, "race-result-current-race-start").text
                        start_time = re.search(r'\d{2}:\d{2}', start_raw).group()
                        r_dt = TOKYO_TZ.localize(datetime.datetime.strptime(f"{today_str} {start_time}", "%Y-%m-%d %H:%M"))
                        t_dt = r_dt - datetime.timedelta(minutes=15)
                        if t_dt > now_jst:
                            target_times.append(t_dt.strftime("%Y-%m-%dT%H:%M:00"))
                    except: pass

                    base_data = {str(i): {} for i in range(1, 9)}
                    fetch_tab_data_by_click(driver, wait, "program", base_data, {"車": 0, "_raw_info": 1, "ハンデ": 2, "試走T": 3, "偏差": 4, "連率": 5}, "出走表", force_click=(r > 1))
                    
                    # 選手名などのバラシ処理
                    for car_no, row_data in base_data.items():
                        raw_text = row_data.get("_raw_info", "")
                        p_name, p_car, p_loc, p_gen, p_age, p_class, p_rank = ["-"] * 7
                        if raw_text and raw_text != "-":
                            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
                            if len(lines) >= 1: p_name = lines[0]
                            if len(lines) >= 2: p_car  = lines[1]
                            if len(lines) >= 3:
                                parts = re.split(r'\s+', lines[2]); p_loc, p_gen = (parts + ["-"]*2)[:2]
                            if len(lines) >= 4:
                                parts = re.split(r'\s+', lines[3]); p_age, p_class, p_rank = (parts + ["-"]*3)[:3]
                        row_data.update({"選手名":p_name,"競走車":p_car,"所属":p_loc,"期":p_gen,"年齢":p_age,"車級":p_class,"ランク":p_rank})
                        if "_raw_info" in row_data: del row_data["_raw_info"]

                    fetch_tab_data_by_click(driver, wait, "recent10", base_data, {f"近10_{i-1}": i for i in range(2, 12)}, "近10走")
                    f_map = {"前1": 2, "前2": 3, "前3": 4, "前4": 5, "前5": 6, "平近順": 7, "近況": 8, "2連対率": 9}
                    for sub_id in ["good5", "wet5", "han5"]:
                        l_prefix = "良5" if sub_id == "good5" else "湿5" if sub_id == "wet5" else "斑5"
                        fetch_tab_data_by_click(driver, wait, sub_id, base_data, {f"{l_prefix}_{k}": v for k, v in f_map.items()}, l_prefix)

                    # --- 詳細データの取得 (将来用：コメントアウト保持) ---
                    """
                    fetch_tab_data_by_click(driver, wait, "recent90", base_data, {"90出走":2, "90平均ST":5, "90平均競":10}, "近90日")
                    fetch_tab_data_by_click(driver, wait, "recent180", base_data, {"180良2連":2, "180湿2連":5}, "近180日")
                    fetch_tab_data_by_click(driver, wait, "recent365", base_data, {"通算優勝":4, "通算2連":9}, "今年/通算")
                    """

                    df = pd.DataFrame([v for v in base_data.values() if v.get("選手名") and v.get("選手名") != "-"])
                    df = add_predictions(df)

                    # カラム並び替えと挿入
                    fixed_cols = ["印(良)", "印(湿)", "車", "選手名", "ハンデ", "偏差", "前日ゴール時間(良)", "前日予想競走T(良)", "前日ゴール時間(湿)", "前日予想競走T(湿)"]
                    df = df[fixed_cols + [c for c in df.columns if c not in fixed_cols]]
                    df.insert(0, '場所', place); df.insert(1, 'グレード', grade_val); df.insert(2, '日付', date_val); df.insert(3, 'レース', race_val); df.insert(4, '発走予定', start_time)
                    
                    df.to_csv(f"data/race_data_{place}_{race_no_str}R.csv", index=False, encoding="utf-8-sig")
                    print(f"  => {place} {r}R 保存完了。", flush=True)
                    time.sleep(random.uniform(3.0, 5.0))

                except Exception as e:
                    print(f"  => {r}R 失敗: {e}", flush=True)

        # 最後に一括でGASへ予約送信
        if target_times:
            unique_times = sorted(list(set(target_times)))
            try:
                res = requests.post(GAS_WEBAPP_URL, json={"times": unique_times}, timeout=20)
                print(f"\nGAS予約送信完了: {res.status_code} ({len(unique_times)}件の予約)")
            except Exception as e:
                print(f"\nGAS送信エラー: {e}")

    finally:
        driver.quit()
        print("\n全工程終了。", flush=True)

if __name__ == "__main__":
    main()
