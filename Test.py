import os
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定と定数定義
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# ハンデごとの【基準座標】【配置角度】【間隔】を個別に定義
# angle: 0.0は垂直。マイナスは右上(イン)-左下(アウト)。
# spacing: そのハンデライン上での車番同士の距離。多車（5台など）の場合は少し詰め気味に設定。
HANDE_CONFIG = {
    0:   {'x': 175, 'y': 400, 'angle': 0.0,  'spacing': 12}, # 垂直は少し余裕を持たせる
    10:  {'x': 120, 'y': 380, 'angle': -0.8, 'spacing': 9},  # カーブ区間はタイトに
    20:  {'x': 90,  'y': 355, 'angle': -0.6, 'spacing': 9}, 
    30:  {'x': 60,  'y': 323, 'angle': -0.3, 'spacing': 10}, 
    40:  {'x': 40,  'y': 285, 'angle': -0.1, 'spacing': 13}, 
    50:  {'x': 25,  'y': 245, 'angle':-0.05, 'spacing': 13}, 
    60:  {'x': 25,  'y': 199, 'angle': 0.1, 'spacing': 13},  
    70:  {'x': 50,  'y': 161, 'angle': 0.2,  'spacing': 13}, 
    80:  {'x': 63,  'y': 118, 'angle': 0.4,  'spacing': 13}, 
    90:  {'x': 87,  'y': 82,  'angle': 0.6,  'spacing': 9}, 
    100: {'x': 120, 'y': 52,  'angle': 0.9,  'spacing': 8},  
}

X_LIMIT = (15, 380)  
Y_LIMIT = (30, 460) 

# ==========================================
# 2. 座標計算ロジック
# ==========================================
def calculate_full_positions(df):
    # 並び順を安定させる（ハンデ内は車番昇順）
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

        # --- 間隔の調整 ---
        spacing = config.get('spacing', 10)
        offset = (idx - (num_cars - 1) / 2) * spacing
        
        if config['angle'] == 0:
            # 【0m：垂直配置】
            target_x = config['x']
            target_y = config['y'] + offset 
        else:
            # 【10-100m：角度あり配置】
            # 斜めの時、X方向に広がりすぎると白線から浮くため、Xの移動をさらに抑制(0.6倍)
            target_x = config['x'] - (offset * 0.6)
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
            print(f"全ハンデ5台配置テスト（計{len(df)}台）を送信しました。")
        else:
            print("画像生成失敗")

    except Exception as e:
        print(f"エラー: {e}")

# ==========================================
# 4. テスト実行（各ハンデに5台ずつ配置）
# ==========================================
if __name__ == "__main__":
    test_data = []
    # 全ハンデに一律5台配置して密度を確認
    patterns = [5]
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
