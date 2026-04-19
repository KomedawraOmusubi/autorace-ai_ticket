import os
import visualizer

# --- 設定値（微調整用） ---
# 1000→400, 2000→800 などに落とすと、車番が重なりすぎずスッキリします
TIME_GRAVITY = 500  # 試走0.01秒 = 5px
ST_GRAVITY = 1000    # ST 0.01秒 = 10px

def generate_and_send(df, webhook_url):
    """メインコードからDFを受け取って画像を送信するメイン関数"""
    try:
        # --- ハンデ戦用レイアウト（画像1枚目：斜めに並ぶ） ---
        layout_handicap = {
            1: {'x': 230,            'y': 400},
            2: {'x': 260 - 90,       'y': 520},
            3: {'x': 300 - 90,       'y': 600},
            4: {'x': 310 - (30 * 6), 'y': 680},
            5: {'x': 340 - (30 * 6), 'y': 770},
            6: {'x': 380 - (30 * 6), 'y': 860},
            7: {'x': 380 - (30 * 9), 'y': 930},
            8: {'x': 420 - (30 * 9), 'y': 1010},
        }

        # --- オープン戦用レイアウト（画像2枚目：左下に縦1列） ---
        layout_open = {
            1: {'x': 70, 'y': 490},
            2: {'x': 65, 'y': 570},
            3: {'x': 60, 'y': 650},
            4: {'x': 55, 'y': 730},
            5: {'x': 50, 'y': 810},
            6: {'x': 45, 'y': 890},
            7: {'x': 40, 'y': 970},
            8: {'x': 35, 'y': 1050},
        }

        # --- レイアウト判定ロジック ---
        # 6号車のハンデを確認（6号車が0mならオープン戦とみなす）
        car6_data = df[df['車'] == 6]
        is_open_race = False
        
        if not car6_data.empty:
            try:
                handicap_6 = float(car6_data.iloc[0]['ハンデ'])
                if handicap_6 == 0:
                    is_open_race = True
            except (ValueError, TypeError):
                pass
        
        current_layout = layout_open if is_open_race else layout_handicap
        mode_label = "オープン戦" if is_open_race else "ハンデ戦"
        print(f"判定: {mode_label}レイアウトを適用します")

        calculated_positions = []
        for _, row in df.iterrows():
            car = int(row['車'])
            if car not in current_layout: continue
            
            base = current_layout[car]
            
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
        print(f"展開予想図（{mode_label}）の送信に成功しました。")
        return True
    except Exception as e:
        print(f"画像生成・送信エラー: {e}")
        return False

# 単体テスト用
if __name__ == "__main__":
    import pandas as pd
    # テスト用のダミーデータ（CSVから読み込む想定）
    test_df = pd.DataFrame([
        {'車': 1, 'ハンデ': 0, '試走T': 3.35, '平均st': 0.15},
        {'車': 6, 'ハンデ': 0, '試走T': 3.30, '平均st': 0.15}, # ここを10にするとハンデ戦レイアウト
        {'車': 8, 'ハンデ': 0, '試走T': 3.28, '平均st': 0.15},
    ])
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if url:
        generate_and_send(test_df, url)
    else:
        print("Webhook URLが設定されていません。")
