import os
import pandas as pd
import requests
import visualizer  # 自作モジュール

# ==========================================
# 1. 環境変数の設定
# ==========================================
# GitHub Secretsで設定した名前（WEBHOOK_URL）を取得
DISCORD_WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# ==========================================
# 2. メッセージ送信関数
# ==========================================
def send_discord_message(content):
    """テキストメッセージを送信"""
    if not DISCORD_WEBHOOK_URL:
        print("エラー: DISCORD_WEBHOOK_URLが設定されていません。")
        return
    data = {"content": content}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data).raise_for_status()
    except Exception as e:
        print(f"Discord送信エラー: {e}")

# ==========================================
# 3. 展開予想図（画像）生成・送信ロジック
# ==========================================
# 設定値（バラけ具合を調整するパラメータ）
TIME_BOOST = 350
ST_BOOST = 500
OUTSIDE_LINE_RATIO = {
    1: 0.0, 2: 0.0, 3: 0.0,
    4: 0.01, 5: 0.02, 6: 0.03, 
    7: 0.05, 8: 0.06
}
ST_DRIFT_RATIO = 0.03 

def generate_and_send(df, webhook_url=DISCORD_WEBHOOK_URL):
    """DFから予想図を生成して送信"""
    try:
        if not webhook_url:
            print("エラー: Webhook URLがありません。")
            return False

        # ハンデ戦用ベース座標
        layout_handicap = {
            1: {'x': 230, 'y': 380}, 2: {'x': 180, 'y': 520},
            3: {'x': 210, 'y': 540}, 4: {'x': 150, 'y': 720},
            5: {'x': 170, 'y': 740}, 6: {'x': 200, 'y': 760},
            7: {'x': 130, 'y': 880}, 8: {'x': 160, 'y': 900},
        }

        # オープン戦用ベース座標
        layout_open = {
            1: {'x': 70,  'y': 480}, 2: {'x': 90,  'y': 570},
            3: {'x': 110, 'y': 650}, 4: {'x': 130, 'y': 730},
            5: {'x': 150, 'y': 810}, 6: {'x': 170, 'y': 890},
            7: {'x': 190, 'y': 970}, 8: {'x': 210, 'y': 1050},
        }

        # オープン戦判定（6号車基準）
        car6_data = df[df['車'] == 6]
        is_open_race = False
        if not car6_data.empty:
            try:
                if float(car6_data.iloc[0]['ハンデ']) == 0:
                    is_open_race = True
            except: pass
        
        current_layout = layout_open if is_open_race else layout_handicap
        calculated_positions = []

        for _, row in df.iterrows():
            car = int(row['車'])
            if car not in current_layout: continue
            
            base = current_layout[car]
            trial_val = str(row.get('試走T', '')).strip()
            if trial_val in ["", "-", "nan", "欠車"]: continue

            try:
                trial_time = float(trial_val)
                st_val = str(row.get('平均st', '')).strip()
                avg_st = float(st_val) if st_val not in ["", "-", "nan"] else 0.25
            except: continue

            # 縦移動（Y軸）
            total_upward = max(0, (3.45 - trial_time) * TIME_BOOST) + max(0, (0.25 - avg_st) * ST_BOOST)
            
            # 横移動（X軸）：外枠補正 + ST遅れによる外ドリフト
            base_cut_ratio = max(0, 0.08 - OUTSIDE_LINE_RATIO.get(car, 0.0))
            x_cut_handicap = total_upward * base_cut_ratio
            drift_dist = (avg_st - 0.25) * ST_BOOST * ST_DRIFT_RATIO if avg_st > 0.25 else 0
            
            final_x = base['x'] - x_cut_handicap + drift_dist
            final_y = base['y'] - total_upward
            
            calculated_positions.append({
                'car': car, 
                'x': int(max(30, final_x)), 
                'y': int(max(510, final_y))
            })

        if calculated_positions:
            img_path = visualizer.create_prediction_image(calculated_positions)
            visualizer.send_to_discord(img_path, webhook_url)
            return True
        return False
    except Exception as e:
        print(f"画像生成・送信エラー: {e}")
        return False

# ==========================================
# 4. 実行テスト
# ==========================================
if __name__ == "__main__":
    # 極端な数値を入れて「散らばり」をテスト
    df_test = pd.DataFrame([
        {'車': 1, '試走T': 3.42, '平均st': 0.15, 'ハンデ': 0},
        {'車': 2, '試走T': 3.41, '平均st': 0.18, 'ハンデ': 10},
        {'車': 5, '試走T': 3.37, '平均st': 0.35, 'ハンデ': 40}, # ST遅れ（右へ）
        {'車': 6, '試走T': 3.35, '平均st': 0.12, 'ハンデ': 50}, # ST速い（左へ）
        {'車': 8, '試走T': 3.31, '平均st': 0.26, 'ハンデ': 80}, # 捲り（外側キープ）
    ])

    print("--- 処理開始 ---")
    
    # 挨拶メッセージ
    send_discord_message("🔥 展開予想ロジック調整用テスト配信 🔥")
    
    # 画像送信
    if generate_and_send(df_test):
        print("Discordへの送信が成功しました。")
    else:
        print("送信に失敗しました。")
