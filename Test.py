import os
import pandas as pd
import requests
# 環境に応じて visualizer をインポートしてください
# import visualizer 

# ==========================================
# 1. 環境変数の設定
# ==========================================
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
# 2. 展開ロジックの設定値（進みすぎ防止・マイルド版）
# ==========================================
# 前進の激しさを抑えるための係数
TIME_BOOST = 15    # 35から大幅に下げ、タイム差による飛び出しを抑制
ST_BOOST = 20      # 45から下方修正
MOVEMENT_SCALE = 0.6  # 全体の移動量をさらに60%に圧縮

# --- コース境界線の最終防衛ライン ---
Y_LOWER_LIMIT = 360  # 画面下側の限界
X_LEFT_LIMIT = 35    # 左側の限界
X_RIGHT_LIMIT = 280  # 右側の限界

# 外側を通る車番の補正
OUTSIDE_LINE_RATIO = {
    1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.02
}
ST_DRIFT_RATIO = 0.01 

# スタート時の密集度調整
HANDY_X_STEP = -20  # ハンデによる横の広がり
HANDY_Y_STEP = 50   # ハンデによる縦の間隔（150から50に短縮して密集させる）

# 各車番の初期位置オフセット（コース形状に合わせて階段状に配置）
CAR_FORMAT_OFFSET = {
    1: {'dx': 270, 'dy': -20},
    2: {'dx': 240, 'dy': 10},
    3: {'dx': 210, 'dy': 40},
    4: {'dx': 180, 'dy': 70},
    5: {'dx': 150, 'dy': 100},
    6: {'dx': 120, 'dy': 130},
    7: {'dx': 90,  'dy': 160}, 
    8: {'dx': 60,  'dy': 190}, 
}

def generate_and_send(df):
    try:
        calculated_positions = []
        for _, row in df.iterrows():
            car = int(row['車'])
            handy = int(row.get('ハンデ', 0))
            
            # --- 1. 初期位置計算 ---
            effective_handy_x = min(handy, 30)
            shift_x = (effective_handy_x / 10) * HANDY_X_STEP
            shift_y = (handy / 10) * HANDY_Y_STEP
            
            offset = CAR_FORMAT_OFFSET.get(car, {'dx': 150, 'dy': 0})
            start_x = offset['dx'] + shift_x
            start_y = 350 + offset['dy'] + shift_y
            
            # --- 2. 移動量計算（進み具合をマイルドに） ---
            trial_time = float(row.get('試走T', 3.45))
            avg_st = float(row.get('平均st', 0.25))
            
            # 前進ベース値（基準 3.45 / 0.25）
            total_upward = (
                max(0, (3.45 - trial_time) * TIME_BOOST) + 
                max(0, (0.25 - avg_st) * ST_BOOST)
            ) * MOVEMENT_SCALE
            
            # --- 3. イン切り込みロジック ---
            handy_cut_bonus = (handy / 10) * 0.02 
            base_cut_ratio = max(0, 0.12 + handy_cut_bonus - OUTSIDE_LINE_RATIO.get(car, 0.0))
            x_cut = total_upward * base_cut_ratio
            drift = (avg_st - 0.25) * ST_BOOST * ST_DRIFT_RATIO if avg_st > 0.25 else 0
            
            # --- 4. 座標統合と全方向リミッター ---
            # 横座標を先に確定
            final_x = start_x + x_cut - drift
            final_x = max(X_LEFT_LIMIT, min(X_RIGHT_LIMIT, final_x))

            # 【重要】白線の傾きに合わせた動的Yリミッター
            # 左(X=35)ほど白線が手前(Y=180)にあり、右(X=280)ほど奥(Y=120)にあると仮定
            dynamic_y_upper_limit = 180 - (final_x - 35) * 0.24
            
            raw_y = start_y - total_upward
            # 下限と動的上限でクランプ
            final_y = max(dynamic_y_upper_limit, min(Y_LOWER_LIMIT, raw_y))
            
            calculated_positions.append({
                'car': car, 
                'x': int(final_x),
                'y': int(final_y) 
            })

        if calculated_positions:
            # デバッグ表示
            print(f"{'車':<4} | {'X':<5} | {'Y':<5}")
            print("-" * 20)
            for pos in calculated_positions:
                print(f"{pos['car']:<4} | {pos['x']:<5} | {pos['y']:<5}")
            
            # 送信処理（visualizerが有効な場合）
            # img_path = visualizer.create_prediction_image(calculated_positions)
            # if WEBHOOK_URL:
            #     visualizer.send_to_discord(img_path, WEBHOOK_URL)
            return True
        return False
    except Exception as e:
        print(f"エラー: {e}")
        return False

# ==========================================
# 3. テスト実行（1～8号車フルメンバー）
# ==========================================
if __name__ == "__main__":
    # 多様なタイム設定でのテスト
    test_data = [
        {'車': 1, '試走T': 3.45, '平均st': 0.25, 'ハンデ': 0},
        {'車': 2, '試走T': 3.43, '平均st': 0.22, 'ハンデ': 10},
        {'車': 3, '試走T': 3.41, '平均st': 0.20, 'ハンデ': 20},
        {'車': 4, '試走T': 3.40, '平均st': 0.18, 'ハンデ': 30},
        {'車': 5, '試走T': 3.38, '平均st': 0.17, 'ハンデ': 30},
        {'車': 6, '試走T': 3.35, '平均st': 0.15, 'ハンデ': 40},
        {'車': 7, '試走T': 3.32, '平均st': 0.13, 'ハンデ': 50},
        {'車': 8, '試走T': 3.28, '平均st': 0.11, 'ハンデ': 50}, 
    ]
    df_test = pd.DataFrame(test_data)

    print("--- 全車番・進行度抑制テスト開始 ---")
    if generate_and_send(df_test):
        print("\n計算成功。画像の密集具合を確認してください。")
    else:
        print("\n計算失敗。")
