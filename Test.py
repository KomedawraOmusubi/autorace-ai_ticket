import os
import math
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定と定数定義
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# 経由地点
POINT_A = {'x': 175, 'y': 400}  # 0m付近
POINT_B = {'x': 420, 'y': 400}  # ゴール線付近
POINT_C = {'x': 650, 'y': 265}  # 最終目標（イン角）

# 芝生境界の最小y（下コース: 390, 上コース: 140 と仮定）
SHIBAFU_LIMIT_Y = 390 

HANDE_CONFIG = {
    0:   {'x': 175, 'y': 400}, 10:  {'x': 120, 'y': 380}, 20:  {'x': 87,  'y': 354},
    30:  {'x': 65,  'y': 323}, 40:  {'x': 45,  'y': 285}, 50:  {'x': 35,  'y': 245},
    60:  {'x': 36,  'y': 202}, 70:  {'x': 48,  'y': 163}, 80:  {'x': 68,  'y': 125},
    90:  {'x': 93,  'y': 92},  100: {'x': 125, 'y': 66}
}

# ==========================================
# 2. B-C間ガード付き移動ロジック
# ==========================================
def calculate_secure_abc_path(df):
    df = df.sort_values(['ハンデ', '車'])
    final_results = []
    
    # 0m選手がA-B-Cを完走する距離
    dist_ab = math.sqrt((POINT_B['x'] - POINT_A['x'])**2 + (POINT_B['y'] - POINT_A['y'])**2)
    dist_bc = math.sqrt((POINT_C['x'] - POINT_B['x'])**2 + (POINT_C['y'] - POINT_B['y'])**2)
    total_allowed_dist = dist_ab + dist_bc

    for _, row in df.iterrows():
        car = int(row['車'])
        handy = int(row.get('ハンデ', 0))
        config = HANDE_CONFIG[min(max(0, (handy // 10) * 10), 100)]
        
        curr_x, curr_y = config['x'], config['y']
        move_left = total_allowed_dist

        # ステップ1: A地点へ
        d = math.sqrt((POINT_A['x'] - curr_x)**2 + (POINT_A['y'] - curr_y)**2)
        if move_left > 0 and d > 0:
            m = min(move_left, d)
            curr_x += (POINT_A['x'] - curr_x) * (m/d)
            curr_y += (POINT_A['y'] - curr_y) * (m/d)
            move_left -= m

        # ステップ2: B地点へ
        d = math.sqrt((POINT_B['x'] - curr_x)**2 + (POINT_B['y'] - curr_y)**2)
        if move_left > 0 and d > 0:
            m = min(move_left, d)
            curr_x += (POINT_B['x'] - curr_x) * (m/d)
            curr_y += (POINT_B['y'] - curr_y) * (m/d)
            move_left -= m

        # ステップ3: C地点へ (ここで芝生侵入をガード)
        d = math.sqrt((POINT_C['x'] - curr_x)**2 + (POINT_C['y'] - curr_y)**2)
        if move_left > 0 and d > 0:
            m = min(move_left, d)
            progress = m / d
            # 基本の移動先
            next_x = curr_x + (POINT_C['x'] - curr_x) * progress
            next_y = curr_y + (POINT_C['y'] - curr_y) * progress
            
            # C地点手前での芝生侵入防止:
            # xがターゲット(650)に近づくほどyを絞るが、道中ではSHIBAFU_LIMITより外を維持
            if next_x < 600:
                if curr_y > 265: # 下から来る車
                    next_y = max(next_y, SHIBAFU_LIMIT_Y)
                else: # 上から来る車
                    next_y = min(next_y, 140)
            
            curr_x, curr_y = next_x, next_y

        final_results.append({'car': car, 'x': int(curr_x), 'y': int(curr_y)})
        
    return final_results

def run_simulation_and_send(df):
    try:
        positions = calculate_secure_abc_path(df)
        img_path = visualizer.create_prediction_image(positions)
        if img_path:
            visualizer.send_to_discord(img_path, WEBHOOK_URL)
            print("C地点手前の芝生ガードを強化して送信しました。")
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    handicaps = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    test_data = [{'車': (i % 8) + 1, 'ハンデ': h} for i, h in enumerate(handicaps)]
    run_simulation_and_send(pd.DataFrame(test_data))
