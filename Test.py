import os
import math
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定と座標レールの定義
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# 走行レール（この地点を順番に結んだ線の上を走る）
POINT_A = {'x': 175, 'y': 400}  # 0m地点
POINT_B = {'x': 420, 'y': 400}  # ゴール線
POINT_C = {'x': 593, 'y': 242}  # コーナーのイン角（ターゲット）

# スタート位置の辞書
HANDE_CONFIG = {
    0:   {'x': 175, 'y': 400}, 10:  {'x': 120, 'y': 380}, 20:  {'x': 87,  'y': 354},
    30:  {'x': 65,  'y': 323}, 40:  {'x': 45,  'y': 285}, 50:  {'x': 35,  'y': 245},
    60:  {'x': 36,  'y': 202}, 70:  {'x': 48,  'y': 163}, 80:  {'x': 68,  'y': 125},
    90:  {'x': 93,  'y': 92},  100: {'x': 125, 'y': 66}
}

# ==========================================
# 2. レール走行シミュレーション
# ==========================================
def calculate_rail_positions(df):
    df = df.sort_values(['ハンデ', '車'])
    final_results = []
    
    # 基準：0m選手がAからBを経てCに到達するまでの総移動距離
    dist_ab = abs(POINT_B['x'] - POINT_A['x'])
    dist_bc = math.sqrt((POINT_C['x'] - POINT_B['x'])**2 + (POINT_C['y'] - POINT_B['y'])**2)
    total_allowed_dist = dist_ab + dist_bc

    for _, row in df.iterrows():
        car = int(row['車'])
        handy = int(row.get('ハンデ', 0))
        config = HANDE_CONFIG[min(max(0, (handy // 10) * 10), 100)]
        
        curr_x, curr_y = config['x'], config['y']
        move_left = total_allowed_dist

        # 1. スタート地点から A地点へ
        d = math.sqrt((POINT_A['x'] - curr_x)**2 + (POINT_A['y'] - curr_y)**2)
        if move_left > 0:
            m = min(move_left, d)
            if d > 0:
                curr_x += (POINT_A['x'] - curr_x) * (m/d)
                curr_y += (POINT_A['y'] - curr_y) * (m/d)
            move_left -= m

        # 2. A地点から B地点へ (直線)
        if move_left > 0:
            d = abs(POINT_B['x'] - curr_x)
            m = min(move_left, d)
            curr_x += m
            curr_y = POINT_A['y'] # Yは水平固定
            move_left -= m

        # 3. B地点から C地点へ (イン切り込み)
        if move_left > 0:
            d = math.sqrt((POINT_C['x'] - curr_x)**2 + (POINT_C['y'] - curr_y)**2)
            m = min(move_left, d)
            if d > 0:
                curr_x += (POINT_C['x'] - curr_x) * (m/d)
                curr_y += (POINT_C['y'] - curr_y) * (m/d)
            move_left -= m

        final_results.append({'car': car, 'x': int(curr_x), 'y': int(curr_y)})
        
    return final_results

# ==========================================
# 3. 実行
# ==========================================
def run_simulation(df):
    try:
        positions = calculate_rail_positions(df)
        img_path = visualizer.create_prediction_image(positions)
        if img_path:
            visualizer.send_to_discord(img_path, WEBHOOK_URL)
            print("送信完了：A-B-Cレール走行により、1号車がイン角に刺さった瞬間を再現しました。")
    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    test_data = [{'車': (i % 8) + 1, 'ハンデ': i*10} for i in range(11)]
    run_simulation(pd.DataFrame(test_data))
