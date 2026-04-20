import os
import math
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定と定数定義
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# ターゲット座標：画像右側、白線のイン角
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
# 2. 移動シミュレーション・座標計算ロジック
# ==========================================
def calculate_reaching_positions(df):
    """
    誰かがターゲットに到達した瞬間の全車の位置を計算する
    """
    df = df.sort_values(['ハンデ', '車'])
    temp_positions = []
    
    # 1. まず各車のスタート位置とターゲットまでの距離を算出
    handy_groups = df.groupby('ハンデ')['車'].apply(list).to_dict()
    processed_count = {h: 0 for h in handy_groups.keys()}

    for _, row in df.iterrows():
        car = int(row['車'])
        handy = int(row.get('ハンデ', 0))
        trial_time = float(row.get('試走', 3.30))
        
        base_h = min(max(0, (handy // 10) * 10), 100)
        config = HANDE_CONFIG[base_h]
        
        # スタート時の配置角度を計算
        dx = TARGET_X - config['x']
        dy = TARGET_Y - config['y']
        angle_to_target = math.atan2(dy, dx)
        line_angle = angle_to_target + math.pi / 2

        num_cars = len(handy_groups[handy])
        idx = processed_count[handy]
        processed_count[handy] += 1
        spacing = config.get('spacing', 11)
        offset = (idx - (num_cars - 1) / 2) * spacing
        
        # 各車の初期座標 (sx, sy)
        sx = config['x'] + offset * math.cos(line_angle)
        sy = config['y'] + offset * math.sin(line_angle)
        
        # ターゲットまでの距離と必要時間（時間 = 距離 * 試走タイム ※簡易係数）
        dist_to_target = math.sqrt((TARGET_X - sx)**2 + (TARGET_Y - sy)**2)
        time_needed = dist_to_target * trial_time
        
        temp_positions.append({
            'car': car,
            'sx': sx, 'sy': sy,
            'angle': angle_to_target,
            'dist': dist_to_target,
            'time_needed': time_needed
        })

    # 2. 最も早く到達する車の時間を特定
    min_time = min(p['time_needed'] for p in temp_positions)
    
    # 3. その時間経過時点での全車の位置を決定
    final_results = []
    for p in temp_positions:
        # 進んだ比率 (最速の車は ratio=1.0 になる)
        ratio = min_time / p['time_needed']
        
        curr_x = p['sx'] + (TARGET_X - p['sx']) * ratio
        curr_y = p['sy'] + (TARGET_Y - p['sy']) * ratio
        
        final_results.append({
            'car': p['car'],
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

        # 「到達時点」の座標を計算
        positions = calculate_reaching_positions(df)
        
        img_path = visualizer.create_prediction_image(positions)
        
        if img_path:
            visualizer.send_to_discord(img_path, WEBHOOK_URL)
            print("誰かがインに到達した瞬間の画像を送信しました。")
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
            '試走': 3.30  # 全員同じタイム
        })

    df_test = pd.DataFrame(test_data)
    run_simulation_and_send(df_test)
