import os
import pandas as pd
import requests
import visualizer

# ==========================================
# 1. 環境変数の設定
# ==========================================
# GitHub Secretsの登録名「DISCORD_WEBHOOK_URL」を使用
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def send_discord_message(content):
    if not WEBHOOK_URL:
        print("エラー: DISCORD_WEBHOOK_URLが取得できていません。")
        return
    data = {"content": content}
    try:
        requests.post(WEBHOOK_URL, json=data).raise_for_status()
    except Exception as e:
        print(f"Discord送信エラー: {e}")

# ==========================================
# 2. 展開ロジックの設定値
# ==========================================
TIME_BOOST = 350
ST_BOOST = 500
OUTSIDE_LINE_RATIO = {
    1: 0.0, 2: 0.0, 3: 0.0,
    4: 0.01, 5: 0.02, 6: 0.03, 
    7: 0.05, 8: 0.06
}
ST_DRIFT_RATIO = 0.03 

def generate_and_send(df):
    try:
        if not WEBHOOK_URL:
            print("エラー: Webhook URLがありません。")
            return False

        # 初期配置座標
        layout_handicap = {
            1: {'x': 270, 'y': 60},
            2: {'x': 230,  'y': 560},
            3: {'x': 260, 'y': 660},
            4: {'x': 120,  'y': 630},
            5: {'x': 130, 'y': 720}, 
            6: {'x': 140, 'y': 810},
            7: {'x': 30,  'y': 800}, 
            8: {'x': 40, 'y': 900},
        }
        
        calculated_positions = []
        for _, row in df.iterrows():
            car = int(row['車'])
            base = layout_handicap.get(car, {'x': 150, 'y': 800})
            
            trial_time = float(row.get('試走T', 3.45))
            avg_st = float(row.get('平均st', 0.25))

            # 縦移動
            total_upward = max(0, (3.45 - trial_time) * TIME_BOOST) + max(0, (0.25 - avg_st) * ST_BOOST)
            
            # 横移動
            base_cut_ratio = max(0, 0.08 - OUTSIDE_LINE_RATIO.get(car, 0.0))
            x_cut = total_upward * base_cut_ratio
            drift = (avg_st - 0.25) * ST_BOOST * ST_DRIFT_RATIO if avg_st > 0.25 else 0
            
            final_x = base['x'] - x_cut + drift
            final_y = base['y'] - total_upward
            
            #リミッター
            
            calculated_positions.append({
                'car': car, 'x': int(max(30, final_x)), 'y': int(max(370, final_y))
            })

        if calculated_positions:
            img_path = visualizer.create_prediction_image(calculated_positions)
            visualizer.send_to_discord(img_path, WEBHOOK_URL)
            return True
        return False
    except Exception as e:
        print(f"エラー: {e}")
        return False

if __name__ == "__main__":
    # 全車（1〜8）のテストデータを作成
    test_data = [
        {'車': 1, '試走T': 3.35, '平均st': 0.15},
        {'車': 2, '試走T': 3.35, '平均st': 0.15},
        {'車': 3, '試走T': 3.35, '平均st': 0.15},
        {'車': 4, '試走T': 3.35, '平均st': 0.15},
        {'車': 5, '試走T': 3.35, '平均st': 0.15},
        {'車': 6, '試走T': 3.35, '平均st': 0.15},
        {'車': 7, '試走T': 3.35, '平均st': 0.15},
        {'車': 8, '試走T': 3.35, '平均st': 0.15},
    ]
    df_test = pd.DataFrame(test_data)

    print("--- 処理開始 ---")
    send_discord_message("🔥 全車描画テスト配信 🔥")
    if generate_and_send(df_test):
        print("成功しました")
    else:
        print("失敗しました")
