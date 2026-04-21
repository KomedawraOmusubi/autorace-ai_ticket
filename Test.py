import os
import math
import pandas as pd
import visualizer

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# 走行レール定義（赤線：コースの「外枠の限界線」として機能します）
POINT_A   = {'x': 175, 'y': 420}
POINT_B   = {'x': 420, 'y': 410}
POINT_B_1 = {'x': 500, 'y': 380}
POINT_B_2 = {'x': 570, 'y': 320}
POINT_B_3 = {'x': 590, 'y': 280}
POINT_C   = {'x': 598, 'y': 242}

WAYPOINTS = [POINT_A, POINT_B, POINT_B_1, POINT_B_2, POINT_B_3, POINT_C]

HANDE_CONFIG = {
    0:   {'x': 175, 'y': 400}, 10:  {'x': 120, 'y': 380}, 20:  {'x': 87,  'y': 354},
    30:  {'x': 65,  'y': 323}, 40:  {'x': 45,  'y': 285}, 50:  {'x': 35,  'y': 245},
    60:  {'x': 36,  'y': 202}, 70:  {'x': 48,  'y': 163}, 80:  {'x': 68,  'y': 125},
    90:  {'x': 93,  'y': 92},  100: {'x': 125, 'y': 66}
}

def calculate_rail_positions(df):
    df = df.sort_values(['ハンデ', '車'])
    final_results = []
    
    total_dist = 0
    for i in range(len(WAYPOINTS)-1):
        p1, p2 = WAYPOINTS[i], WAYPOINTS[i+1]
        total_dist += math.sqrt((p2['x']-p1['x'])**2 + (p2['y']-p1['y'])**2)

    for _, row in df.iterrows():
        car = int(row['car'] if 'car' in row else row['車'])
        handy = int(row.get('ハンデ', 0))
        config = HANDE_CONFIG[min(max(0, (handy // 10) * 10), 100)]
        
        curr_x, curr_y = config['x'], config['y']
        move_left = total_dist
        
        # --- 全車が赤線（基準）より内側を走るロジック ---
        # 8号車を最大値(0)として、車番が小さいほどマイナス（内側）へ
        lane_offset = (car - 8) * 4 

        for pt in WAYPOINTS:
            target_x = pt['x']
            target_y = pt['y'] + lane_offset
            
            dist = math.sqrt((target_x - curr_x)**2 + (target_y - curr_y)**2)
            if move_left > 0 and dist > 0:
                move_dist = min(move_left, dist)
                curr_x += (target_x - curr_x) * (move_dist / dist)
                curr_y += (target_y - curr_y) * (move_dist / dist)
                move_left -= move_dist

        final_results.append({'car': car, 'x': int(curr_x), 'y': int(curr_y)})
    return final_results

def run_simulation(df):
    positions = calculate_rail_positions(df)
    # 赤線を引いて、その内側に全員がいることを確認
    img_path = visualizer.create_prediction_image(positions, waypoints=WAYPOINTS)
    if img_path:
        visualizer.send_to_discord(img_path, WEBHOOK_URL)
        print("全車が赤線の内側を通る設定で送信しました。")

if __name__ == "__main__":
    test_data = [{'車': i+1, 'ハンデ': i*10} for i in range(8)]
    run_simulation(pd.DataFrame(test_data))
