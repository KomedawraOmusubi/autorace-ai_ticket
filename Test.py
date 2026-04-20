import os
import math
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定と定数定義
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# 経由地点の設定

# a地点 (0mハンデ基準点)
POINT_A = {'x': 175, 'y': 400}

# c地点 (最終目標：イン角)
# --- 修正箇所：X座標を大幅に減少（500 -> 350付近） ---
POINT_C_X = 350 
POINT_C_Y = 265 # Cのyは維持

# 芝生の境界線 (これより内側は禁止)
INNER_BOUNDARY_TOP = 140
INNER_BOUNDARY_BOTTOM = 390

# 各ハンデのスタート位置設定
HANDE_CONFIG = {
    0:   {'x': 175, 'y': 400, 'spacing': 9}, 
    10:  {'x': 120, 'y': 380, 'spacing': 10},  
    20:  {'x': 87,  'y': 354, 'spacing': 10}, 
    30:  {'x': 65,  'y': 323, 'spacing': 10}, 
    40:  {'x': 45,  'y': 285, 'spacing': 10}, 
    50:  {'x': 35,  'y': 245, 'spacing': 10}, 
    60:  {'x': 36,  'y': 202, 'spacing': 10},  
    70:  {'x': 48,  'y': 163, 'spacing': 11}, 
    80:  {'x': 68,  'y': 125, 'spacing': 11}, 
    90:  {'x': 93,  'y': 92,  'spacing': 10}, 
    100: {'x': 125, 'y': 66,  'spacing': 10},  
}

X_LIMIT = (15, 750)  
Y_LIMIT = (20, 480) 

# ==========================================
# 2. 座標計算ロジック（C地点修正、芝生回避）
# ==========================================
def calculate_secure_abc_path(df):
    df = df.sort_values(['ハンデ', '車'])
    final_results = []
    
    # 全員の基準移動量を「0m選手がTARGET_Xに届くまでのX距離」に設定
    # ターゲットが近くなったため、この距離も短くなります
    base_dx = POINT_C_X - POINT_A['x']

    handy_groups = df.groupby('ハンデ')['車'].apply(list).to_dict()
    processed_count = {h: 0 for h in handy_groups.keys()}

    for _, row in df.iterrows():
        car = int(row['車'])
        handy = int(row.get('ハンデ', 0))
        
        base_h = min(max(0, (handy // 10) * 10), 100)
        config = HANDE_CONFIG[base_h]
        
        # スタート座標 (sx, sy)
        dx_to_c = POINT_C_X - config['x']
        dy_to_c = POINT_C_Y - config['y']
        angle = math.atan2(dy_to_c, dx_to_c)
        line_angle = angle + math.pi / 2

        num_cars = len(handy_groups[handy])
        idx = processed_count[handy]
        processed_count[handy] += 1
        spacing = config.get('spacing', 11)
        offset = (idx - (num_cars - 1) / 2) * spacing
        
        sx = config['x'] + offset * math.cos(line_angle)
        sy = config['y'] + offset * math.sin(line_angle)

        # --- 移動の計算 (0mがインに到達した時点) ---
        move_ratio = 1.0 # 到達時点
        
        # ターゲットxまで移動
        curr_x = min(POINT_C_X, sx + base_dx)
        
        # --- 芝生を回避する弧の計算 ---
        dx_total = POINT_C_X - sx
        # ターゲットに近づくほど急カーブにする (progressの2乗)
        progress = (curr_x - sx) / dx_total if dx_total > 0 else 1.0
        
        # 基本の移動先 (二次関数でカーブを再現)
        curr_y = sy + (POINT_C_Y - sy) * (progress ** 2)

        # --- 最終ガードレール: 芝生（内沼）の境界判定 ---
        # 簡易的な楕円形コースとして、特定のX範囲でyが内側に入りすぎないよう補正
        # ターゲット（c点）は最もイン側。道中は芝生の縁を越えない。
        if sy > 250: # 下半分のコース
            curr_y = max(min(sy, curr_y), INNER_BOUNDARY_BOTTOM if curr_x < 550 else POINT_C_Y)
        else: # 上半分のコース
            curr_y = min(max(sy, curr_y), INNER_BOUNDARY_TOP if curr_x < 550 else POINT_C_Y)

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
        positions = calculate_secure_abc_path(df)
        img_path = visualizer.create_prediction_image(positions)
        
        if img_path:
            visualizer.send_to_discord(img_path, WEBHOOK_URL)
            print(f"C地点のX座標を {POINT_C_X} へ修正し、芝生を回避してイン角へ向かう画像を送信しました。")
        else:
            print("画像生成失敗")
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    handicaps = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    test_data = [{'車': (i % 8) + 1, 'ハンデ': h} for i, h in enumerate(handicaps)]
    run_simulation_and_send(pd.DataFrame(test_data))
