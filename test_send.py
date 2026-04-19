import os
import visualizer

# --- 設定値（動きをさらにマイルドに：1px単位の微調整） ---
TIME_BOOST = 800   # 試走0.01秒 = 8px上昇
ST_BOOST = 1000    # ST 0.01秒 = 10px上昇
IN_CUT_RATIO = 0.08 # インへの切り込みもさらに抑えめ

def generate_and_send(df, webhook_url):
    """メインコードからDFを受け取って画像を送信するメイン関数"""
    try:
        # ハンデ戦用ベース
        layout_handicap = {
            1: {'x': 230,            'y': 480},
            2: {'x': 260 - 90,       'y': 520},
            3: {'x': 300 - 90,       'y': 600},
            4: {'x': 310 - (30 * 6), 'y': 680},
            5: {'x': 340 - (30 * 6), 'y': 770},
            6: {'x': 380 - (30 * 6), 'y': 860},
            7: {'x': 380 - (30 * 9), 'y': 930},
            8: {'x': 420 - (30 * 9), 'y': 1010},
        }

        # オープン戦用ベース
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

        # レイアウト判定
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
            
            # 1. まずレイアウトに車番があるか確認
            if car not in current_layout:
                continue
            
            # 2. baseを定義（エラー回避のため、試走チェックより先に定義）
            base = current_layout[car]
            
            # 3. 試走データのチェック（空・欠車・異常値を除外）
            trial_val = str(row.get('試走T', '')).strip()
            if trial_val in ["", "-", "nan", "欠車", "None", "."]:
                print(f"{car}号車は試走データがないため除外します")
                continue

            try:
                trial_time = float(trial_val)
                # 平均STが空の場合は0.25（動かない基準）を入れる
                st_val = str(row.get('平均st', '')).strip()
                avg_st = float(st_val) if st_val not in ["", "-", "nan"] else 0.25
                
                if trial_time <= 0: continue
            except (ValueError, TypeError):
                continue

            # --- 上昇量（Y軸）の計算 ---
            # 基準値より速い（数値が小さい）分だけ上昇。遅ければ0。
            upward_dist_trial = max(0, (3.45 - trial_time) * TIME_BOOST)
            upward_dist_st = max(0, (0.25 - avg_st) * ST_BOOST)
            total_upward = upward_dist_trial + upward_dist_st
            
            # --- 横移動（X軸）の修正 ---
            x_cut = total_upward * IN_CUT_RATIO
            
            final_y = base['y'] - total_upward
            final_x = base['x'] - x_cut
            
            # 制限：1号車のライン(y=480)より前には出ない
            final_y = max(480, final_y)
            # コース左端ガード
            final_x = max(30, final_x)
            
            calculated_positions.append({
                'car': car,
                'x': int(final_x),
                'y': int(final_y)
            })

        if calculated_positions:
            img_path = visualizer.create_prediction_image(calculated_positions)
            visualizer.send_to_discord(img_path, webhook_url)
            print("展開予想図を送信しました。")
            return True
        return False
    except Exception as e:
        print(f"画像生成・送信エラー: {e}")
        import traceback
        traceback.print_exc() # 詳細なエラー箇所を出力
        return False
