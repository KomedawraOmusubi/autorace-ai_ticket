import os
import math
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定と定数定義
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# ターゲット座標（イン角）
TARGET_X = 650
TARGET_Y = 265

# 各ハンデのスタート基準点
HANDE_CONFIG = {
    0:   {'x': 175, 'y': 400, 'spacing': 11}, 
    10:  {'x': 120, 'y': 380, 'spacing': 11},  
    20:  {'x': 87,  'y': 354, 'spacing': 11}, 
    30:  {'x': 65,  'y': 323, 'spacing': 11}, 
    40:  {'x': 45,  'y': 285, 'spacing': 11}, 
    50:  {'x': 35,  'y': 245, 'spacing': 11}, 
    60:  {'x': 36,  'y': 202, 'spacing': 11},  
    70:  {'x': 48,  'y': 163, 'spacing': 11}, 
    80:  {'x': 68,  'y': 125, 'spacing': 11}, 
    90:  {'x': 93,  'y': 92,  'spacing': 11}, 
    100: {'x': 125, 'y': 66,  'spacing': 11},  
}

X_LIMIT = (15, 780)  
Y_LIMIT = (20, 480) 

# ==========================================
# 2. 座標計算ロジック
# ==========================================
def calculate_natural_positions(df):
    df = df.sort_values(['ハンデ', '車'])
    final_results = []  # ここで初期化
    
    handy_groups = df.groupby('ハンデ')['車'].apply(list).to_dict()
    processed_count = {h: 0 for h in handy_groups.keys()}

    # 最も近い0m選手がターゲットに到達するまでの距離を基準に、
    # その100%（到達した瞬間）を全員の移動量とする
    base_dist = math.sqrt((TARGET_X - HANDE_CONFIG[0]['x'])**2 + (TARGET_Y - HANDE_CONFIG[0]['y'])**2)

    for _, row in df.iterrows():
        car = int(row['car'] if 'car' in row else row['車'])
        handy = int(row.get('ハンデ', 0))

        base_h = min(max(0, (handy // 10) * 10), 100)
        config = HANDE_CONFIG[base_h]
        
        # スタート時の配置角度
        dx = TARGET_X - config['x']
        dy = TARGET_Y - config['y']
        angle_to_target = math.atan2(dy, dx)
        line_angle = angle_to_target + math.pi / 2

        num_cars = len(handy_groups[handy])
        idx = processed_count[handy]
        processed_count[handy] += 1
        spacing = config.get('spacing', 11)
        offset = (idx - (num_cars - 1) / 2) * spacing
        
        # 初期座標
        sx = config['x'] + offset * math.cos(line_angle)
        sy = config['y'] + offset * math.sin(line_angle)
        
        # ターゲットまでの距離
        dist_to_target = math.sqrt((TARGET_X - sx)**2 + (TARGET_Y - sy)**2)
        
        # 全員「base_dist」分だけ進む（ただしターゲットは超えない）
        actual_move_dist = min(dist_to_target, base_dist)
        
        # 移動比率
        ratio = actual_move_dist / dist_to_target if dist_to_target > 0 else 1.0
        
        curr_x = sx + (TARGET_X - sx) * ratio
        curr_y = sy + (TARGET_Y - sy) * ratio
        
        final_results.append({
            'car': car,
            'x': int(max(X_LIMIT[0], min(X_LIMIT[1], curr_x))),
            'y': int(max(Y_LIMIT[0], min(Y_LIMIT[1], curr_y)))
        })
        
    return final_results

# ==========================================
# 3. 実行メイン処理
# ==========================================
def run_simulation_and_send(df):
    try:
        if not WEBHOOK_URL or "YOUR_WEBHOOK" in WEBHOOK_URL:
            print("エラー: Discord Webhook URLを設定してください。")
            return

        positions = calculate_natural_positions(df)
        img_path = visualizer.create_prediction_image(positions)
        
        if img_path:
            visualizer.send_to_discord(img_path, WEBHOOK_URL)
            print("0mがインに到達した瞬間の画像を送信しました。")
        else:
            print("画像生成失敗")
    except Exception as e:
        print(f"エラー: {e}")

# ==========================================
# 4. データ作成と実行
# ==========================================
if __name__ == "__main__":
    handicaps = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    test_data = []
    for i, h in enumerate(handicaps):
        test_data.append({
            '車': (i % 8) + 1,
            'ハンデ': h,
            '試走': 3.30
        })

    df_test = pd.DataFrame(test_data)
    run_simulation_and_send(df_test)
