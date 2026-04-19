import os
import pandas as pd
import requests
import visualizer

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
# 2. 展開ロジックの設定値
# ==========================================
# 試走タイムとSTの影響力（ブースト値）
TIME_BOOST = 350
ST_BOOST = 500

# 外枠ほどインに絞り込みすぎないための比率
OUTSIDE_LINE_RATIO = {
    1: 0.0, 2: 0.0, 3: 0.0, 4: 0.01, 5: 0.02, 6: 0.03, 7: 0.05, 8: 0.06
}
ST_DRIFT_RATIO = 0.03 

# ハンデ10mあたりの斜めスライド量
HANDY_X_STEP = -30  # 10mごとに左(xマイナス)へ
HANDY_Y_STEP = 150  # 10mごとに下(yプラス)へ

# --- 0m地点基準のバラけ方（画像再現：7を6の後ろ、8をその横に配置） ---
CAR_FORMAT_OFFSET = {
    1: {'dx': 270, 'dy': 0},
    2: {'dx': 230, 'dy': 90},
    3: {'dx': 260, 'dy': 180},
    4: {'dx': 120, 'dy': 70},
    5: {'dx': 130, 'dy': 160},
    6: {'dx': 140, 'dy': 250},
    7: {'dx': 140, 'dy': 340}, # 6号車の真後ろ
    8: {'dx': 50,  'dy': 340}, # 7号車の左横
}

def generate_and_send(df):
    try:
        if not WEBHOOK_URL:
            print("エラー: Webhook URLがありません。")
            return False

        calculated_positions = []
        for _, row in df.iterrows():
            car = int(row['車'])
            handy = int(row.get('ハンデ', 0))
            
            # --- 横方向(x)のリミッター：ハンデ30mを上限にする ---
            # これにより、ハンデ40m以上の車も8号車のラインより外にはいかない
            effective_handy_x = min(handy, 30)
            shift_x = (effective_handy_x / 10) * HANDY_X_STEP
            
            # 縦方向(y)はハンデ通りに下げ続ける
            shift_y = (handy / 10) * HANDY_Y_STEP
            
            # 基準位置 ＝ (0m基準オフセット) ＋ (ハンデスライド)
            offset = CAR_FORMAT_OFFSET.get(car, {'dx': 150, 'dy': 0})
            start_x = offset['dx'] + shift_x
            start_y = 350 + offset['dy'] + shift_y
            
            # タイムとSTによる移動計算
            trial_time = float(row.get('試走T', 3.45))
            avg_st = float(row.get('平均st', 0.25))

            # 上への移動量
            total_upward = max(0, (3.45 - trial_time) * TIME_BOOST) + max(0, (0.25 - avg_st) * ST_BOOST)
            
            # 横移動（絞り込みとST遅れによる膨らみ）
            base_cut_ratio = max(0, 0.08 - OUTSIDE_LINE_RATIO.get(car, 0.0))
            x_cut = total_upward * base_cut_ratio
            drift = (avg_st - 0.25) * ST_BOOST * ST_DRIFT_RATIO if avg_st > 0.25 else 0
            
            final_x = start_x - x_cut + drift
            final_y = start_y - total_upward
            
            # --- リミッターの解除 ---
            # yの最小値を350から50へ引き上げ、1号車より前への突き抜けを許可
            calculated_positions.append({
                'car': car, 
                'x': int(max(30, final_x)), 
                'y': int(max(50, final_y))
            })

        if calculated_positions:
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
    # 0m〜30mの基本並び ＋ 50mハンデの突き抜けテスト
    test_data = [
        {'車': 1, '試走T': 3.40, '平均st': 0.15, 'ハンデ': 0},
        {'車': 2, '試走T': 3.39, '平均st': 0.15, 'ハンデ': 20},
        {'車': 3, '試走T': 3.38, '平均st': 0.15, 'ハンデ': 20},
        {'車': 4, '試走T': 3.37, '平均st': 0.15, 'ハンデ': 30},
        {'車': 5, '試走T': 3.36, '平均st': 0.15, 'ハンデ': 30},
        {'車': 6, '試走T': 3.35, '平均st': 0.15, 'ハンデ': 30},
        {'車': 7, '試走T': 3.30, '平均st': 0.15, 'ハンデ': 40},
        
# 爆速の50mハンデ車（1号車をぶち抜く設定）
        {'車': 8, '試走T': 3.27, '平均st': 0.10, 'ハンデ': 50}, 
    ]
    df_test = pd.DataFrame(test_data)

    print("--- 処理開始 ---")
    send_discord_message("🔥 リミッター解除・ハンデ連動テスト配信 🔥")
    if generate_and_send(df_test):
        print("成功しました")
    else:
        print("失敗しました")
