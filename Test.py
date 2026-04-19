import os
import pandas as pd
import requests
import visualizer

# ==========================================
# 1. 環境変数の設定
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def send_discord_message(content):
    if not WEBHOOK_URL:
        print("エラー: DISCORD_WEBHOOK_URLが取得できていません。")
        return
    data = {"content": content}
    try:
        requests.post(WEBHOOK_URL, json=data).raise_for_status()
    except Exception as e:
        print(f"Discord送信エラー: {e}")

# ==========================================
# 2. 展開ロジックの設定値
# ==========================================
TIME_BOOST = 350
ST_BOOST = 500
OUTSIDE_LINE_RATIO = {
    1: 0.0, 2: 0.0, 3: 0.0,
    4: 0.01, 5: 0.02, 6: 0.03, 
    7: 0.05, 8: 0.06
}
ST_DRIFT_RATIO = 0.03 

# --- ハンデごとのベースY座標（0m〜80mまで拡張） ---
# 10mごとに約150pxの間隔で設定しています
HANDICAP_Y_BASE = {
    0:  370,   # 0m
    10: 520,   # 10m
    20: 670,   # 20m
    30: 820,   # 30m
    40: 970,   # 40m
    50: 1120,  # 50m
    60: 1270,  # 60m
    70: 1420,  # 70m
    80: 1570,  # 80m
}

# --- 車番ごとのベースX座標 ---
CAR_X_BASE = {
    1: 270, 2: 230, 3: 260, 
    4: 120, 5: 130, 6: 140, 
    7: 30,  8: 40
}

def generate_and_send(df):
    try:
        if not WEBHOOK_URL:
            print("エラー: Webhook URLがありません。")
            return False

        calculated_positions = []
        for _, row in df.iterrows():
            car = int(row['車'])
            
            # ハンデに基づいてベースYを決定。登録がない大きなハンデは1570をデフォルトに。
            handy = int(row.get('ハンデ', 0))
            base_y = HANDICAP_Y_BASE.get(handy, 1570)
            
            # 車番に基づいてベースXを決定
            base_x = CAR_X_BASE.get(car, 150)
            
            # タイムとSTの読み込み
            trial_val = str(row.get('試走T', '')).strip()
            if trial_val in ["", "-", "nan", "欠車"]: continue
            
            try:
                trial_time = float(trial_val)
                st_val = str(row.get('平均st', '')).strip()
                avg_st = float(st_val) if st_val not in ["", "-", "nan"] else 0.25
            except: continue

            # 縦移動（速いほど上へ）
            total_upward = max(0, (3.45 - trial_time) * TIME_BOOST) + max(0, (0.25 - avg_st) * ST_BOOST)
            
            # 横移動
            base_cut_ratio = max(0, 0.08 - OUTSIDE_LINE_RATIO.get(car, 0.0))
            x_cut = total_upward * base_cut_ratio
            drift = (avg_st - 0.25) * ST_BOOST * ST_DRIFT_RATIO if avg_st > 0.25 else 0
            
            final_x = base_x - x_cut + drift
            final_y = base_y - total_upward
            
            # リミッター（1号車のスタートライン 370px 付近を最前線とする）
            calculated_positions.append({
                'car': car, 
                'x': int(max(30, final_x)), 
                'y': int(max(370, final_y))
            })

        if calculated_positions:
            img_path = visualizer.create_prediction_image(calculated_positions)
            visualizer.send_to_discord(img_path, WEBHOOK_URL)
            return True
        return False
    except Exception as e:
        print(f"エラー: {e}")
        return False

# ==========================================
# 3. テスト実行
# ==========================================
if __name__ == "__main__":
    # 0mから80mまでの混在レースを想定したテスト
    test_data = [
        {'車': 1, '試走T': 3.35, '平均st': 0.15, 'ハンデ': 0},
        {'車': 2, '試走T': 3.35, '平均st': 0.15, 'ハンデ': 20},
        {'車': 3, '試走T': 3.35, '平均st': 0.15, 'ハンデ': 20},
        {'車': 4, '試走T': 3.35, '平均st': 0.15, 'ハンデ': 50},
        {'車': 5, '試走T': 3.35, '平均st': 0.15, 'ハンデ': 50},
        {'車': 6, '試走T': 3.35, '平均st': 0.15, 'ハンデ': 80},
        {'車': 7, '試走T': 3.35, '平均st': 0.15, 'ハンデ': 80},
        {'車': 8, '試走T': 3.35, '平均st': 0.15, 'ハンデ': 80},
    ]
    df_test = pd.DataFrame(test_data)

    print("--- 処理開始 ---")
    send_discord_message("🔥 ハンデ80m対応・最終ロジックテスト配信 🔥")
    if generate_and_send(df_test):
        print("成功しました")
    else:
        print("失敗しました")
