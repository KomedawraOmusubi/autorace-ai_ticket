import os
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定と定数定義
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# ハンデラインの基準座標（0mから100mまで定義）
HANDE_LINE_COORDS = {
    0:   {'x': 170, 'y': 400}, 
    10:  {'x': 115, 'y': 370}, 
    20:  {'x': 85,  'y': 345}, 
    30:  {'x': 70,  'y': 315}, 
    40:  {'x': 45,  'y': 280}, 
    50:  {'x': 35,  'y': 240}, 
    60:  {'x': 35,  'y': 200}, 
    70:  {'x': 35,  'y': 170}, 
    80:  {'x': 35,  'y': 140}, 
    90:  {'x': 35,  'y': 110}, 
    100: {'x': 35,  'y': 80},  
}

X_LIMIT = (20, 380)  
Y_LIMIT = (50, 450) 

# ==========================================
# 2. 座標計算ロジック
# ==========================================
def calculate_full_positions(df):
    results = []
    # ハンデごとにグループ化して、同一ハンデ内の並び順を管理
    # 車番が重複してもリスト内での位置(index)で座標をずらす
    handy_groups = df.groupby('ハンデ')['車'].apply(list).to_dict()
    
    # 重複車番を正しく処理するため、各ハンデで何台目かを数えるカウンター
    processed_count = {h: 0 for h in handy_groups.keys()}

    for _, row in df.iterrows():
        car = int(row['車'])
        handy = int(row.get('ハンデ', 0))
        
        base_handy = min(max(0, (handy // 10) * 10), 100)
        pos = HANDE_LINE_COORDS[base_handy].copy()
        
        num_cars_at_this_handy = len(handy_groups[handy])
        idx = processed_count[handy]
        processed_count[handy] += 1

        # 隣同士の間隔（ここを詰めると密集します）
        spacing = 15 

        if handy < 50:
            # 【カーブ区間】
            # 同一ハンデ内で「内側」から順に並べる計算
            shift = ((num_cars_at_this_handy - 1) / 2 - idx) * spacing
            pos['x'] += shift
            pos['y'] -= shift * 1.1 
        else:
            # 【直線区間】
            # イン(右)・アウト(左)の関係を整理
            reverse_idx = (num_cars_at_this_handy - 1) - idx
            move_val = reverse_idx * spacing
            pos['x'] += move_val
            pos['y'] -= move_val * 0.3 

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
            print("エラー: Webhook URLが未設定です。")
            return

        positions = calculate_full_positions(df)
        img_path = visualizer.create_prediction_image(positions)
        
        if img_path:
            visualizer.send_to_discord(img_path, WEBHOOK_URL)
            print(f"全{len(df)}台の配置図を送信しました。")

    except Exception as e:
        print(f"エラー: {e}")

# ==========================================
# 4. 全ハンデ埋め尽くしテスト（1-8車を繰り返し使用）
# ==========================================
if __name__ == "__main__":
    # 各ハンデに車を配置するデータセット
    # 0m〜100mの全11箇所に、1〜8車を順番に2回以上使って配置
    full_test_data = [
        {'車': 1, 'ハンデ': 0},
        {'車': 2, 'ハンデ': 10},
        {'車': 3, 'ハンデ': 10}, # 10mに2台
        {'車': 4, 'ハンデ': 20},
        {'車': 5, 'ハンデ': 30},
        {'車': 6, 'ハンデ': 40},
        {'車': 7, 'ハンデ': 40}, # 40mに2台
        {'車': 8, 'ハンデ': 50},
        {'車': 1, 'ハンデ': 50}, # 1を再利用
        {'車': 2, 'ハンデ': 60},
        {'車': 3, 'ハンデ': 70},
        {'車': 4, 'ハンデ': 80},
        {'車': 5, 'ハンデ': 80}, # 80mに2台
        {'車': 6, 'ハンデ': 90},
        {'車': 7, 'ハンデ': 100},
        {'車': 8, 'ハンデ': 100}, # 100mに2台
    ]
    
    df_test = pd.DataFrame(full_test_data)
    run_prediction_and_send(df_test)
