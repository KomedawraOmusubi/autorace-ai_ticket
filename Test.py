import os
import math
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定と定数定義
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# ターゲット座標（イン角の点）
TARGET_X = 650
TARGET_Y = 265

# スタート位置
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
# 2. 芝生回避型・物理弧計算ロジック
# ==========================================
def calculate_natural_positions(df):
    df = df.sort_values(['ハンデ', '車'])
    final_results = []
    
    handy_groups = df.groupby('ハンデ')['車'].apply(list).to_dict()
    processed_count = {h: 0 for h in handy_groups.keys()}

    # 0mが到達するまでの移動距離を「1.0」とする
    # (0mのスタートxからターゲットxまでの距離を基準にする)
    base_move_x = TARGET_X - HANDE_CONFIG[0]['x']

    for _, row in df.iterrows():
        car = int(row['car'] if 'car' in row else row['車'])
        handy = int(row.get('ハンデ', 0))

        base_h = min(max(0, (handy // 10) * 10), 100)
        config = HANDE_CONFIG[base_h]
        
        # 初期整列の計算
        dx_to_target = TARGET_X - config['x']
        dy_to_target = TARGET_Y - config['y']
        angle = math.atan2(dy_to_target, dx_to_target)
        line_angle = angle + math.pi / 2

        num_cars = len(handy_groups[handy])
        idx = processed_count[handy]
        processed_count[handy] += 1
        spacing = config.get('spacing', 11)
        offset = (idx - (num_cars - 1) / 2) * spacing
        
        sx = config['x'] + offset * math.cos(line_angle)
        sy = config['y'] + offset * math.sin(line_angle)

        # --- 移動の計算 ---
        # 全員、0m車がTARGET_Xに届くのと同じ「X方向の移動量」だけ進むと仮定
        move_ratio = 1.0 # 0mがインに到達した時点
        
        # 現在のX座標 (直線的に進む)
        curr_x = sx + (base_move_x * move_ratio)
        # ターゲットを追い越さないように制限
        if curr_x > TARGET_X: curr_x = TARGET_X

        # --- 芝生を回避する弧の計算 ---
        # 進行度(sxからTARGET_Xまでの進捗)を再計算
        progress = (curr_x - sx) / (TARGET_X - sx) if (TARGET_X - sx) != 0 else 1.0
        
        # y座標の計算: 
        # 初期syからターゲットTARGET_Yへ、二次関数的に近づく（弧を描く）
        # sy > TARGET_Y なら減少し、sy < TARGET_Y なら増加する。
        # いずれも「初期位置 y」を超えないように制限。
        curr_y = sy + (TARGET_Y - sy) * (progress ** 2)

        # --- 最終ガードレール: 芝生（内沼）の境界判定 ---
        # 簡易的な楕円形コースとして、特定のX範囲でyが内側に入りすぎないよう補正
        # 画像中央(x=400付近)が最も芝生が張り出している
        if 180 < curr_x < 620:
            # 芝生の縁のy座標（概算）
            inner_boundary_min = 130 
            inner_boundary_max = 370
            if sy > 250: # 下半分のコース
                curr_y = max(curr_y, inner_boundary_max)
            else: # 上半分のコース
                curr_y = min(curr_y, inner_boundary_min)

        final_results.append({
            'car': car,
            'x': int(max(X_LIMIT[0], min(X_LIMIT[1], curr_x))),
            'y': int(max(Y_LIMIT[0], min(Y_LIMIT[1], curr_y)))
        })
        
    return final_results

# ==========================================
# 3. 実行
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
            print("芝生回避ロジックを適用し、0m到達時点の画像を送信しました。")
        else:
            print("画像生成失敗")
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    handicaps = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    test_data = [{'車': (i % 8) + 1, 'ハンデ': h, '試走': 3.30} for i, h in enumerate(handicaps)]
    run_simulation_and_send(pd.DataFrame(test_data))
