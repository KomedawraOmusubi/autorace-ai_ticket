import os
import math
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定と定数定義
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# ターゲット座標（イン角の白線端）
TARGET_X = 650
TARGET_Y = 265

# スタート位置の基本設定
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
# 2. 物理的な最短「イン切り」軌道ロジック
# ==========================================
def calculate_natural_positions(df):
    df = df.sort_values(['ハンデ', '車'])
    final_results = []
    
    handy_groups = df.groupby('ハンデ')['車'].apply(list).to_dict()
    processed_count = {h: 0 for h in handy_groups.keys()}

    # 0m選手がターゲットに到達するまでの「弧の長さ」を基準にする
    # yの差分とxの差分から、大まかなカーブ距離を算出
    base_dx = abs(TARGET_X - HANDE_CONFIG[0]['x'])
    base_dy = abs(TARGET_Y - HANDE_CONFIG[0]['y'])
    # 弧の長さの近似 (直線より長く、外周より短い)
    base_move_dist = math.sqrt(base_dx**2 + base_dy**2) * 1.1

    for _, row in df.iterrows():
        car = int(row['car'] if 'car' in row else row['車'])
        handy = int(row.get('ハンデ', 0))

        base_h = min(max(0, (handy // 10) * 10), 100)
        config = HANDE_CONFIG[base_h]
        
        # 1. 初期配置の計算 (複数車番の整列)
        dx_init = TARGET_X - config['x']
        dy_init = TARGET_Y - config['y']
        angle_to_target = math.atan2(dy_init, dx_init)
        line_angle = angle_to_target + math.pi / 2

        num_cars = len(handy_groups[handy])
        idx = processed_count[handy]
        processed_count[handy] += 1
        spacing = config.get('spacing', 11)
        offset = (idx - (num_cars - 1) / 2) * spacing
        
        sx = config['x'] + offset * math.cos(line_angle)
        sy = config['y'] + offset * math.sin(line_angle)

        # 2. 移動シミュレーション
        # 試走タイムが同じなので、全員一律で base_move_dist 分だけ進む
        # ただし、ターゲットまでの実距離がそれより短い場合はターゲットで止まる
        total_dist_to_target = math.sqrt((TARGET_X - sx)**2 + (TARGET_Y - sy)**2) * 1.1
        move_ratio = min(1.0, base_move_dist / total_dist_to_target)

        # 3. 軌道計算 (yが大きくならないように弧を描く)
        # 進行度(move_ratio)に応じて、xは増加し、yはターゲットに向かって「収束」する
        # 三次関数（Ease-In-Out風）を使って、最初は緩やかに、後半に鋭くインへ切り込む
        
        if handy <= 50:
            # 下半分(0-50m): yは減少していく
            curr_x = sx + (TARGET_X - sx) * move_ratio
            # yの減少を加速させることで「インに絞る」動きを再現
            curr_y = sy + (TARGET_Y - sy) * (move_ratio ** 1.5)
        else:
            # 上半分(60-100m): yは増加していく（ターゲットが下にあるため）
            # ただし「外に膨らまない」という原則を守るため、syを上限とする
            curr_x = sx + (TARGET_X - sx) * move_ratio
            curr_y = sy + (TARGET_Y - sy) * (move_ratio ** 1.5)

        # 最終チェック: 芝生に入らないよう、yの範囲をスタート時とターゲットの間でロック
        # 下半分なら sy >= curr_y >= TARGET_Y, 上半分なら sy <= curr_y <= TARGET_Y
        if sy > TARGET_Y:
            curr_y = max(TARGET_Y, min(sy, curr_y))
        else:
            curr_y = min(TARGET_Y, max(sy, curr_y))

        final_results.append({
            'car': car,
            'x': int(max(X_LIMIT[0], min(X_LIMIT[1], curr_x))),
            'y': int(max(Y_LIMIT[0], min(Y_LIMIT[1], curr_y)))
        })
        
    return final_results

# ==========================================
# 3. 実行メイン
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
            print("y座標の増加を抑制し、インへ絞り込む弧の軌道で送信しました。")
        else:
            print("画像生成失敗")
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    handicaps = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    test_data = [{'車': (i % 8) + 1, 'ハンデ': h, '試走': 3.30} for i, h in enumerate(handicaps)]
    run_simulation_and_send(pd.DataFrame(test_data))
