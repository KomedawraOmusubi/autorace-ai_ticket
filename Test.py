import os
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定と定数定義
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# ハンデごとの【基準座標】と【配置角度】
# angle: 0.0は垂直。マイナス値が大きくなるほど「右上(イン)ー左下(アウト)」の傾斜が強くなります。
HANDE_CONFIG = {
    0:   {'x': 170, 'y': 400, 'angle': 0.0},   # ★0mは垂直
    10:  {'x': 120, 'y': 370, 'angle': -1.2},  
    20:  {'x': 90, 'y': 345, 'angle': -1.2}, 
    30:  {'x': 65,  'y': 315, 'angle': -0.6}, 
    40:  {'x': 40,  'y': 280, 'angle': -0.3}, 
    50:  {'x': 20,  'y': 240, 'angle': -0.2}, 
    60:  {'x': 20,  'y': 195, 'angle': -0.4},  
    70:  {'x': 50,  'y': 165, 'angle': 0.4}, 
    80:  {'x': 60,  'y': 115, 'angle': 0.5}, 
    90:  {'x': 85,  'y': 77, 'angle': 0.8}, 
    100: {'x': 120,  'y': 52,  'angle': 0.3},  # ★100mは角度あり
}

# 画像外への飛び出しを防ぐリミッター
X_LIMIT = (15, 380)  
Y_LIMIT = (30, 460) 

# ==========================================
# 2. 座標計算ロジック
# ==========================================
def calculate_full_positions(df):
    # ハンデ順、次に車番順でソート
    df = df.sort_values(['ハンデ', '車'])
    results = []
    
    # 同一ハンデ内の車番リストを作成
    handy_groups = df.groupby('ハンデ')['車'].apply(list).to_dict()
    # 処理済みの台数をカウントする用
    processed_count = {h: 0 for h in handy_groups.keys()}

    for _, row in df.iterrows():
        car = int(row['車'])
        handy = int(row.get('ハンデ', 0))
        
        # 設定が存在するハンデ(0,10,20...)に丸める
        base_h = min(max(0, (handy // 10) * 10), 100)
        config = HANDE_CONFIG[base_h]
        
        num_cars = len(handy_groups[handy])
        idx = processed_count[handy]
        processed_count[handy] += 1

        # 車番同士の間隔
        spacing = 15 
        # 中心からのオフセット計算
        offset = (idx - (num_cars - 1) / 2) * spacing
        
        if config['angle'] == 0:
            # 【垂直モード】 0mなど
            target_x = config['x']
            target_y = config['y'] + offset # 若番(idx小)が上、老番が下
        else:
            # 【角度ありモード】 10m-100m
            # 若番(idx小)ほど右上(x大, y小)へ
            target_x = config['x'] - offset
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
            print(f"全ハンデ配置テスト（計{len(df)}台）を送信しました。")
        else:
            print("画像生成失敗")

    except Exception as e:
        print(f"エラー: {e}")

# ==========================================
# 4. テスト実行（全ハンデに不規則な台数を配置）
# ==========================================
if __name__ == "__main__":
    # 各ハンデに 3車, 2車, 1車, 4車 のパターンを繰り返し配置
    test_data = []
    patterns = [3, 2, 1, 4]
    handicaps = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    
    car_cycle = [1, 2, 3, 4, 5, 6, 7, 8]
    car_idx = 0
    
    for i, h in enumerate(handicaps):
        # パターンから台数を決定（3, 2, 1, 4, 3, 2...）
        num_to_place = patterns[i % len(patterns)]
        
        for _ in range(num_to_place):
            test_data.append({
                '車': car_cycle[car_idx % 8],
                'ハンデ': h
            })
            car_idx += 1

    df_test = pd.DataFrame(test_data)
    run_prediction_and_send(df_test)
