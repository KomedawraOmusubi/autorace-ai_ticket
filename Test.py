import os
import math
import pandas as pd
import visualizer

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# 基準座標
POINT_A   = {'x': 175, 'y': 430} # ここが「8号車」の通過目標になる
POINT_B   = {'x': 420, 'y': 410}
POINT_B_1 = {'x': 500, 'y': 380}
POINT_B_2 = {'x': 570, 'y': 340}
POINT_B_3 = {'x': 590, 'y': 300}
POINT_C   = {'x': 600, 'y': 250}

WAYPOINTS = [POINT_A, POINT_B, POINT_B_1, POINT_B_2, POINT_B_3, POINT_C]

HANDE_CONFIG = {
    0: {'x': 175, 'y': 400}, 10: {'x': 120, 'y': 380}, 20: {'x': 87, 'y': 354},
    30: {'x': 65, 'y': 323}, 40: {'x': 45, 'y': 285}, 50: {'x': 35, 'y': 245},
    60: {'x': 36, 'y': 202}, 70: {'x': 48, 'y': 163}, 80: {'x': 68, 'y': 125},
    90: {'x': 93, 'y': 92}, 100: {'x': 125, 'y': 66}
}

def calculate_rail_positions(df):
    df = df.sort_values(['ハンデ', '車'])
    final_results = []
    
    # 0m車の走行距離（スタート175,400からA,B,Cを回る距離）を基準にする
    total_dist = 0
    ref_x, ref_y = HANDE_CONFIG[0]['x'], HANDE_CONFIG[0]['y']
    for pt in WAYPOINTS:
        total_dist += math.sqrt((pt['x'] - ref_x)**2 + (pt['y'] - ref_y)**2)
        ref_x, ref_y = pt['x'], pt['y']

    for _, row in df.iterrows():
        car = int(row['車'])
        handy = int(row.get('ハンデ', 0))
        config = HANDE_CONFIG[min(max(0, (handy // 10) * 10), 100)]
        
        curr_x, curr_y = config['x'], config['y']
        move_left = total_dist
        history = [(curr_x, curr_y)]

        # --- 重要：(car - 8) により、8号車が基準(offset=0)になる ---
        # 8号車: offset = 0   -> POINT_A(175, 430)を直撃
        # 1号車: offset = -28 -> POINT_A(175, 402)を通過（スタートより内側）
        lane_offset = (car - 8) * 4 

        for pt in WAYPOINTS:
            target_x = pt['x']
            target_y = pt['y'] + lane_offset

            d = math.sqrt((target_x - curr_x)**2 + (target_y - curr_y)**2)
            
            if move_left > 0 and d > 0:
                m = min(move_left, d)
                curr_x += (target_x - curr_x) * (m/d)
                curr_y += (target_y - curr_y) * (m/d)
                move_left -= m
                history.append((curr_x, curr_y))

        final_results.append({'car': car, 'last_pos': (curr_x, curr_y), 'path': history})
    return final_results

def run_simulation(df):
    results = calculate_rail_positions(df)
    img_path = visualizer.create_prediction_image(results, waypoints=WAYPOINTS)
    if img_path:
        visualizer.send_to_discord(img_path, WEBHOOK_URL)

if __name__ == "__main__":
    test_data = [{'車': i+1, 'ハンデ': i*10} for i in range(8)]
    run_simulation(pd.DataFrame(test_data))
