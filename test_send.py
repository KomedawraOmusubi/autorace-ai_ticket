import os
import visualizer

# --- 設定値（動きをマイルドに調整） ---
TIME_BOOST = 300   # 試走タイムによる上昇幅
ST_BOOST = 400     # STによる上昇幅
IN_CUT_RATIO = 0.02 # 外枠勢（5-8号車）のみに適用する切り込み比率

def generate_and_send(df, webhook_url):
    """メインコードからDFを受け取って画像を送信するメイン関数"""
    try:
        # --- ハンデ戦用ベース ---
        # 1-4号車はイン側、5-8号車は少し外側に初期配置
        layout_handicap = {
            1: {'x': 230, 'y': 380},
            2: {'x': 190, 'y': 520},
            3: {'x': 230, 'y': 540},
            4: {'x': 150, 'y': 720},
            5: {'x': 180, 'y': 740},
            6: {'x': 210, 'y': 760},
            7: {'x': 130, 'y': 880},
            8: {'x': 170, 'y': 900},
        }

        # --- オープン戦用ベース ---
        layout_open = {
            1: {'x': 70, 'y': 480},
            2: {'x': 65, 'y': 570},
            3: {'x': 60, 'y': 650},
            4: {'x': 55, 'y': 730},
            5: {'x': 50, 'y': 810},
            6: {'x': 45, 'y': 890},
            7: {'x': 40, 'y': 970},
            8: {'x': 35, 'y': 1050},
        }

        # レイアウト判定（6号車のハンデが0ならオープン戦とみなす）
        car6_data = df[df['車'] == 6]
        is_open_race = False
        if not car6_data.empty:
            try:
                if float(car6_data.iloc[0]['ハンデ']) == 0:
                    is_open_race = True
            except:
                pass
        
        current_layout = layout_open if is_open_race else layout_handicap
        calculated_positions = []

        for _, row in df.iterrows():
            car = int(row['車'])
            if car not in current_layout:
                continue
            
            base = current_layout[car]
            
            # 試走データのチェック（空・欠車・異常値を除外）
            trial_val = str(row.get('試走T', '')).strip()
            if trial_val in ["", "-", "nan", "欠車", "None", "."]:
                print(f"{car}号車は試走データがないため除外します")
                continue

            try:
                trial_time = float(trial_val)
                st_val = str(row.get('平均st', '')).strip()
                # STデータがない場合は平均的な0.25を代入
                avg_st = float(st_val) if st_val not in ["", "-", "nan"] else 0.25
                if trial_time <= 0: continue
            except (ValueError, TypeError):
                continue

            # --- 上昇量（Y軸）の計算 ---
            upward_dist_trial = max(0, (3.45 - trial_time) * TIME_BOOST)
            upward_dist_st = max(0, (0.25 - avg_st) * ST_BOOST)
            total_upward = upward_dist_trial + upward_dist_st
            
            # --- 横移動（X軸）の判定 ---
            # 5, 6, 7, 8号車だけ切り込みを適用し、1-4号車は真っ直ぐ進ませる
            if car >= 5:
                x_cut = total_upward * IN_CUT_RATIO
            else:
                x_cut = 0
            
            final_y = base['y'] - total_upward
            final_x = base['x'] - x_cut
            
            # 画面外に出ないための制限
            final_y = max(510, final_y)
            final_x = max(30, final_x)
            
            calculated_positions.append({
                'car': car,
                'x': int(final_x),
                'y': int(final_y)
            })

        if calculated_positions:
            # 算出した座標を元に画像を生成
            img_path = visualizer.create_prediction_image(calculated_positions)
            # Discord等へ送信
            visualizer.send_to_discord(img_path, webhook_url)
            print(f"展開予想図（外枠切り込み設定）を送信しました。")
            return True
        return False

    except Exception as e:
        print(f"画像生成・送信エラー: {e}")
        import traceback
        traceback.print_exc()
        return False
