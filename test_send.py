import os
import visualizer

# --- 新・設定値（散らばり重視に調整） ---
# 縦の速さを表現するブースト値
TIME_BOOST = 350   # 試走タイムによる上昇（少し強めて縦の差を出す）
ST_BOOST = 500     # STによる上昇（横移動にも影響させる）

# --- 横方向の散らばり設定（重要） ---
# 1号車を基準(0)とし、外枠に行くほどインに切り込みにくくする「補正値」
OUTSIDE_LINE_RATIO = {
    1: 0.0,   # 完全インベタ
    2: 0.0, 
    3: 0.0,
    4: 0.01,  
    5: 0.02,  # 5号車から少し外を回り始める
    6: 0.03,  
    7: 0.05,  # 7号車は大外
    8: 0.06   # 8号車は大外
}

# ST（平均st）の悪さが「外への流れ」になる比率
# 平均stが遅い（数値が大きい）ほど、ST_BOOSTをこの比率で掛けて右へ移動させる
ST_DRIFT_RATIO = 0.03  # 0.25より遅ければ外へ逃げる

def generate_and_send(df, webhook_url):
    """メインコードからDFを受け取って画像を送信するメイン関数"""
    try:
        # --- ハンデ戦用ベース（初期x坐标を少し離して配置） ---
        layout_handicap = {
            1: {'x': 230, 'y': 380}, # イン
            2: {'x': 180, 'y': 520},
            3: {'x': 210, 'y': 540},
            4: {'x': 150, 'y': 720}, # 少し外へ
            5: {'x': 170, 'y': 740}, 
            6: {'x': 200, 'y': 760},
            7: {'x': 130, 'y': 880}, # 外
            8: {'x': 160, 'y': 900}, # 外
        }

        # --- オープン戦用ベース（初期x坐标を離して配置） ---
        layout_open = {
            1: {'x': 70,  'y': 480},
            2: {'x': 90,  'y': 570},
            3: {'x': 110, 'y': 650},
            4: {'x': 130, 'y': 730},
            5: {'x': 150, 'y': 810},
            6: {'x': 170, 'y': 890},
            7: {'x': 190, 'y': 970},
            8: {'x': 210, 'y': 1050},
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
            
            # データチェック
            trial_val = str(row.get('試走T', '')).strip()
            if trial_val in ["", "-", "nan", "欠車"]: continue

            try:
                trial_time = float(trial_val)
                st_val = str(row.get('平均st', '')).strip()
                avg_st = float(st_val) if st_val not in ["", "-", "nan"] else 0.25
                if trial_time <= 0: continue
            except: continue

            # --- 上昇量（Y軸）の計算 ---
            upward_dist_trial = max(0, (3.45 - trial_time) * TIME_BOOST)
            upward_dist_st = max(0, (0.25 - avg_st) * ST_BOOST)
            total_upward = upward_dist_trial + upward_dist_st
            
            # --- 横移動（X軸）の計算（新ロジック） ---
            
            # 1. ハディによる切り込み補正（外枠ほどインへ切り込まない）
            # 外枠ほど OUTSIDE_LINE_RATIO が大きいため、x_cut（インへの移动量）が小さくなる
            base_cut_ratio = max(0, 0.08 - OUTSIDE_LINE_RATIO.get(car, 0.0))
            x_cut_handicap = total_upward * base_cut_ratio
            
            # 2. STの遅さによる「外へのドリフト」
            # 平均stが0.25より遅い（数値が大きい）ほど、右へドリフトさせる
            if avg_st > 0.25:
                drift_dist = (avg_st - 0.25) * ST_BOOST * ST_DRIFT_RATIO
            else:
                drift_dist = 0
            
            # インへの切り込み量(x_cut)からドリフト量を引いて、最終的なX座標を決定
            # ドリフトが大きいとx座標が増える（右にずれる）
            final_x = base['x'] - x_cut_handicap + drift_dist
            
            final_y = base['y'] - total_upward
            
            # 制限
            final_y = max(510, final_y)
            final_x = max(30, final_x)
            
            calculated_positions.append({
                'car': car,
                'x': int(final_x),
                'y': int(final_y)
            })

        if calculated_positions:
            img_path = visualizer.create_prediction_image(calculated_positions)
            visualizer.send_to_discord(img_path, webhook_url)
            print(f"展開予想図（新・散らばり設定）を送信しました。")
            return True
        return False

    except Exception as e:
        print(f"画像生成・送信エラー: {e}")
        import traceback
        traceback.print_exc()
        return False
