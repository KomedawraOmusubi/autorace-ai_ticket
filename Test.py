import os
import math
import pandas as pd
import visualizer

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# 走行レール定義
POINT_A   = {'x': 175, 'y': 420}
POINT_B   = {'x': 420, 'y': 410}
POINT_B_2 = {'x': 570, 'y': 320}
POINT_B_3 = {'x': 580, 'y': 280}
POINT_C   = {'x': 598, 'y': 242}

# 赤線を引く順番
WAYPOINTS = [POINT_A, POINT_B, POINT_B_2, POINT_B_3, POINT_C]

HANDE_CONFIG = {
    0:   {'x': 175, 'y': 400}, 10:  {'x': 120, 'y': 380}, 20:  {'x': 87,  'y': 354},
    30:  {'x': 65,  'y': 323}, 40:  {'x': 45,  'y': 285}, 50:  {'x': 35,  'y': 245},
    60:  {'x': 36,  'y': 202}, 70:  {'x': 48,  'y': 163}, 80:  {'x': 68,  'y': 125},
    90:  {'x': 93,  'y': 92},  100: {'x': 125, 'y': 66}
}

def calculate_rail_positions(df):
    df = df.sort_values(['ハンデ', '車'])
    final_results = []
    
    # 距離計算
    total_dist = 0
    for i in range(len(WAYPOINTS)-1):
        p1, p2 = WAYPOINTS[i], WAYPOINTS[i+1]
        total_dist += math.sqrt((p2['x']-p1['x'])**2 + (p2['y']-p1['y'])**2)

    for _, row in df.iterrows():
        car = int(row['車'])
        handy = int(row.get('ハンデ', 0))
        config = HANDE_CONFIG[min(max(0, (handy // 10) * 10), 100)]
        
        curr_x, curr_y = config['x'], config['y']
        move_left = total_dist

        # スタート -> A -> B -> B2 -> B3 -> C
        full_path = [POINT_A] + WAYPOINTS[1:]
        for pt in full_path:
            d = math.sqrt((pt['x'] - curr_x)**2 + (pt['y'] - curr_y)**2)
            if move_left > 0 and d > 0:
                m = min(move_left, d)
                curr_x += (pt['x'] - curr_x) * (m/d)
                curr_y += (pt['y'] - curr_y) * (m/d)
                move_left -= m

        final_results.append({'car': car, 'x': int(curr_x), 'y': int(curr_y)})
    return final_results

def run_simulation(df):
    positions = calculate_rail_positions(df)
    # WAYPOINTSを渡して赤線を引かせる
    img_path = visualizer.create_prediction_image(positions, waypoints=WAYPOINTS)
    if img_path:
        visualizer.send_to_discord(img_path, WEBHOOK_URL)

if __name__ == "__main__":
    test_data = [{'車': (i % 8) + 1, 'ハンデ': i*10} for i in range(11)]
    run_simulation(pd.DataFrame(test_data))
