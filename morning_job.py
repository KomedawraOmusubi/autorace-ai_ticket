import os
import time
import datetime
import pandas as pd
import pytz
import glob
import re
import random  # ★追加
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
        # ★ 旧テーブルを保持（更新検知用）
        old_table = None
        try:
            old_table = driver.find_element(By.CSS_SELECTOR, "table")
        except:
            pass

        driver.get(target_url)

        # ★ テーブル更新待ち（重要）
        if old_table:
            try:
                wait.until(EC.staleness_of(old_table))
            except:
                pass

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody")))
        time.sleep(random.uniform(1.5, 3.0))  # ★ランダム待機

        # ★ 表示テーブルを1つだけ取得
        tables = driver.find_elements(By.CSS_SELECTOR, "table")
        target_table = None

        for table in tables:
            if table.is_displayed():
                target_table = table
                break

        if target_table is None:
            print("      テーブルが見つからない")
            return

        t_rows = target_table.find_elements(By.CSS_SELECTOR, "tbody tr")

        for t_row in t_rows:
            t_cols = t_row.find_elements(By.TAG_NAME, "td")
            if len(t_cols) >= 2:
                t_no = t_cols[0].text.strip()
                if t_no in data_map:
                    for key, idx in col_indices.items():
                        data_map[t_no][key] = get_safe_text(t_cols, idx)

    except Exception as e:
        print("      取得エラー: " + str(e))

def main():
    if not os.path.exists("data"): os.makedirs("data")
    for f in glob.glob("data/*.csv"):
        try: os.remove(f)
        except: pass

    now_jst = datetime.datetime.now(TOKYO_TZ)
    today_str = now_jst.strftime("%Y-%m-%d")
    today_id = now_jst.strftime("%Y%m%d")

    places = ["kawaguchi", "sanyou", "iizuka", "hamamatsu", "isesaki"]

    driver = get_driver()
    wait = WebDriverWait(driver, 20)

    try:
        for place in places:
            print("\n--- " + place.upper() + " 取得開始 ---")

            valid_races = list(range(1, 13))

            print(f"  => {place}: 最大12レース取得モード")

            for r in valid_races:
                try:
                    race_no_str = str(r).zfill(2)
                    race_id = today_id + "_" + place + "_" + race_no_str
                    base_url = f"https://autorace.jp/race_info/Program/{place}/{today_str}_{r}"

                    driver.get(base_url + "/program")
                    
                    try:
                        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table")))
                    except:
                        continue

                    time.sleep(random.uniform(1.5, 3.0))

                    info_tables = driver.find_elements(By.CLASS_NAME, "race-infoTable")

                    def get_info_val(t_idx, c_idx):
                        try:
                            return info_tables[t_idx].find_elements(By.TAG_NAME, "td")[c_idx].text.strip()
                        except:
                            return "-"

                    try:
                        grade_title = driver.find_element(By.CSS_SELECTOR, "h1").text.strip()
                        race_title = driver.find_element(By.CLASS_NAME, "race_title").text.strip()
                        start_time = driver.find_element(By.CSS_SELECTOR, ".start_time").text.replace("発走予定", "").strip()
                    except:
                        grade_title, race_title, start_time = "Unknown", "Unknown", "-"

                    info = {
                        "grade": grade_title,
                        "name": race_title,
                        "dist": get_info_val(0, 2),
                        "weather": get_info_val(0, 3),
                        "temp": get_info_val(1, 0),
                        "humid": get_info_val(1, 1),
                        "road_t": get_info_val(1, 2),
                        "road_c": get_info_val(1, 3),
                        "start": start_time
                    }

                    base_data = {}
                    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

                    for row in rows:
                        cols = row.find_elements(By.TAG_NAME, "td")
                        if len(cols) >= 6:
                            no = cols[0].text.strip()
                            if not no.isdigit():
                                continue

                            base_data[no] = {
                                "レースID": race_id,
                                "日付": today_str,
                                "場所": place,
                                "グレード大会名": info["grade"],
                                "レース名": info["name"],
                                "距離": info["dist"],
                                "天候": info["weather"],
                                "気温": info["temp"],
                                "湿度": info["humid"],
                                "走路温度": info["road_t"],
                                "走路状況": info["road_c"],
                                "車": no,
                                "選手名": cols[1].text.split('\n')[0].strip(),
                                "発走予定": info["start"],
                                "ハンデ": cols[2].text.strip(),
                                "試走T": get_safe_text(cols, 3),
                                "偏差": cols[4].text.strip(),
                                "出走表_連率": cols[5].text.strip()
                            }

                    if base_data:
                        fetch_tab_data_robust(driver, wait, base_url + "/recent10", base_data, {
                            "全10_1":2, "全10_2":3, "全10_3":4, "全10_4":5, "全10_5":6,
                            "全10_6":7, "全10_7":8, "全10_8":9, "全10_9":10, "全10_10":11
                        })

                        f_map = {"前1":2, "前2":3, "前3":4, "前4":5, "前5":6, "平順":7, "近況":8, "2連":9}
                        for b in [("good5","良"), ("wet5","湿"), ("han5","斑")]:
                            fetch_tab_data_robust(driver, wait, base_url + "/" + b[0], base_data, {b[1] + "5_" + k:v for k,v in f_map.items()})

                        fetch_tab_data_robust(driver, wait, base_url + "/recent90", base_data, {
                            "90出走":2, "90優出":3, "90優勝":4, "90平均ST":5, 
                            "90_1着":6, "90_2連率":7, "90_3連率":8, "90平均試":9, "90平均競":10
                        })

                        fetch_tab_data_robust(driver, wait, base_url + "/recent180", base_data, {
                            "180良_2連率":2, "180良_連対回数":3, "180良_出走数":4,
                            "180湿_2連率":5, "180湿_連対回数":6, "180湿_出走数":7
                        })

                        fetch_tab_data_robust(driver, wait, base_url + "/recent365", base_data, {
                            "365出走":2, "365優勝":4, "365_1着":6
                        })

                        fetch_tab_data_robust(driver, wait, base_url + "/total", base_data, {
                            "今年_優出":2, "今年_優勝":3, "通算_優勝":5, 
                            "通算_1着":6, "通算_2着":7, "通算_3着":8, "通算_2連率":10
                        })

                        df = pd.DataFrame(base_data.values()).sort_values("車")

                        df.to_csv(f"data/race_data_{place}_{race_no_str}R.csv",
                                  index=False,
                                  encoding="utf-8-sig")

                        print(f"  => {race_id} 保存完了")

                except Exception as e:
                    print(f"  => {r}R エラー: {e}")

    except Exception as e:
        print("メインエラー:", e)

    finally:
        driver.quit()
        print("\n全ての処理が終了しました。")

if __name__ == "__main__":
    main()
