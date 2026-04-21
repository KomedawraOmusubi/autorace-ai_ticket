import os
import math
import pandas as pd
import visualizer

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# --- 1. 初期配置（スタート地点） ---
HANDE_CONFIG = {
    0:   {'x': 175, 'y': 400},
    10:  {'x': 120, 'y': 380},
    20:  {'x': 87,  'y': 354},
    30:  {'x': 65,  'y': 323},
    40:  {'x': 45,  'y': 285},
    50:  {'x': 35,  'y': 245},
    60:  {'x': 36,  'y': 202},
    70:  {'x': 48,  'y': 163},
    80:  {'x': 68,  'y': 125},
    90:  {'x': 93,  'y': 92},
    100: {'x': 125, 'y': 66}
}

# --- 2. 各ハンデごとの「仮想A地点」 ---
CUSTOM_A_POINTS = {
    0:   {'x': 175, 'y': 400}, 
    10:  {'x': 175, 'y': 390},
    20:  {'x': 175, 'y': 390},
    30:  {'x': 175, 'y': 380},
    40:  {'x': 175, 'y': 370},
    50:  {'x': 175, 'y': 370},
    60:  {'x': 175, 'y': 370},
    70:  {'x': 175, 'y': 370},
    80:  {'x': 175, 'y': 370},
    90:  {'x': 175, 'y': 370},
    100: {'x': 175, 'y': 370}
}

# --- 3. A地点通過後のウェイポイント ---
POINT_B   = {'x': 455, 'y': 410}
POINT_B_1 = {'x': 550, 'y': 370} # 基本のB_1（8号車基準）
POINT_B_2 = {'x': 570, 'y': 350}
POINT_B_3 = {'x': 590, 'y': 310}
POINT_C   = {'x': 600, 'y': 250}

WAYPOINTS_AFTER_A = [
    {'name': 'B',   'pos': POINT_B},
    {'name': 'B_1', 'pos': POINT_B_1},
    {'name': 'B_2', 'pos': POINT_B_2},
    {'name': 'B_3', 'pos': POINT_B_3},
    {'name': 'C',   'pos': POINT_C}
]

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

        # 8号車を基準、他は5pxずつ内側
        lane_offset = (car - 8) * 5

        # [STEP 1] A地点（合流）
        target_a = CUSTOM_A_POINTS.get(handy_key, CUSTOM_A_POINTS[0])
        history.append((target_a['x'], target_a['y']))

        # [STEP 2] B以降のウェイポイント
        for wp in WAYPOINTS_AFTER_A:
            # --- 0ハンデ車専用の直線ロジック ---
            if handy == 0:
                if wp['name'] == 'B':
                    continue # B地点は通らず真っ直ぐB_1へ
                if wp['name'] == 'B_1':
                    # B_1地点のyを400に固定して水平にする
                    history.append((wp['pos']['x'], 400))
                    continue

            # 通常の走行（8号車の内側5pxルール）
            target_x = wp['pos']['x']
            target_y = wp['pos']['y'] + lane_offset
            history.append((target_x, target_y))

        final_results.append({
            'car': car, 
            'last_pos': history[-1], 
            'path': history
        })
    return final_results

def run_simulation(df):
    results = calculate_rail_positions(df)
    virtual_pts = [CUSTOM_A_POINTS[0]] + [wp['pos'] for wp in WAYPOINTS_AFTER_A]
    img_path = visualizer.create_prediction_image(results, virtual_pts)
    if img_path:
        visualizer.send_to_discord(img_path, WEBHOOK_URL)

if __name__ == "__main__":
    test_data = [{'車': i+1, 'ハンデ': i*10} for i in range(8)]
    run_simulation(pd.DataFrame(test_data))
