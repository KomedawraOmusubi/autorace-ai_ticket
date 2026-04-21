import os
import math
import pandas as pd
import visualizer

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# --- 1. 初期配置（スタート地点） ---
HANDE_CONFIG = {
    0:   {'x': 175, 'y': 400}, 10:  {'x': 120, 'y': 380},
    20:  {'x': 87,  'y': 354}, 30:  {'x': 65,  'y': 323},
    40:  {'x': 45,  'y': 285}, 50:  {'x': 35,  'y': 245},
    60:  {'x': 36,  'y': 202}, 70:  {'x': 48,  'y': 163},
    80:  {'x': 68,  'y': 125}, 90:  {'x': 93,  'y': 92},
    100: {'x': 125, 'y': 66}
}

# --- 2. 各ハンデごとの「仮想A地点」 ---
# ここで8号車（ピンク）が通る基準座標を指定します
CUSTOM_A_POINTS = {
    h: {'x': 175, 'y': 430} for h in HANDE_CONFIG.keys()
}

# --- 3. A地点通過後の共通ルート ---
POINT_B   = {'x': 420, 'y': 410}
POINT_B_1 = {'x': 500, 'y': 380}
POINT_B_2 = {'x': 570, 'y': 340}
POINT_B_3 = {'x': 590, 'y': 300}
POINT_C   = {'x': 600, 'y': 250}

WAYPOINTS_AFTER_A = [POINT_B, POINT_B_1, POINT_B_2, POINT_B_3, POINT_C]

def calculate_rail_positions(df):
    df = df.sort_values(['ハンデ', '車'])
    final_results = []

    for _, row in df.iterrows():
        car = int(row['車'])
        handy = int(row.get('ハンデ', 0))
        handy_key = min(max(0, (handy // 10) * 10), 100)
        
        start_pos = HANDE_CONFIG.get(handy_key, HANDE_CONFIG[0])
        curr_x, curr_y = start_pos['x'], start_pos['y']
        history = [(curr_x, curr_y)]

        # --- ここを修正：各車を内側に10ずつずらす ---
        # 8号車: (8-8)*10 = 0   (y: 430)
        # 7号車: (7-8)*10 = -10 (y: 420)
        # 1号車: (1-8)*10 = -70 (y: 360)
        lane_offset = (car - 8) * 10

        # [STEP 1] A地点（合流地点）
        target_a = CUSTOM_A_POINTS.get(handy_key, CUSTOM_A_POINTS[0])
        curr_x = target_a['x']
        curr_y = target_a['y'] + lane_offset
        history.append((curr_x, curr_y))

        # [STEP 2] 以降のウェイポイント
        for pt in WAYPOINTS_AFTER_A:
            target_x = pt['x']
            target_y = pt['y'] + lane_offset
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
    virtual_waypoints = [CUSTOM_A_POINTS[0]] + WAYPOINTS_AFTER_A
    img_path = visualizer.create_prediction_image(results, waypoints=virtual_waypoints)
    if img_path:
        visualizer.send_to_discord(img_path, WEBHOOK_URL)

if __name__ == "__main__":
    test_data = [{'車': i+1, 'ハンデ': i*10} for i in range(8)]
    run_simulation(pd.DataFrame(test_data))
