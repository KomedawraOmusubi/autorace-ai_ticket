import os
import math
import pandas as pd
import visualizer

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# 基準座標
POINT_A   = {'x': 175, 'y': 430} # 8号車がここを目指す（y=400より内側）
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

    for _, row in df.iterrows():
        car = int(row['車'])
        handy = int(row.get('ハンデ', 0))
        # ハンデに基づいてスタート地点を取得
        config = HANDE_CONFIG[min(max(0, (handy // 10) * 10), 100)]
        
        curr_x, curr_y = config['x'], config['y']
        history = [(curr_x, curr_y)]

        # 車番ごとのオフセット（8号車を赤線/基準点にする）
        lane_offset = (car - 8) * 4 

        # 全員が全てのWAYPOINTSを通過するまでループ
        for pt in WAYPOINTS:
            target_x = pt['x']
            target_y = pt['y'] + lane_offset
            
            # ここでは距離制限を設けず、ターゲットに直接移動させる
            # これにより、ハンデがあっても必ずPOINT_Cまで到達します
            curr_x, curr_y = target_x, target_y
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

if __name__ == "__main__":
    # 0m〜70mハンデのテストデータ
    test_data = [{'車': i+1, 'ハンデ': i*10} for i in range(8)]
    run_simulation(pd.DataFrame(test_data))
