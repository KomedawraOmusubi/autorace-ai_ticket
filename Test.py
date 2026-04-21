import os
import pandas as pd
import visualizer

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

HANDE_CONFIG = {
    0:   {'x': 175, 'y': 400}, 10:  {'x': 120, 'y': 380}, 20:  {'x': 87,  'y': 354},
    30:  {'x': 65,  'y': 323}, 40:  {'x': 45,  'y': 285}, 50:  {'x': 35,  'y': 245},
    60:  {'x': 36,  'y': 202}, 70:  {'x': 48,  'y': 163}, 80:  {'x': 68,  'y': 125},
    90:  {'x': 93,  'y': 92}, 100: {'x': 125, 'y': 66}
}

CUSTOM_A_POINTS = {
    0:   {'x': 175, 'y': 400}, 10:  {'x': 175, 'y': 390}, 20:  {'x': 175, 'y': 390},
    30:  {'x': 175, 'y': 380}, 40:  {'x': 175, 'y': 370}, 50:  {'x': 175, 'y': 370},
    60:  {'x': 175, 'y': 370}, 70:  {'x': 175, 'y': 370}, 80:  {'x': 175, 'y': 370},
    90:  {'x': 175, 'y': 370}, 100: {'x': 175, 'y': 370}
}

# 輪郭の点線データ（ご提示の最新版）
OUTER_LINE = [(175, 400),(465, 395), (500, 395), (525, 395),(565, 370), (590, 330), (635, 210)]
INNER_LINE = [(175, 350), (465, 355),(500, 350), (525, 340), (570, 330),(580, 310), (600, 210)]

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
        car, handy = int(row['車']), int(row.get('ハンデ', 0))
        handy_key = min(max(0, (handy // 10) * 10), 100)
        start_pos = HANDE_CONFIG.get(handy_key, HANDE_CONFIG[0])
        history = [(start_pos['x'], start_pos['y'])]
        
        # 同じハンデなら±4pxの幅で散らす
        base_handy_offset = -(handy / 10) * 5
        spread_offset = -4 + (car - 1) * (8 / 7)
        total_offset = base_handy_offset + spread_offset

        history.append((CUSTOM_A_POINTS[handy_key]['x'], CUSTOM_A_POINTS[handy_key]['y']))

        for wp in WAYPOINTS_AFTER_A:
            # 1号車専用の補正
            if car == 1:
                if wp['name'] == 'B': history.append((wp['pos']['x'], 395)); continue
                if wp['name'] == 'B_1': history.append((wp['pos']['x'], 350)); continue
            history.append((wp['pos']['x'], wp['pos']['y'] + total_offset))
        
        final_results.append({'car': car, 'path': history})
    return final_results

def run_simulation(df):
    results = calculate_rail_positions(df)
    img_path = visualizer.create_prediction_image(
        results, 
        outer_line=OUTER_LINE, 
        inner_line=INNER_LINE
    )
    if img_path:
        visualizer.send_to_discord(img_path, WEBHOOK_URL)

if __name__ == "__main__":
    # テスト走行：全車異なるハンデの場合
    test_data = [{'車': i+1, 'ハンデ': i*10} for i in range(8)]
    run_simulation(pd.DataFrame(test_data))
