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
# 2. 展開ロジックの設定値（修正版：移動マイルド）
# ==========================================
# 前進量をマイルドに抑えるための係数
TIME_BOOST = 12   # 元の35から大幅に削減
ST_BOOST = 18    # 元の45から大幅に削減

# --- コース境界線の最終防衛ライン ---
# 1枚目よりスタートラインを下げるため下限を広げました
Y_UPPER_LIMIT = 150  
Y_LOWER_LIMIT = 500  # 340だと上すぎるので広げました
X_LEFT_LIMIT = 30    
X_RIGHT_LIMIT = 280  

# ハンデによる横の広がりを少し抑える
HANDY_X_STEP = -25  
# ハンデによる縦の間隔を大幅に短縮（150→50）
HANDY_Y_STEP = 50   

# 【最重要】初期配置オフセットの再設計（2枚目画像を参考に縦一列＆カーブ）
# Xを左寄りにし、白線の形状に合わせて緩やかにカーブさせながら縦に並べます
CAR_FORMAT_OFFSET = {
    1: {'dx': 110, 'dy': -20}, # 最も白線寄り
    2: {'dx': 120, 'dy': 30},
    3: {'dx': 130, 'dy': 80},
    4: {'dx': 140, 'dy': 130},
    5: {'dx': 150, 'dy': 180},
    6: {'dx': 160, 'dy': 230},
    7: {'dx': 170, 'dy': 280}, 
    8: {'dx': 180, 'dy': 330}, 
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
            
            # --- 1. 初期位置計算（修正版） ---
            effective_handy_x = min(handy, 30)
            shift_x = (effective_handy_x / 10) * HANDY_X_STEP
            shift_y = (handy / 10) * HANDY_Y_STEP
            
            # コース中央に配置するため、dxを調整した CAR_FORMAT_OFFSET を使用
            offset = CAR_FORMAT_OFFSET.get(car, {'dx': 150, 'dy': 0})
            
            start_x = offset['dx'] + shift_x
            # start_y の基準を350に下げて、画面下からスタートするように変更
            start_y = 400 + offset['dy'] + shift_y
            
            # --- 2. 移動量計算（修正版：進み具合をマイルドに） ---
            trial_time = float(row.get('試走T', 3.45))
            avg_st = float(row.get('平均st', 0.25))
            
            # 前進のベース値（TIME_BOOST, ST_BOOSTを下げたのでマイルドに）
            total_upward = (
                max(0, (3.45 - trial_time) * TIME_BOOST) + 
                max(0, (0.25 - avg_st) * ST_BOOST)
            )
            
            # --- 3. イン切り込みロジック（そのまま） ---
            x_cut = total_upward * (0.10 + (handy / 10) * 0.02)
            
            # --- 4. 座標統合と動的リミッター（そのまま） ---
            final_x = max(X_LEFT_LIMIT, min(X_RIGHT_LIMIT, start_x + x_cut))

            # 白線の斜めに合わせた動的上限設定（そのまま）
            dynamic_y_upper_limit = 180 - (final_x - 30) * 0.25
            
            raw_y = start_y - total_upward
            # 下限と動的上限でクランプ
            final_y = max(dynamic_y_upper_limit, min(Y_LOWER_LIMIT, raw_y))
            
            calculated_positions.append({
                'car': car, 
                'x': int(final_x),
                'y': int(final_y) 
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
# 3. テスト実行（そのまま）
# ==========================================
if __name__ == "__main__":
    test_data = [
        {'車': 1, '試走T': 3.45, '平均st': 0.25, 'ハンデ': 0},
        {'車': 2, '試走T': 3.42, '平均st': 0.20, 'ハンデ': 10},
        {'車': 3, '試走T': 3.40, '平均st': 0.18, 'ハンデ': 10},
        {'車': 4, '試走T': 3.38, '平均st': 0.15, 'ハンデ': 20},
        {'車': 5, '試走T': 3.36, '平均st': 0.15, 'ハンデ': 20},
        {'車': 6, '試走T': 3.34, '平均st': 0.14, 'ハンデ': 30},
        {'車': 7, '試走T': 3.30, '平均st': 0.12, 'ハンデ': 40},
        {'車': 8, '試走T': 3.25, '平均st': 0.10, 'ハンデ': 50}, 
    ]
    df_test = pd.DataFrame(test_data)

    print("--- 初期配置修正・最終テスト開始 ---")
    generate_and_send(df_test)
