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
ST_BOOST = 450

# --- コース境界線の最終防衛ライン ---
Y_UPPER_LIMIT = 120  # 白線より上（芝生）には絶対に行かない
Y_LOWER_LIMIT = 340  # 画像の「8」より下（画面外）には絶対に行かない
X_LEFT_LIMIT = 30    
X_RIGHT_LIMIT = 280  

OUTSIDE_LINE_RATIO = {
    1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.01
}
ST_DRIFT_RATIO = 0.01 

HANDY_X_STEP = -30  
HANDY_Y_STEP = 150  

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
            
            # --- 1. 初期位置計算 ---
            effective_handy_x = min(handy, 30)
            shift_x = (effective_handy_x / 10) * HANDY_X_STEP
            shift_y = (handy / 10) * HANDY_Y_STEP
            
            offset = CAR_FORMAT_OFFSET.get(car, {'dx': 150, 'dy': 0})
            start_x = offset['dx'] + shift_x
            start_y = 350 + offset['dy'] + shift_y
            
            # --- 2. 移動量計算 ---
            trial_time = float(row.get('試走T', 3.45))
            avg_st = float(row.get('平均st', 0.25))
            total_upward = max(0, (3.45 - trial_time) * TIME_BOOST) + max(0, (0.25 - avg_st) * ST_BOOST)
            
            # --- 3. イン切り込みロジック ---
            handy_cut_bonus = (handy / 10) * 0.03 
            base_cut_ratio = max(0, 0.15 + handy_cut_bonus - OUTSIDE_LINE_RATIO.get(car, 0.0))
            x_cut = total_upward * base_cut_ratio
            drift = (avg_st - 0.25) * ST_BOOST * ST_DRIFT_RATIO if avg_st > 0.25 else 0
            
            # --- 4. 座標統合と全方向リミッター ---
            # 横：計算座標に「ハンデ連動密集補正」をかけ、左右リミッターで縛る
            final_x = start_x + x_cut - drift
            in_course_limit = 150 + (handy / 10) * 10
            final_x = max(in_course_limit, final_x)
            final_x = max(X_LEFT_LIMIT, min(X_RIGHT_LIMIT, final_x))

            # 縦：計算座標を「上下リミッター」で縛る
            raw_y = start_y - total_upward
            y_clamped = min(Y_LOWER_LIMIT, raw_y) # 下（後ろ）のリミッター
            final_y = max(Y_UPPER_LIMIT, y_clamped) # 上（前）のリミッター
            
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
# 3. テスト実行（1～8号車フルメンバー）
# ==========================================
if __name__ == "__main__":
    # 1号車から8号車まで、現実的かつリミッター確認用の設定
    test_data = [
        {'車': 1, '試走T': 3.45, '平均st': 0.25, 'ハンデ': 0},  # 遅め：Y=340付近
        {'車': 2, '試走T': 3.42, '平均st': 0.20, 'ハンデ': 10},
        {'車': 3, '試走T': 3.40, '平均st': 0.18, 'ハンデ': 10},
        {'車': 4, '試走T': 3.38, '平均st': 0.15, 'ハンデ': 20},
        {'車': 5, '試走T': 3.36, '平均st': 0.15, 'ハンデ': 20},
        {'車': 6, '試走T': 3.34, '平均st': 0.14, 'ハンデ': 30},
        {'車': 7, '試走T': 3.30, '平均st': 0.12, 'ハンデ': 40},
        {'車': 8, '試走T': 3.25, '平均st': 0.10, 'ハンデ': 50}, # 爆速：Y=120（白線）
    ]
    df_test = pd.DataFrame(test_data)

    print("--- 1～8号車フルメンバー・最終テスト開始 ---")
    if generate_and_send(df_test):
        print("成功しました！Discordでコース内の密集具合を確認してください。")
    else:
        print("失敗しました。")
