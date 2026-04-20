import os
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定と定数定義
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# ハンデラインの基準座標
# コースの形状に合わせて、重ハンデほど「上」かつ「左」へスライド
HANDE_LINE_COORDS = {
    0:   {'x': 170, 'y': 400}, 
    10:  {'x': 115, 'y': 370}, 
    20:  {'x': 85,  'y': 345}, 
    30:  {'x': 70,  'y': 315}, 
    40:  {'x': 45,  'y': 280}, 
    50:  {'x': 35,  'y': 240}, 
    60:  {'x': 32,  'y': 205}, 
    70:  {'x': 30,  'y': 175}, 
    80:  {'x': 28,  'y': 145}, 
    90:  {'x': 26,  'y': 115}, 
    100: {'x': 25,  'y': 85},  
}

X_LIMIT = (15, 385)  
Y_LIMIT = (40, 460) 

# ==========================================
# 2. 座標計算ロジック
# ==========================================
def calculate_full_positions(df):
    # 同一ハンデ内での並びを制御するため、車番昇順で処理
    df = df.sort_values(['ハンデ', '車'])
    results = []
    
    handy_groups = df.groupby('ハンデ')['車'].apply(list).to_dict()
    processed_count = {h: 0 for h in handy_groups.keys()}

    for _, row in df.iterrows():
        car = int(row['車'])
        handy = int(row.get('ハンデ', 0))
        
        base_handy = min(max(0, (handy // 10) * 10), 100)
        pos = HANDE_LINE_COORDS[base_handy].copy()
        
        num_cars = len(handy_groups[handy])
        # idx 0 がそのハンデの中で一番若い車番
        idx = processed_count[handy]
        processed_count[handy] += 1

        # 車番同士の間隔
        spacing = 12 

        # --- 配置ロジックの統一 ---
        # 「若番ほど内側(右上)」「老番ほど外側(左下)」に並べる
        # 基準点(pos)を2車の中間に持ってくるためのオフセット計算
        offset = ((num_cars - 1) / 2 - idx) * spacing
        
        if handy < 50:
            # 0-40m: カーブがきついので角度を急にする
            pos['x'] += offset
            pos['y'] -= offset * 1.2
        else:
            # 50-100m: 直線に近いが、白線はまだ斜めなので角度を維持
            # ここで「おかしい」部分を修正：xだけでなくyもしっかり動かす
            pos['x'] += offset
            pos['y'] -= offset * 0.8

        results.append({
            'car': car,
            'x': int(max(X_LIMIT[0], min(X_LIMIT[1], pos['x']))),
            'y': int(max(Y_LIMIT[0], min(Y_LIMIT[1], pos['y'])))
        })
    return results

# ==========================================
# 3. メイン処理
# ==========================================
def run_prediction_and_send(df):
    try:
        if not WEBHOOK_URL or "YOUR_WEBHOOK" in WEBHOOK_URL:
            print("エラー: Webhook URL未設定")
            return

        positions = calculate_full_positions(df)
        img_path = visualizer.create_prediction_image(positions)
        
        if img_path:
            visualizer.send_to_discord(img_path, WEBHOOK_URL)
            print(f"全{len(df)}台の配置図を送信しました。")

    except Exception as e:
        print(f"エラー: {e}")

# ==========================================
# 4. テスト実行（全ハンデに複数配置）
# ==========================================
if __name__ == "__main__":
    # 1〜8車を複数回使い、全ハンデに2台ずつ並べて確認
    test_cases = []
    handicaps = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    
    car_num = 1
    for h in handicaps:
        test_cases.append({'車': car_num, 'ハンデ': h})
        car_num = car_num + 1 if car_num < 8 else 1
        test_cases.append({'車': car_num, 'ハンデ': h})
        car_num = car_num + 1 if car_num < 8 else 1

    df_test = pd.DataFrame(test_cases)
    run_prediction_and_send(df_test)
