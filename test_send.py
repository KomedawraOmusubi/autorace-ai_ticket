import os
import visualizer

# --- 設定値 ---
# 数値が「小さい（速い）」ほど、上昇量（マイナス方向への移動）が大きくなります
TIME_BOOST = 2500  
ST_BOOST = 3500    

# 速い選手がどれだけ追加でイン（左）に切り込むか
# 上昇量 100px につき Xを 15px 左に寄せる設定
IN_CUT_RATIO = 0.15

def generate_and_send(df, webhook_url):
    """メインコードからDFを受け取って画像を送信するメイン関数"""
    try:
        # --- ハンデ戦用ベース（ご提示の計算式を反映） ---
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

        # --- オープン戦用ベース（ご提示のDEFAULT_LAYOUTを反映） ---
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
        car6_data = df[df['車'] == 6]
        is_open_race = False
        if not car6_data.empty:
            try:
                # 6号車が0mハンデならオープン戦
                if float(car6_data.iloc[0]['ハンデ']) == 0:
                    is_open_race = True
            except: pass
        
        current_layout = layout_open if is_open_race else layout_handicap
        mode_label = "オープン戦" if is_open_race else "ハンデ戦"
        
        calculated_positions = []
        for _, row in df.iterrows():
            car = int(row['車'])
            if car not in current_layout: continue
            
            base = current_layout[car]
            
            try:
                trial_time = float(row['試走T'])
                avg_st = float(row['平均st'])
            except:
                # 基準値を3.50 / 0.30とし、これより速い分だけ上昇させる
                trial_time, avg_st = 3.50, 0.30 

            # --- 上昇量（Y軸）の計算 ---
            # 3.50 / 0.30 を「上昇ゼロ」の基準点とする
            upward_dist_trial = max(0, (3.50 - trial_time) * TIME_BOOST)
            upward_dist_st = max(0, (0.30 - avg_st) * ST_BOOST)
            total_upward = upward_dist_trial + upward_dist_st
            
            # --- 横移動（X軸）の追加修正 ---
            # 上に上がるほど、左（イン）へ切り込む
            x_cut = total_upward * IN_CUT_RATIO
            
            final_y = base['y'] - total_upward
            final_x = base['x'] - x_cut
            
            # Xがコースアウトしないよう最低値をガード
            final_x = max(30, final_x)
            
            calculated_positions.append({
                'car': car,
                'x': int(final_x),
                'y': int(final_y)
            })

        # 画像生成
        img_path = visualizer.create_prediction_image(calculated_positions)
        # Discordへ送信
        visualizer.send_to_discord(img_path, webhook_url)
        print(f"展開予想図（{mode_label}）を送信しました。ご指定の初期値から速い車が左上に動きます。")
        return True
    except Exception as e:
        print(f"画像生成・送信エラー: {e}")
        return False

# 単体テスト用
if __name__ == "__main__":
    import pandas as pd
    test_df = pd.DataFrame([
        {'車': 1, 'ハンデ': 0, '試走T': 3.30, '平均st': 0.15},
        {'車': 8, 'ハンデ': 10, '試走T': 3.45, '平均st': 0.25},
    ])
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if url: generate_and_send(test_df, url)
