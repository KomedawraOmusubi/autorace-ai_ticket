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

TOKYO_TZ = pytz.timezone('Asia/Tokyo')

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument('--lang=ja-JP')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--blink-settings=imagesEnabled=false')
    options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def fetch_tab_data_by_click(driver, wait, submenu_id, data_map, col_indices, label="", force_click=False):
    if label:
        print(f"      >>> [処理開始] {label} (ID: {submenu_id})", flush=True)
    try:
        # 初期化
        for car_no in data_map:
            for key in col_indices.keys():
                data_map[car_no][key] = "-"

        if submenu_id != "program" or force_click:
            # 切り替え前の状態を把握
            try:
                old_header = driver.find_element(By.CSS_SELECTOR, "table.liveTable thead").text.strip()
            except:
                old_header = ""

            xpath = f"//*[@data-program-submenu='{submenu_id}']"
            print(f"      [操作] タブをクリックします: {xpath}", flush=True)
            target_tab = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            driver.execute_script("arguments[0].click();", target_tab)
            
            print(f"      [待機] テーブルのヘッダーが切り替わるのを待っています...", flush=True)
            
            def table_switched(d):
                try:
                    new_header = d.find_element(By.CSS_SELECTOR, "table.liveTable thead").text.strip()
                    return new_header != old_header and new_header != ""
                except:
                    return False

            try:
                WebDriverWait(driver, 10).until(table_switched)
                print(f"      [検知] ヘッダーの切り替わりを確認しました。", flush=True)
            except:
                print(f"      [警告] タイムアウトしましたが、処理を続行します。", flush=True)
            
            time.sleep(1.2)

        # 最終的な表示確認
        print(f"      [待機] データテーブルの出現を最終確認中...", flush=True)
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "table.liveTable")))
        tables = driver.find_elements(By.CSS_SELECTOR, "table.liveTable")
        
        target_table = None
        for table in tables:
            if table.is_displayed():
                target_table = table
                break

        if target_table:
            print(f"      [抽出] データを読み取っています...", flush=True)
            rows = target_table.find_elements(By.CSS_SELECTOR, "tbody tr")
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 2:
                    car_no = cols[0].text.strip()
                    if car_no in data_map:
                        clean_texts = [c.text.strip().replace("\n", " ") for c in cols if c.text.strip() != ""]
                        for key, idx in col_indices.items():
                            if idx < len(clean_texts):
                                data_map[car_no][key] = clean_texts[idx]
            print(f"      [完了] {label} の取得に成功しました。", flush=True)
        else:
            print(f"      [失敗] 表示されているテーブルが見つかりませんでした。", flush=True)

    except Exception as e:
        if label: print(f"      [エラー] {label} 取得中に問題が発生しました: {e}", flush=True)

def main():
    if not os.path.exists("data"): os.makedirs("data")
    for f in glob.glob("data/*.csv"):
        try: os.remove(f)
        except: pass

    now_jst = datetime.datetime.now(TOKYO_TZ)
    today_str = now_jst.strftime("%Y-%m-%d")
    today_id = now_jst.strftime("%Y%m%d")

    driver = get_driver()
    wait = WebDriverWait(driver, 15)

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

        print(f"本日の開催場所: {active_places}", flush=True)

        for place in active_places:
            first_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_1/program"
            print(f"\n[場所: {place}] に移動します...", flush=True)
            driver.get(first_url)
            time.sleep(3)

            for r in range(1, 13):
                try:
                    race_tabs = driver.find_elements(By.XPATH, f"//*[@data-raceno='{r}']")
                    if not race_tabs: break

                    if r > 1:
                        print(f"  [操作] {r}R タブをクリックします。", flush=True)
                        driver.execute_script("arguments[0].click();", race_tabs[0])
                        time.sleep(2)

                    race_no_str = str(r).zfill(2)
                    race_id = f"{today_id}_{place}_{race_no_str}"
                    print(f"\n  ===[ {race_id} 処理開始 ]===", flush=True)

                    base_data = {str(i): {} for i in range(1, 9)}
                    
                    # 出走表
                    fetch_tab_data_by_click(driver, wait, "program", base_data, {"選手名": 1, "ハンデ": 2, "試走T": 3, "偏差": 4, "連率": 5}, "出走表", force_click=(r > 1))
                    
                    # 近10走
                    recent10_cols = {f"近10_{i}": i for i in range(1, 11)}
                    fetch_tab_data_by_click(driver, wait, "recent10", base_data, recent10_cols, "近10走")
                    
                    # --- コメントアウトセクション ---
                    """
                    # 良・湿・斑
                    f_map = {"前1":2, "前2":3, "前3":4, "前4":5, "前5":6, "平近順":7, "近況":8, "2連対率":9}
                    for sub_id in ["good5", "wet5", "han5"]:
                        l_prefix = "良5" if sub_id=="good5" else "湿5" if sub_id=="wet5" else "斑5"
                        fetch_tab_data_by_click(driver, wait, sub_id, base_data, {f"{l_prefix}_{k}":v for k,v in f_map.items()}, l_prefix)
                    
                    # 近90日
                    fetch_tab_data_by_click(driver, wait, "recent90", base_data, {"90出走":2, "90優出":3, "90優勝":4, "90平均ST":5, "90(近10)_2連対率":7}, "近90日")
                    """

                    df = pd.DataFrame(base_data.values())
                    df.insert(0, '場所', place)
                    df.insert(1, 'レース番号', r)
                    df.to_csv(f"data/race_data_{place}_{race_no_str}R.csv", index=False, encoding="utf-8-sig")
                    print(f"  => {race_id} ファイル保存完了", flush=True)

                except Exception as e:
                    print(f"  => {r}R 取得失敗: {e}", flush=True)
    finally:
        driver.quit()
        print("\n全ての処理が終了しました。", flush=True)

if __name__ == "__main__":
    main()
