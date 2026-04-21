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

# --- 3. コース輪郭（点線用）の定義 ---
# A〜C地点の「幅」の端点を定義
OUTER_LINE = [
    (175, 400), (455, 395), (550, 330), (570, 290), (590, 250), (600, 210)
]
INNER_LINE = [
    (175, 360), (455, 355), (550, 290), (570, 330), (590, 290), (625, 210)
]

# 通過ウェイポイント（基準点）
WAYPOINTS_AFTER_A = [
    {'name': 'B',   'pos': {'x': 455, 'y': 395}},
    {'name': 'B_1', 'pos': {'x': 550, 'y': 360}},
    {'name': 'B_2', 'pos': {'x': 570, 'y': 350}},
    {'name': 'B_3', 'pos': {'x': 590, 'y': 310}},
    {'name': 'C',   'pos': {'x': 600, 'y': 250}}
]

def calculate_rail_positions(df):
    df = df.sort_values(['ハンデ', '車'])
    final_results = []

    for _, row in df.iterrows():
        car = int(row['車'])
        handy = int(row.get('ハンデ', 0))
        handy_key = min(max(0, (handy // 10) * 10), 100)
        
        start_pos = HANDE_CONFIG.get(handy_key, HANDE_CONFIG[0])
        history = [(start_pos['x'], start_pos['y'])]

        # ハンデ基準オフセット + 車番微調整 (±4px)
        base_handy_offset = -(handy / 10) * 5
        spread_offset = -4 + (car - 1) * (8 / 7)
        total_offset = base_handy_offset + spread_offset

        # [STEP 1] A地点
        target_a = CUSTOM_A_POINTS.get(handy_key, CUSTOM_A_POINTS[0])
        history.append((target_a['x'], target_a['y']))

        # [STEP 2] B以降
        for wp in WAYPOINTS_AFTER_A:
            # 1号車の特別指定
            if car == 1:
                if wp['name'] == 'B':
                    history.append((wp['pos']['x'], 395))
                    continue
                if wp['name'] == 'B_1':
                    history.append((wp['pos']['x'], 350))
                    continue

            target_x = wp['pos']['x']
            target_y = wp['pos']['y'] + total_offset
            history.append((target_x, target_y))

        final_results.append({'car': car, 'path': history})
    return final_results

def run_simulation(df):
    results = calculate_rail_positions(df)
    
    # 輪郭点線の描画指示（visualizer側の仕様に合わせた疑似呼び出し）
    # 第3引数以降で点線のリストを渡す想定
    img_path = visualizer.create_prediction_image(
        results, 
        outer_line=OUTER_LINE, 
        inner_line=INNER_LINE,
        draw_dashed=True
    )
    
    if img_path:
        visualizer.send_to_discord(img_path, WEBHOOK_URL)

if __name__ == "__main__":
    test_data = [{'車': i+1, 'ハンデ': i*10} for i in range(8)]
    run_simulation(pd.DataFrame(test_data))
