import os
import math
import pandas as pd
import visualizer

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# 基準座標
POINT_A,POINT_B = {'x': 175, 'y': 420}, {'x': 420, 'y': 410}
POINT_B_1, POINT_B_2 = {'x': 500, 'y': 390}, {'x': 570, 'y': 340}
POINT_B_3, POINT_C = {'x': 590, 'y': 300}, {'x': 600, 'y': 250}
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
    
    # 0m車の走行距離を基準にする
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
        
        # 走行軌跡を記録するリスト（スタート地点を追加）
        history = [(curr_x, curr_y)]
        
        # 8号車を基準に全員イン寄り（全車赤線より内側）
        lane_offset = (car - 8) * 4 

        for pt in WAYPOINTS:
            tx, ty = pt['x'], pt['y'] + lane_offset
            d = math.sqrt((tx - curr_x)**2 + (ty - curr_y)**2)
            
            if move_left > 0 and d > 0:
                m = min(move_left, d)
                curr_x += (tx - curr_x) * (m/d)
                curr_y += (ty - curr_y) * (m/d)
                move_left -= m
                # 通過点または最終点を記録
                history.append((curr_x, curr_y))

        final_results.append({
            'car': car, 
            'last_pos': (curr_x, curr_y), 
            'path': history
        })
    return final_results

def run_simulation(df):
    results = calculate_rail_positions(df)
    img_path = visualizer.create_prediction_image(results, waypoints=WAYPOINTS)
    if img_path:
        visualizer.send_to_discord(img_path, WEBHOOK_URL)
        print("各車の専用カラーラインを描画しました。")

if __name__ == "__main__":
    test_data = [{'車': i+1, 'ハンデ': i*10} for i in range(8)]
    run_simulation(pd.DataFrame(test_data))
