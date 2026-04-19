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
# 2. 展開ロジックの設定値（初期配置のみ使用）
# ==========================================
TIME_BOOST = 35
ST_BOOST = 45

# --- コース境界線の最終防衛ライン ---
Y_UPPER_LIMIT = 120  
Y_LOWER_LIMIT = 340  
X_LEFT_LIMIT = 30    
X_RIGHT_LIMIT = 280  

HANDY_X_STEP = -30  
HANDY_Y_STEP = 150  

# 初期値（この配置のみを反映します）
CAR_FORMAT_OFFSET = {
    1: {'dx': 270, 'dy': 0},
    2: {'dx': 230, 'dy': 90},
    3: {'dx': 260, 'dy': 180},
    4: {'dx': 120, 'dy': 70},
    5: {'dx': 130, 'dy': 160},
    6: {'dx': 140, 'dy': 250},
    7: {'dx': 140, 'dy': 340}, 
    8: {'dx': 50,  'dy': 340}, 
}

def generate_and_send(df):
    try:
        if not WEBHOOK_URL:
            print("エラー: Webhook URLがありません。")
            return False

        calculated_positions = []
        for _, row in df.iterrows():
            car = int(row['車'])
            handy = int(row.get('ハンデ', 0))
            
            # --- 1. 初期位置計算（ここだけを活かす） ---
            effective_handy_x = min(handy, 30)
            shift_x = (effective_handy_x / 10) * HANDY_X_STEP
            shift_y = (handy / 10) * HANDY_Y_STEP
            
            offset = CAR_FORMAT_OFFSET.get(car, {'dx': 150, 'dy': 0})
            
            # 計算結果をそのまま初期値にする
            final_x = offset['dx'] + shift_x
            final_y = 350 + offset['dy'] + shift_y
            
            # --- 2. 移動量計算（コメントアウト・無効化） ---
            # trial_time = float(row.get('試走T', 3.45))
            # avg_st = float(row.get('平均st', 0.25))
            # total_upward = max(0, (3.45 - trial_time) * TIME_BOOST) + max(0, (0.25 - avg_st) * ST_BOOST)
            total_upward = 0
            
            # --- 3. イン切り込みロジック（コメントアウト・無効化） ---
            # x_cut = total_upward * (0.15 + (handy / 10) * 0.03)
            # drift = (avg_st - 0.25) * ST_BOOST * 0.01 if avg_st > 0.25 else 0
            x_cut = 0
            drift = 0
            
            # --- 4. 座標統合とリミッター（初期配置がはみ出さないよう一応適用） ---
            final_x = max(X_LEFT_LIMIT, min(X_RIGHT_LIMIT, final_x))
            final_y = max(Y_UPPER_LIMIT, min(Y_LOWER_LIMIT, final_y))
            
            calculated_positions.append({
                'car': car, 
                'x': int(final_x),
                'y': int(final_y) 
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
    test_data = [
        {'車': 1, '試走T': 3.45, '平均st': 0.25, 'ハンデ': 0},
        {'車': 2, '試走T': 3.42, '平均st': 0.20, 'ハンデ': 10},
        {'車': 3, '試走T': 3.40, '平均st': 0.18, 'ハンデ': 10},
        {'車': 4, '試走T': 3.38, '平均st': 0.15, 'ハンデ': 20},
        {'車': 5, '試走T': 3.36, '平均st': 0.15, 'ハンデ': 20},
        {'車': 6, '試走T': 3.34, '平均st': 0.14, 'ハンデ': 30},
        {'車': 7, '試走T': 3.30, '平均st': 0.12, 'ハンデ': 40},
        {'車': 8, '試走T': 3.25, '平均st': 0.10, 'ハンデ': 50}, 
    ]
    df_test = pd.DataFrame(test_data)

    print("--- 初期配置のみ・ロジック完全無効化テスト ---")
    generate_and_send(df_test)
