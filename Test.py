import os
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定と定数定義
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# ハンデごとの【基準座標】と【配置角度】
# 1000029459.png をベースに微調整
HANDE_CONFIG = {
    0:   {'x': 175, 'y': 400, 'angle': 0.0},   
    10:  {'x': 120, 'y': 380, 'angle': -1.1},  
    20:  {'x': 90,  'y': 355, 'angle': -1.2}, 
    30:  {'x': 60,  'y': 323, 'angle': -0.4}, 
    40:  {'x': 40,  'y': 285, 'angle': -0.2}, 
    50:  {'x': 25,  'y': 245, 'angle': -0.2}, 
    60:  {'x': 25,  'y': 199, 'angle': -0.4},  
    70:  {'x': 50,  'y': 161, 'angle': 0.3 }, 
    80:  {'x': 63,  'y': 118, 'angle': 0.5}, 
    90:  {'x': 87,  'y': 82,  'angle': 0.8}, 
    100: {'x': 120, 'y': 50,  'angle': 0.9},  
}

X_LIMIT = (15, 380)  
Y_LIMIT = (30, 460) 

# ==========================================
# 2. 座標計算ロジック
# ==========================================
def calculate_full_positions(df):
    # ハンデ順、次に車番順でソート
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
        # spacingを11に縮小し、車番同士を密着
        spacing = 9 
        offset = (idx - (num_cars - 1) / 2) * spacing
        
        if config['angle'] == 0:
            # 0m地点（垂直）：xは固定、y方向にのみ配置
            target_x = config['x']
            target_y = config['y'] + offset 
        else:
            # 10-100m地点（角度あり）
            # 斜めのライン上で横（X）に離れすぎないよう、Xの移動量をさらに抑制(0.7倍)
            # これにより「縦に重なりつつ、少しだけ横にずれる」密集感を出します
            target_x = config['x'] - (offset * 0.7)
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
            print("横の間隔を詰めた全ハンデ配置図を送信しました。")
        else:
            print("画像生成失敗")

    except Exception as e:
        print(f"エラー: {e}")

# ==========================================
# 4. テスト実行（全ハンデに不規則な台数を配置）
# ==========================================
if __name__ == "__main__":
    # パターン：3車, 2車, 1車, 4車 の繰り返し
    test_data = []
    patterns = [3, 2, 1, 4]
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
