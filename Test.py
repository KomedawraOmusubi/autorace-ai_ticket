import os
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定と定数定義
# ==========================================
# DiscordのWebhook URLを設定
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# ハンデライン（画像上の各白線の基準中心座標）
# ※1000029456.jpgの白線位置に合わせた微調整値
HANDE_LINE_COORDS = {
    0:  {'x': 170, 'y': 400}, 
    10: {'x': 115, 'y': 370}, 
    20: {'x': 85,  'y': 345}, 
    30: {'x': 70,  'y': 315}, 
    40: {'x': 45,  'y': 280}, 
    50: {'x': 35,  'y': 240}, 
}

# --- コースのリミッター（ネズミ色の範囲内のみ許可） ---
X_LIMIT = (30, 350)  
Y_LIMIT = (80, 450) 

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
        pos = HANDE_LINE_COORDS.get(base_handy, HANDE_LINE_COORDS[50]).copy()
        
        same_handy_cars = handy_groups[handy]
        num_cars = len(same_handy_cars)
        idx = same_handy_cars.index(car)

        # --- 初期配置のオフセット計算 ---
        if handy < 50:
            # 【通常ハンデ】
            # 若番(idx小)ほど shiftがプラスになり「右(+)・上(-)」＝右上(内)へ
            shift = ((num_cars - 1) / 2 - idx) * 20 
            pos['x'] += shift
            pos['y'] -= shift * 1.3   # 傾き1.0で右上方向へ
        else:
            # 【50m以降】8番が最外(左下)、7番が内(右上)
            # 7,8番の場合：7番(idx 0) -> reverse 1 / 8番(idx 1) -> reverse 0
            reverse_idx = (num_cars - 1) - idx
            
            # reverse_idxが大きい(7番)ほど「右(+)・上(-)」へ動かす
            move_x = reverse_idx * 22
            pos['x'] += move_x
            pos['y'] -= move_x * 0.01  # ここをマイナスに修正（8番の右上へ7番を置く）

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
# 3. 実行・送信メイン処理
# ==========================================
def run_prediction_and_send(df):
    try:
        if not WEBHOOK_URL or "YOUR_WEBHOOK" in WEBHOOK_URL:
            print("エラー: Discord Webhook URLが正しく設定されていません。")
            return

        # 1. 座標計算
        positions = calculate_full_positions(df)
        
        # 2. 画像生成 (visualizer.py を使用)
        img_path = visualizer.create_prediction_image(positions)
        
        # 3. Discordへ送信
        if img_path:
            visualizer.send_to_discord(img_path, WEBHOOK_URL)
            print("Discordに展開予想図を送信しました。")
        else:
            print("画像生成に失敗しました。")

    except Exception as e:
        print(f"エラーが発生しました: {e}")

# ==========================================
# 4. テスト実行
# ==========================================
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
    df_test = pd.DataFrame(test_data)
    run_prediction_and_send(df_test)
