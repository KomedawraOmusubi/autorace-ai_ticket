import os
import time
import datetime
import pandas as pd
import pytz
import glob
import random  # ランダム待機用に追加
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
        # 初期化：古いデータが混ざらないようにする
        for car_no in data_map:
            for key in col_indices.keys():
                data_map[car_no][key] = "-"

        # コンテナID
        container_id = f"live-program-{submenu_id}-container"

        if submenu_id != "program" or force_click:
            # タブをクリック
            xpath = f"//*[@data-program-submenu='{submenu_id}']//a"
            print(f"      [操作] タブをクリック: {submenu_id}", flush=True)
            try:
                target_tab = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                driver.execute_script("arguments[0].click();", target_tab)
            except:
                target_tab = driver.find_element(By.XPATH, f"//*[@data-program-submenu='{submenu_id}']")
                driver.execute_script("arguments[0].click();", target_tab)
            
            # コンテナ内の「テーブル」が表示されるまで待機
            print(f"      [待機] コンテナ '{container_id}' 内のテーブルを待機中...", flush=True)
            wait.until(EC.presence_of_element_located((By.ID, container_id)))
            
            # テーブルの中身が読み込まれるまでランダムに待機（負荷軽減）
            time.sleep(random.uniform(1.2, 2.0))

        # ターゲットとなるコンテナを特定
        container = driver.find_element(By.ID, container_id)
        target_table = container.find_element(By.CSS_SELECTOR, "table.liveTable")

        if target_table:
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
            print(f"      [成功] {label} 取得完了。", flush=True)
        else:
            print(f"      [失敗] テーブルが見つかりませんでした。", flush=True)

    except Exception as e:
        if label: print(f"      [エラー] {label} 取得失敗: {str(e)}", flush=True)

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

        print(f"開催場所: {active_places}", flush=True)

        for place in active_places:
            first_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_1/program"
            driver.get(first_url)
            time.sleep(4)

            for r in range(1, 13):
                try:
                    race_tabs = driver.find_elements(By.XPATH, f"//*[@data-raceno='{r}']")
                    if not race_tabs: break

                    if r > 1:
                        print(f"\n  [操作] {r}Rに切り替え", flush=True)
                        driver.execute_script("arguments[0].click();", race_tabs[0])
                        time.sleep(random.uniform(2.5, 4.0)) # レース切り替えも少し長めに待機

                    race_no_str = str(r).zfill(2)
                    race_id = f"{today_id}_{place}_{race_no_str}"
                    print(f"\n  ===[ {race_id} ]===", flush=True)

                    base_data = {str(i): {} for i in range(1, 9)}
                    
                    # 出走表
                    fetch_tab_data_by_click(driver, wait, "program", base_data, {"選手名": 1, "ハンデ": 2, "試走T": 3, "偏差": 4, "連率": 5}, "出走表", force_click=(r > 1))
                    
                    # 近10走: インデックスを 2〜11（10走分）に修正
                    recent10_cols = {f"近10_{i-1}": i for i in range(2, 12)}
                    fetch_tab_data_by_click(driver, wait, "recent10", base_data, recent10_cols, "近10走")
                    
                    # 良・湿・斑
                    f_map = {"前1":2, "前2":3, "前3":4, "前4":5, "前5":6, "平近順":7, "近況":8, "2連対率":9}
                    for sub_id in ["good5", "wet5", "han5"]:
                        l_prefix = "良5" if sub_id=="good5" else "湿5" if sub_id=="wet5" else "斑5"
                        fetch_tab_data_by_click(driver, wait, sub_id, base_data, {f"{l_prefix}_{k}":v for k,v in f_map.items()}, l_prefix)
                    
                    # 近90日: ラベル名を追加
                    fetch_tab_data_by_click(driver, wait, "recent90", base_data, {
                        "90出走":2, "90優出":3, "90優勝":4, "90平均ST":5,"90(近10)_各着順":6, 
                        "90(近10)_2連対率":7, "90(近10)_3連対率":8, "90(良10)平均試":9, 
                        "90(良10)平均競":10, "90(良10)最高競T(場)":11
                    }, "近90日")

                    # 近180日
                    fetch_tab_data_by_click(driver, wait, "recent180", base_data, {
                        "180良_2連対率":2, "180良_連対回数":3, "180良_出走数":4, 
                        "180湿_2連対率":5, "180湿_連対回数":6, "180湿_出走数":7
                    }, "近180日")

                    # 今年/通算
                    fetch_tab_data_by_click(driver, wait, "recent365", base_data, {
                        "今年_優出":2, "今年_優勝":3, "通算_優勝":5, "通算_1着":6, 
                        "通算_2着":7, "通算_3着":8, "通算_単勝率":9, "通算_2連対率":10, "通算_3連対率":11
                    }, "今年/通算")

                    # 保存
                    df = pd.DataFrame(base_data.values())
                    df.insert(0, '場所', place)
                    df.insert(1, 'レース番号', r)
                    df.to_csv(f"data/race_data_{place}_{race_no_str}R.csv", index=False, encoding="utf-8-sig")
                    print(f"  => {race_id} 保存完了。次の処理まで少し休みます...", flush=True)
                    
                    # レース終了ごとにランダム休憩（負荷軽減）
                    time.sleep(random.uniform(2.0, 5.0))

                except Exception as e:
                    print(f"  => {r}R 失敗: {e}", flush=True)
    finally:
        driver.quit()
        print("\n全工程終了。お疲れ様でした。", flush=True)

if __name__ == "__main__":
    main()
