import os
import visualizer

# --- 設定値（微調整用） ---
TIME_GRAVITY = 1000  # 試走0.01秒 = 10px
ST_GRAVITY = 2000    # ST 0.01秒 = 20px

# 【オープン戦用レイアウト】左下に縦1列で並ぶ設定
# x: 左端からの距離 / y: 上からの距離（1000から80px刻みで配置）
DEFAULT_LAYOUT = {
    1: {'x': 70, 'y': 490},
    2: {'x': 65, 'y': 570},
    3: {'x': 60, 'y': 650},
    4: {'x': 55, 'y': 730},
    5: {'x': 50, 'y': 810},
    6: {'x': 45, 'y': 890},
    7: {'x': 40, 'y': 970},
    8: {'x': 35, 'y': 1050},
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
                # CSV内のカラム名が「試走T」「平均st」であることを前提
                trial_time = float(row['試走T']) if '試走T' in row else 3.30
                avg_st = float(row['平均st']) if '平均st' in row else 0.15
            except (ValueError, TypeError):
                trial_time = 3.30
                avg_st = 0.15

            # 試走タイムによる上下 (3.30基準)
            time_diff = (trial_time - 3.30) * TIME_GRAVITY
            # STによる上下 (0.15基準)
            st_offset = (avg_st - 0.15) * ST_GRAVITY
            
            # 初期配置（y）に対して変動分を合算
            final_y = base['y'] + time_diff + st_offset
            
            calculated_positions.append({
                'car': car,
                'x': base['x'],
                'y': int(final_y)
            })

        # 画像生成 (visualizer.pyを呼び出し)
        img_path = visualizer.create_prediction_image(calculated_positions)
        # Discordへ送信
        visualizer.send_to_discord(img_path, webhook_url)
        print("オープン戦用初期配置での画像送信に成功しました。")
        return True
    except Exception as e:
        print(f"画像生成・送信エラー: {e}")
        return False

# --- 手動実行テスト用 ---
if __name__ == "__main__":
    import pandas as pd
    
    # 試走・STが基準値(3.30 / 0.15)の場合、DEFAULT_LAYOUT通りの位置に出力されます
    test_df = pd.DataFrame([
        {'車': 1, '試走T': 3.30, '平均st': 0.15},
        {'車': 2, '試走T': 3.30, '平均st': 0.15},
        {'車': 3, '試走T': 3.30, '平均st': 0.15},
        {'車': 4, '試走T': 3.30, '平均st': 0.15},
        {'車': 5, '試走T': 3.30, '平均st': 0.15},
        {'車': 6, '試走T': 3.30, '平均st': 0.15},
        {'車': 7, '試走T': 3.30, '平均st': 0.15},
        {'車': 8, '試走T': 3.30, '平均st': 0.15},
    ])
    
    # 環境変数からURL取得（設定されていない場合は直接URLを書き換えてテストしてください）
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if url:
        generate_and_send(test_df, url)
    else:
        print("エラー: DiscordのWebhook URLが環境変数に設定されていません。")
