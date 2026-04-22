import os
import pandas as pd
import visualizer 

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# --- 設定データ ---

# スタート座標：50m以降は左端から並ぶようにX座標を小さく調整
HANDE_CONFIG = {
    0:   {'x': 175, 'y': 400}, 10:  {'x': 120, 'y': 380}, 20:  {'x': 87,  'y': 354},
    30:  {'x': 65,  'y': 323}, 40:  {'x': 45,  'y': 285},
    # 50m以降は左端(コースの内側)へ
    50:  {'x': 20,  'y': 245}, 60:  {'x': 20,  'y': 202}, 70:  {'x': 20,  'y': 163},
    80:  {'x': 20,  'y': 125}, 90:  {'x': 20,  'y': 92},  100: {'x': 20,  'y': 66},
    110: {'x': 20,  'y': 45}
}

# 第1合流点(点A)：左端から中央付近へ合流する動き
CUSTOM_A_POINTS = {
    0:   {'x': 175, 'y': 400}, 10:  {'x': 175, 'y': 390}, 20:  {'x': 175, 'y': 390},
    30:  {'x': 175, 'y': 380}, 40:  {'x': 175, 'y': 370},
    50:  {'x': 175, 'y': 370}, 60:  {'x': 175, 'y': 370}, 70:  {'x': 175, 'y': 370},
    80:  {'x': 175, 'y': 370}, 90:  {'x': 175, 'y': 370}, 100: {'x': 175, 'y': 370},
    110: {'x': 175, 'y': 370}
}

OUTER_LINE = [(175, 400), (465, 395), (500, 395), (525, 395), (565, 370), (595, 335), (620, 220)]
INNER_LINE = [(175, 350), (465, 355), (500, 350), (525, 340), (570, 310), (580, 300), (605 , 210)]

WAYPOINTS_AFTER_A = [
    {'name': 'B',   'pos': {'x': 455, 'y': 395}},
    {'name': 'B_1', 'pos': {'x': 550, 'y': 360}},
    {'name': 'B_2', 'pos': {'x': 570, 'y': 350}},
    {'name': 'B_3', 'pos': {'x': 590, 'y': 310}},
    {'name': 'C',   'pos': {'x': 600, 'y': 250}}
]

def calculate_rail_positions(df):
    df = df.sort_values(['車'])
    final_results = []
    for _, row in df.iterrows():
        car = int(row['車'])
        handy = int(row.get('ハンデ', 0))
        handy_key = min(max(0, (handy // 10) * 10), 110)
        
        start_pos = HANDE_CONFIG.get(handy_key, HANDE_CONFIG[0])
        history = [(start_pos['x'], start_pos['y'])]
        history.append((CUSTOM_A_POINTS[handy_key]['x'], CUSTOM_A_POINTS[handy_key]['y']))

        # ライン間の微調整
        base_handy_offset = -(handy / 10) * 3.5 
        spread_offset = -3 + (car * 1.2)
        total_offset = base_handy_offset + spread_offset

        for wp in WAYPOINTS_AFTER_A:
            # 1号車イン差し
            if car == 1:
                if wp['name'] == 'B': history.append((wp['pos']['x'], 380)); continue
                if wp['name'] == 'B_1': history.append((wp['pos']['x'], 340)); continue
            
            target_y = wp['pos']['y'] + total_offset
            history.append((wp['pos']['x'], target_y))
        
        final_results.append({'car': car, 'handy': handy, 'path': history})
    return final_results

def run_simulation(df):
    results = calculate_rail_positions(df)
    img_path = visualizer.create_prediction_image(results, OUTER_LINE, INNER_LINE)
    if img_path:
        visualizer.send_to_discord(img_path, WEBHOOK_URL)

if __name__ == "__main__":
    # 全ハンデ帯でのテスト
    test_data = [
        {'車': 1, 'ハンデ': 0}, {'車': 2, 'ハンデ': 10}, {'車': 3, 'ハンデ': 30},
        {'車': 4, 'ハンデ': 50}, {'車': 5, 'ハンデ': 70}, {'車': 6, 'ハンデ': 80},
        {'車': 7, 'ハンデ': 100}, {'車': 8, 'ハンデ': 110}
    ]
    run_simulation(pd.DataFrame(test_data))
