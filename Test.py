import os
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定と定数定義
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# ハンデごとの【基準座標】【配置角度】【間隔】
# 飛び出し防止のため、重ハンデ(80-100)のx座標を少し内側(右)へ調整
HANDE_CONFIG = {
    0:   {'x': 175, 'y': 400, 'angle': 0.0,  'spacing': 10}, 
    10:  {'x': 120, 'y': 380, 'angle': -0.7, 'spacing': 10},  
    20:  {'x': 87,  'y': 352, 'angle': -0.5, 'spacing': 10}, 
    30:  {'x': 65,  'y': 323, 'angle': -0.4, 'spacing': 10}, 
    40:  {'x': 45,  'y': 285, 'angle': -0.25, 'spacing': 10}, 
    50:  {'x': 35,  'y': 245, 'angle':-0.1, 'spacing': 10}, 
    60:  {'x': 35,  'y': 199, 'angle': 0.07,  'spacing': 10},  
    70:  {'x': 50,  'y': 165, 'angle': 0.32,  'spacing': 12}, 
    80:  {'x': 70,  'y': 125, 'angle': 0.42,  'spacing': 11}, # xを少し右へ
    90:  {'x': 95, 'y': 95,  'angle': 0.6,  'spacing': 10}, # xを少し右へ
    100: {'x': 125, 'y': 68,  'angle': 0.7 ,  'spacing': 10},  # xを少し右へ
}

X_LIMIT = (15, 380)  
Y_LIMIT = (30, 460) 

# ==========================================
# 2. 座標計算ロジック
# ==========================================
def calculate_full_positions(df):
    df = df.sort_values(['ハンデ', '車'])
    results = []
    
    handy_groups = df.groupby('ハンデ')['車'].apply(list).to_dict()
    processed_count = {h: 0 for h in handy_groups.keys()}

    for _, row in df.iterrows():
        car = int(row['車'])
        handy = int(row.get('ハンデ', 0))
        
        base_h = min(max(0, (handy // 10) * 10), 100)
        config = HANDE_CONFIG[base_h]
        
        num_cars = len(handy_groups[handy])
        idx = processed_count[handy]
        processed_count[handy] += 1

        spacing = config.get('spacing', 10)
        offset = (idx - (num_cars - 1) / 2) * spacing
        
        if config['angle'] == 0:
            target_x = config['x']
            target_y = config['y'] + offset 
        else:
            # --- 飛び出し防止ロジック ---
            # 角度(config['angle'])の絶対値が大きいほど、X方向の広がりを抑える(x_ratio)
            # これにより、斜めのライン上で車番が横に膨らみすぎるのを防ぎます
            angle_abs = abs(config['angle'])
            x_ratio = max(0.1, 1.0 - (angle_abs * 0.8)) # 角度がつくほど比率を下げる
            
            target_x = config['x'] - (offset * x_ratio)
            target_y = config['y'] - (offset * config['angle'])

        results.append({
            'car': car,
            'x': int(max(X_LIMIT[0], min(X_LIMIT[1], target_x))),
            'y': int(max(Y_LIMIT[0], min(Y_LIMIT[1], target_y)))
        })
    return results

# ==========================================
# 3. 実行メイン処理
# ==========================================
def run_prediction_and_send(df):
    try:
        if not WEBHOOK_URL or "YOUR_WEBHOOK" in WEBHOOK_URL:
            print("エラー: Discord Webhook URLを設定してください。")
            return

        positions = calculate_full_positions(df)
        img_path = visualizer.create_prediction_image(positions)
        
        if img_path:
            visualizer.send_to_discord(img_path, WEBHOOK_URL)
            print("飛び出し防止補正を適用して送信しました。")
        else:
            print("画像生成失敗")

    except Exception as e:
        print(f"エラー: {e}")

# ==========================================
# 4. テスト実行
# ==========================================
if __name__ == "__main__":
    test_data = []
    patterns = [5] # 全ハンデ5台で厳しくチェック
    handicaps = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    
    car_cycle = [1, 2, 3, 4, 5, 6, 7, 8]
    car_idx = 0
    
    for i, h in enumerate(handicaps):
        num_to_place = patterns[i % len(patterns)]
        for _ in range(num_to_place):
            test_data.append({
                '車': car_cycle[car_idx % 8],
                'ハンデ': h
            })
            car_idx += 1

    df_test = pd.DataFrame(test_data)
    run_prediction_and_send(df_test)
