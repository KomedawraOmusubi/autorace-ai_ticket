import os
import math
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定と座標レールの定義
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# 走行レール（A -> B -> B_2 -> B_3 -> C）
POINT_A   = {'x': 175, 'y': 420}  # 0m地点
POINT_B   = {'x': 420, 'y': 410}  # ゴール線
POINT_B_2 = {'x': 560, 'y': 340}  # コーナー入り口
POINT_B_3 = {'x': 605, 'y': 280}  # 旋回中間地点（追加）
POINT_C   = {'x': 598, 'y': 242}  # コーナーのイン角（ターゲット）

HANDE_CONFIG = {
    0:   {'x': 175, 'y': 400}, 10:  {'x': 120, 'y': 380}, 20:  {'x': 87,  'y': 354},
    30:  {'x': 65,  'y': 323}, 40:  {'x': 45,  'y': 285}, 50:  {'x': 35,  'y': 245},
    60:  {'x': 36,  'y': 202}, 70:  {'x': 48,  'y': 163}, 80:  {'x': 68,  'y': 125},
    90:  {'x': 93,  'y': 92},  100: {'x': 125, 'y': 66}
}

# ==========================================
# 2. レール走行シミュレーション（5段階）
# ==========================================
def calculate_rail_positions(df):
    df = df.sort_values(['ハンデ', '車'])
    final_results = []
    
    # 0m選手が完走する全区間の距離を合計
    dist_ab   = math.sqrt((POINT_B['x'] - POINT_A['x'])**2 + (POINT_B['y'] - POINT_A['y'])**2)
    dist_bb2  = math.sqrt((POINT_B_2['x'] - POINT_B['x'])**2 + (POINT_B_2['y'] - POINT_B['y'])**2)
    dist_b2b3 = math.sqrt((POINT_B_3['x'] - POINT_B_2['x'])**2 + (POINT_B_3['y'] - POINT_B_2['y'])**2)
    dist_b3c  = math.sqrt((POINT_C['x'] - POINT_B_3['x'])**2 + (POINT_C['y'] - POINT_B_3['y'])**2)
    
    total_allowed_dist = dist_ab + dist_bb2 + dist_b2b3 + dist_b3c

    for _, row in df.iterrows():
        car = int(row['車'])
        handy = int(row.get('ハンデ', 0))
        config = HANDE_CONFIG[min(max(0, (handy // 10) * 10), 100)]
        
        curr_x, curr_y = config['x'], config['y']
        move_left = total_allowed_dist

        # 経由地のリスト
        waypoints = [POINT_A, POINT_B, POINT_B_2, POINT_B_3, POINT_C]

        for pt in waypoints:
            if move_left <= 0:
                break
            
            d = math.sqrt((pt['x'] - curr_x)**2 + (pt['y'] - curr_y)**2)
            if d > 0:
                m = min(move_left, d)
                curr_x += (pt['x'] - curr_x) * (m/d)
                curr_y += (pt['y'] - curr_y) * (m/d)
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
            print("送信完了：新設ポイントB_3を経由し、より滑らかなコーナリングを再現しました。")
    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    test_data = [{'車': (i % 8) + 1, 'ハンデ': i*10} for i in range(11)]
    run_simulation(pd.DataFrame(test_data))
