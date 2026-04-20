import os
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定と定数定義
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# 【再調整版】画像上の各白線の中心座標
# xを少し大きく（右へ）、yを少し大きく（下へ）微調整
HANDE_LINE_COORDS = {
    0:  {'x': 235, 'y': 595}, # 0m線（ホームストレッチ入り口）
    10: {'x': 185, 'y': 585}, # 10m線
    20: {'x': 145, 'y': 565}, # 20m線
    30: {'x': 110, 'y': 530}, # 30m線
    40: {'x': 85,  'y': 485}, # 40m線
    50: {'x': 70,  'y': 430}, # 50m線（4角のカーブ中）
}

# --- コースのリミッター（ネズミ色の範囲内を厳守） ---
# 画像サイズに合わせて調整してください（例：1000px基準の場合）
X_LIMIT = (60, 940)  
Y_LIMIT = (80, 620) 

# ==========================================
# 2. 座標計算ロジック
# ==========================================
def calculate_full_positions(df):
    df = df.sort_values('車')
    results = []
    handy_groups = df.groupby('ハンデ')['車'].apply(list).to_dict()

    for _, row in df.iterrows():
        car = int(row['車'])
        handy = int(row.get('ハンデ', 0))
        
        base_handy = handy if handy <= 50 else 50
        # 基準座標をコピー
        pos = HANDE_LINE_COORDS.get(base_handy, HANDE_LINE_COORDS[50]).copy()
        
        same_handy_cars = handy_groups[handy]
        num_cars = len(same_handy_cars)
        idx = same_handy_cars.index(car)

        if handy < 50:
            # 並列配置のズレ幅を15pxに縮小（白線からはみ出さないように）
            shift = ((num_cars - 1) / 2 - idx) * 15 
            pos['x'] += shift
            pos['y'] -= shift * 0.3 # 傾斜角の調整
        else:
            # 50m以降：8番を外、7番を内。ズレ幅を調整
            reverse_idx = (num_cars - 1) - idx
            pos['x'] += (reverse_idx * 20)
            pos['y'] += (reverse_idx * 10)

        # --- リミッター適用 ---
        final_x = max(X_LIMIT[0], min(X_LIMIT[1], pos['x']))
        final_y = max(Y_LIMIT[0], min(Y_LIMIT[1], pos['y']))

        results.append({
            'car': car,
            'x': int(final_x),
            'y': int(final_y)
        })
    return results

# ==========================================
# 3. 実行・送信処理
# ==========================================
def run_prediction_and_send(df):
    try:
        if not WEBHOOK_URL or "YOUR_WEBHOOK" in WEBHOOK_URL:
            print("Webhook URL未設定")
            return

        positions = calculate_full_positions(df)
        img_path = visualizer.create_prediction_image(positions)
        
        if img_path:
            visualizer.send_to_discord(img_path, WEBHOOK_URL)
            print("Discordへ送信成功")
        else:
            print("画像生成失敗")

    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    test_data = [
        {'車': 1, 'ハンデ': 0},
        {'車': 2, 'ハンデ': 10},
        {'車': 3, 'ハンデ': 10},
        {'車': 4, 'ハンデ': 20},
        {'車': 5, 'ハンデ': 30},
        {'車': 6, 'ハンデ': 40},
        {'車': 7, 'ハンデ': 50},
        {'車': 8, 'ハンデ': 50},
    ]
    run_prediction_and_send(pd.DataFrame(test_data))
