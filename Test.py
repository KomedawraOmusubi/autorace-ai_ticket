import os
import pandas as pd
import requests
import visualizer

# ==========================================
# 1. 環境変数の設定
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# ==========================================
# 2. 初期配置の直接指定 (X, Y)
# ==========================================
# 2枚目の理想図を参考に、白線に沿って縦に並ぶよう座標を直打ちします
# X: 右へ行くほど大きい / Y: 下へ行くほど大きい
CAR_INITIAL_POSITIONS = {
    1: {'x': 340, 'y': 360}, # 一番上・右寄り
    2: {'x': 250, 'y': 480},
    3: {'x': 270, 'y': 550},
    4: {'x': 110, 'y': 620},
    5: {'x': 120, 'y': 700},
    6: {'x': 130, 'y': 780},
    7: {'x': 30,  'y': 800}, 
    8: {'x': 40,  'y': 880}, # 一番下
}

def generate_and_send(df):
    try:
        if not WEBHOOK_URL:
            print("エラー: Webhook URLがありません。")
            return False

        calculated_positions = []
        for _, row in df.iterrows():
            car = int(row['車'])
            
            # --- 1. 初期座標の取得 ---
            # dx, dy を介さず、設定した X, Y をそのまま使用します
            pos = CAR_INITIAL_POSITIONS.get(car, {'x': 150, 'y': 500})
            
            final_x = pos['x']
            final_y = pos['y']
            
            # --- 2. 移動ロジック (すべて無効化) ---
            # total_upward = 0
            # x_cut = 0
            
            # そのままの座標をリストに追加
            calculated_positions.append({
                'car': car, 
                'x': int(final_x),
                'y': int(final_y) 
            })

        if calculated_positions:
            # ログ出力して座標を確認
            print("--- 配置確認 (固定XY) ---")
            for p in calculated_positions:
                print(f"車番{p['car']}: X={p['x']}, Y={p['y']}")
            
            img_path = visualizer.create_prediction_image(calculated_positions)
            visualizer.send_to_discord(img_path, WEBHOOK_URL)
            return True
        return False
    except Exception as e:
        print(f"エラー: {e}")
        return False

# ==========================================
# 3. テスト実行
# ==========================================
if __name__ == "__main__":
    # 全車番(1-8)をテスト
    test_data = [{'車': i} for i in range(1, 9)]
    df_test = pd.DataFrame(test_data)
    
    print("--- 固定座標配置テスト開始 ---")
    generate_and_send(df_test)
