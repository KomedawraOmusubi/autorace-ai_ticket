import os
import math
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定と座標レールの定義
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# 走行レール（赤線で結ぶターゲット）
POINT_A   = {'x': 175, 'y': 420}
POINT_B   = {'x': 420, 'y': 410}
POINT_B_2 = {'x': 580, 'y': 320}
POINT_B_3 = {'x': 605, 'y': 280}
POINT_C   = {'x': 598, 'y': 242}

WAYPOINTS = [POINT_A, POINT_B, POINT_B_2, POINT_B_3, POINT_C]

HANDE_CONFIG = {
    0:   {'x': 175, 'y': 400}, 10:  {'x': 120, 'y': 380}, 20:  {'x': 87,  'y': 354},
    30:  {'x': 65,  'y': 323}, 40:  {'x': 45,  'y': 285}, 50:  {'x': 35,  'y': 245},
    60:  {'x': 36,  'y': 202}, 70:  {'x': 48,  'y': 163}, 80:  {'x': 68,  'y': 125},
    90:  {'x': 93,  'y': 92},  100: {'x': 125, 'y': 66}
}

# ==========================================
# 2. レール走行シミュレーション
# ==========================================
def calculate_rail_positions(df):
    df = df.sort_values(['ハンデ', '車'])
    final_results = []
    
    # 距離の計算
    dists = []
    for i in range(len(WAYPOINTS) - 1):
        p1, p2 = WAYPOINTS[i], WAYPOINTS[i+1]
        dists.append(math.sqrt((p2['x'] - p1['x'])**2 + (p2['y'] - p1['y'])**2))
    
    total_allowed_dist = sum(dists)

    for _, row in df.iterrows():
        car = int(row['車'])
        handy = int(row.get('ハンデ', 0))
        config = HANDE_CONFIG[min(max(0, (handy // 10) * 10), 100)]
        
        curr_x, curr_y = config['x'], config['y']
        move_left = total_allowed_dist

        # スタート地点からA地点へ（ここも赤線に含めるならWAYPOINTSに入れる）
        d_start_to_a = math.sqrt((POINT_A['x'] - curr_x)**2 + (POINT_A['y'] - curr_y)**2)
        if move_left > 0 and d_start_to_a > 0:
            m = min(move_left, d_start_to_a)
            curr_x += (POINT_A['x'] - curr_x) * (m/d_start_to_a)
            curr_y += (POINT_A['y'] - curr_y) * (m/d_start_to_a)
            move_left -= m

        # A -> B -> B2 -> B3 -> C を順番に辿る
        for i in range(len(WAYPOINTS) - 1):
            if move_left <= 0: break
            target = WAYPOINTS[i+1]
            d = math.sqrt((target['x'] - curr_x)**2 + (target['y'] - curr_y)**2)
            if d > 0:
                m = min(move_left, d)
                curr_x += (target['x'] - curr_x) * (m/d)
                curr_y += (target['y'] - curr_y) * (m/d)
                move_left -= m

        final_results.append({'car': car, 'x': int(curr_x), 'y': int(curr_y)})
        
    return final_results

# ==========================================
# 3. 実行（描画オプション付き）
# ==========================================
def run_simulation(df):
    try:
        positions = calculate_rail_positions(df)
        
        # 描画用データの作成
        # visualizer側で「線の描画」をサポートさせるための引数例
        # draw_lines=[(p1, p2), (p2, p3)...] のような形式を想定
        lines = []
        for i in range(len(WAYPOINTS) - 1):
            lines.append((WAYPOINTS[i], WAYPOINTS[i+1]))

        # 引数に path_lines を追加（visualizer側の実装に合わせて調整してください）
        img_path = visualizer.create_prediction_image(positions, draw_lines=lines, line_color="red")
        
        if img_path:
            visualizer.send_to_discord(img_path, WEBHOOK_URL)
            print("送信完了：ポイント間を赤線で結び、走行ルートを可視化しました。")
    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    test_data = [{'車': (i % 8) + 1, 'ハンデ': i*10} for i in range(11)]
    run_simulation(pd.DataFrame(test_data))
