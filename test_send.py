import os
import visualizer

# --- 設定値（微調整用） ---
TIME_GRAVITY = 1000  # 試走0.01秒 = 10px
ST_GRAVITY = 2000    # ST 0.01秒 = 20px

# 初期値ハンデ戦（コメントアウトで保持）
"""
test_positions = [
    {'car': 1, 'x': 230,             'y': 400}, # そのまま
    {'car': 2, 'x': 260 - 90,        'y': 520}, # 1個左へ
    {'car': 3, 'x': 300 - 90,        'y': 600}, # 1個左へ
    {'car': 4, 'x': 310 - (30 * 6),  'y': 680}, # 2個左へ
    {'car': 5, 'x': 340 - (30 * 6),  'y': 770}, # 2個左へ
    {'car': 6, 'x': 380 - (30 * 6),  'y': 860}, # 2個左へ
    {'car': 7, 'x': 380 - (30 * 9),  'y': 930}, # 3個左へ
    {'car': 8, 'x': 420 - (30 * 9),  'y': 1010}, # 3個左へ
]
"""

# 計算の基準となるレイアウト
DEFAULT_LAYOUT = {
    1: {'x': 230,            'y': 400},
    2: {'x': 260 - 90,       'y': 520},
    3: {'x': 300 - 90,       'y': 600},
    4: {'x': 310 - (30 * 6), 'y': 680},
    5: {'x': 340 - (30 * 6), 'y': 770},
    6: {'x': 380 - (30 * 6), 'y': 860},
    7: {'x': 380 - (30 * 9), 'y': 930},
    8: {'x': 420 - (30 * 9), 'y': 1010},
}

def generate_and_send(df, webhook_url):
    """メインコードからDFを受け取って画像を送信するメイン関数"""
    try:
        calculated_positions = []
        for _, row in df.iterrows():
            car = int(row['車'])
            if car not in DEFAULT_LAYOUT: continue
            
            base = DEFAULT_LAYOUT[car]
            
            # 数値変換 (エラー時は基準値を使用)
            try:
                trial_time = float(row['試走T'])
                avg_st = float(row['平均st'])
            except (ValueError, TypeError):
                trial_time = 3.30
                avg_st = 0.15

            # 試走タイムによる上下 (3.30基準)
            time_diff = (trial_time - 3.30) * TIME_GRAVITY
            # STによる上下 (0.15基準)
            st_offset = (avg_st - 0.15) * ST_GRAVITY
            
            final_y = base['y'] + time_diff + st_offset
            
            calculated_positions.append({
                'car': car,
                'x': base['x'],
                'y': int(final_y)
            })

        # 画像生成
        img_path = visualizer.create_prediction_image(calculated_positions)
        # Discordへ送信
        visualizer.send_to_discord(img_path, webhook_url)
        print("展開予想図の送信に成功しました。")
        return True
    except Exception as e:
        print(f"画像生成・送信エラー: {e}")
        return False

# 単体テスト用
if __name__ == "__main__":
    import pandas as pd
    # テスト用のダミーデータ
    test_df = pd.DataFrame([
        {'車': 1, '試走T': 3.35, '平均st': 0.18},
        {'車': 8, '試走T': 3.28, '平均st': 0.12},
    ])
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    generate_and_send(test_df, url)
