import os
import pandas as pd
import visualizer

# ==========================================
# 1. 設定値（散らばり重視ロジック）
# ==========================================
TIME_BOOST = 350   # 試走タイムによる上昇
ST_BOOST = 500     # STによる上昇

# 車番ごとの外回り補正（外枠ほどインに切り込みにくくする）
OUTSIDE_LINE_RATIO = {
    1: 0.0, 2: 0.0, 3: 0.0,
    4: 0.01, 5: 0.02, 6: 0.03, 
    7: 0.05, 8: 0.06
}

# 平均stが0.25より遅い場合に外へ流れる比率
ST_DRIFT_RATIO = 0.03 

# ==========================================
# 2. メインロジック関数
# ==========================================
def generate_and_send(df, webhook_url):
    try:
        # ハンデ戦用ベース座標（初期位置を散らして配置）
        layout_handicap = {
            1: {'x': 230, 'y': 380},
            2: {'x': 180, 'y': 520},
            3: {'x': 210, 'y': 540},
            4: {'x': 150, 'y': 720},
            5: {'x': 170, 'y': 740}, 
            6: {'x': 200, 'y': 760},
            7: {'x': 130, 'y': 880},
            8: {'x': 160, 'y': 900},
        }

        layout_open = {
            1: {'x': 70,  'y': 480}, 2: {'x': 90,  'y': 570},
            3: {'x': 110, 'y': 650}, 4: {'x': 130, 'y': 730},
            5: {'x': 150, 'y': 810}, 6: {'x': 170, 'y': 890},
            7: {'x': 190, 'y': 970}, 8: {'x': 210, 'y': 1050},
        }

        # オープン戦判定
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
            
            # 描画制限
            final_y = max(510, final_y)
            final_x = max(30, final_x)
            
            calculated_positions.append({'car': car, 'x': int(final_x), 'y': int(final_y)})

        if calculated_positions:
            img_path = visualizer.create_prediction_image(calculated_positions)
            visualizer.send_to_discord(img_path, webhook_url)
            return True
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

# ==========================================
# 3. テスト実行（SecretsからURL取得）
# ==========================================
if __name__ == "__main__":
    # テスト用データ（散らばりを確認するための極端な数値）
    test_data = [
        {'車': 1, '試走T': 3.42, '平均st': 0.15, 'ハンデ': 0},
        {'車': 2, '試走T': 3.41, '平均st': 0.18, 'ハンデ': 10},
        {'車': 3, '試走T': 3.40, '平均st': 0.20, 'ハンデ': 20},
        {'車': 4, '試走T': 3.39, '平均st': 0.22, 'ハンデ': 30},
        {'車': 5, '試走T': 3.37, '平均st': 0.30, 'ハンデ': 40}, # ST遅いので外へ流れる
        {'車': 6, '試走T': 3.35, '平均st': 0.12, 'ハンデ': 50}, # ST速いのでインへ
        {'車': 7, '試走T': 3.33, '平均st': 0.25, 'ハンデ': 60}, # 大外を走る
        {'車': 8, '試走T': 3.32, '平均st': 0.26, 'ハンデ': 80}, # 最速だけど大外
    ]
    df_test = pd.DataFrame(test_data)

    # シークレットから取得
    webhook_url = os.environ.get('WEBHOOK_URL')

    if webhook_url:
        print("Webhook URLを取得しました。送信します...")
        if generate_and_send(df_test, webhook_url):
            print("成功！Discordを確認してください。")
        else:
            print("送信に失敗しました。")
    else:
        print("エラー: Secretsに 'WEBHOOK_URL' が設定されていません。")
