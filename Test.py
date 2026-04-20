import os
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定
# ==========================================
# DiscordのWebhook URLをここに直接貼るか、環境変数に設定してください
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "ここにWebhook_URLを貼り付け"

# 画像上の各白線の基準中心座標
HANDE_LINE_COORDS = {
    0:  {'x': 150, 'y': 380}, # 0m線
    10: {'x': 115, 'y': 365}, # 10m線
    20: {'x': 85,  'y': 340}, # 20m線
    30: {'x': 60,  'y': 305}, # 30m線
    40: {'x': 45,  'y': 260}, # 40m線
    50: {'x': 35,  'y': 210}, # 50m以降
}

# ==========================================
# 2. 配置計算ロジック
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

        if handy < 50:
            # 【通常ハンデ】センター振り分け
            shift = ((num_cars - 1) / 2 - idx) * 20 
            pos['x'] += shift
            pos['y'] -= shift * 0.4
        else:
            # 【50m以降】8番を一番外(左)にする特殊ルール
            reverse_idx = (num_cars - 1) - idx
            pos['x'] += (reverse_idx * 22)
            pos['y'] += (reverse_idx * 10)

        results.append({
            'car': car,
            'x': int(pos['x']),
            'y': int(pos['y'])
        })
    return results

# ==========================================
# 3. 実行関数（計算 -> 画像作成 -> 送信）
# ==========================================
def run_process(df):
    try:
        # 1. 座標計算
        positions = calculate_full_positions(df)
        
        # 2. 画像生成 (visualizer内の関数を呼び出し)
        # positionsは [{'car': 1, 'x': 150, 'y': 380}, ...] の形式
        img_path = visualizer.create_prediction_image(positions)
        
        # 3. Discord送信
        if img_path and os.path.exists(img_path):
            visualizer.send_to_discord(img_path, WEBHOOK_URL)
            print("Discordへの送信が完了しました。")
        else:
            print("画像ファイルが見つかりません。")
            
    except Exception as e:
        print(f"エラーが発生しました: {e}")

# ==========================================
# 4. テスト実行 (1～8番車)
# ==========================================
if __name__ == "__main__":
    test_data = [
        {'車': 1, 'ハンデ': 0},
        {'車': 2, 'ハンデ': 10},
        {'車': 3, 'ハンデ': 10}, # 10m並列
        {'車': 4, 'ハンデ': 20},
        {'車': 5, 'ハンデ': 30},
        {'車': 6, 'ハンデ': 40},
        {'車': 7, 'ハンデ': 50},
        {'車': 8, 'ハンデ': 50}, # 50m並列 (8が外側)
    ]
    df_test = pd.DataFrame(test_data)
    run_process(df_test)
