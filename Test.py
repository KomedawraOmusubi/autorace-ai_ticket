import os
import pandas as pd
import visualizer 

# Webhook URLの設定
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# --- 設定データ ---

# ハンデごとのスタート座標（110mを追加）
HANDE_CONFIG = {
    0:   {'x': 175, 'y': 400}, 10:  {'x': 120, 'y': 380}, 20:  {'x': 87,  'y': 354},
    30:  {'x': 65,  'y': 323}, 40:  {'x': 45,  'y': 285}, 50:  {'x': 35,  'y': 245},
    60:  {'x': 36,  'y': 202}, 70:  {'x': 48,  'y': 163}, 80:  {'x': 68,  'y': 125},
    90:  {'x': 93,  'y': 92}, 100: {'x': 125, 'y': 66}, 110: {'x': 140, 'y': 45}
}

# ハンデごとの第1合流点(点A)
CUSTOM_A_POINTS = {
    0:   {'x': 175, 'y': 400}, 10:  {'x': 175, 'y': 390}, 20:  {'x': 175, 'y': 390},
    30:  {'x': 175, 'y': 380}, 40:  {'x': 175, 'y': 370}, 50:  {'x': 175, 'y': 370},
    60:  {'x': 175, 'y': 370}, 70:  {'x': 175, 'y': 370}, 80:  {'x': 175, 'y': 370},
    90:  {'x': 175, 'y': 370}, 100: {'x': 175, 'y': 370}, 110: {'x': 175, 'y': 370}
}

# 走行不可境界線（visualizer側で黒の点線として描画される）
OUTER_LINE = [(175, 400), (465, 395), (500, 395), (525, 395), (565, 370), (595, 335), (620, 220)]
INNER_LINE = [(175, 350), (465, 355), (500, 350), (525, 340), (570, 310), (580, 300), (605 , 210)]

# コーナー以降の基準目標地点
WAYPOINTS_AFTER_A = [
    {'name': 'B',   'pos': {'x': 455, 'y': 395}},
    {'name': 'B_1', 'pos': {'x': 550, 'y': 360}},
    {'name': 'B_2', 'pos': {'x': 570, 'y': 350}},
    {'name': 'B_3', 'pos': {'x': 590, 'y': 310}},
    {'name': 'C',   'pos': {'x': 600, 'y': 250}}
]

def calculate_rail_positions(df):
    """
    各車両の走行軌跡を計算する。
    走行ラインはINNER_LINEとOUTER_LINEの間を走るようにオフセットを調整。
    """
    df = df.sort_values(['車'])
    final_results = []

    for _, row in df.iterrows():
        car = int(row['車'])
        handy = int(row.get('ハンデ', 0))
        
        # ハンデキーの特定 (0-110)
        handy_key = min(max(0, (handy // 10) * 10), 110)
        
        # 1. スタート地点の追加
        start_pos = HANDE_CONFIG.get(handy_key, HANDE_CONFIG[0])
        history = [(start_pos['x'], start_pos['y'])]
        
        # 2. 合流点Aの追加
        history.append((CUSTOM_A_POINTS[handy_key]['x'], CUSTOM_A_POINTS[handy_key]['y']))

        # 3. 走行ラインのオフセット計算
        # ハンデが重いほど内側を走る（base）、車番順に重なりを避ける（spread）
        # ※ラインをはみ出さないよう係数を微調整
        base_handy_offset = -(handy / 10) * 3.5 
        spread_offset = -3 + (car - 1) * (6 / 7)
        total_offset = base_handy_offset + spread_offset

        # 4. 各目標地点の計算
        for wp in WAYPOINTS_AFTER_A:
            # 1号車は常にインコース（INNER_LINE付近）を狙う独自処理
            if car == 1:
                if wp['name'] == 'B': 
                    history.append((wp['pos']['x'], 380)) # INNER_LINE(355)とOUTER(395)の間
                    continue
                if wp['name'] == 'B_1': 
                    history.append((wp['pos']['x'], 340)) # INNER_LINE(310)付近
                    continue
            
            # 基準座標にオフセットを適用
            target_y = wp['pos']['y'] + total_offset
            history.append((wp['pos']['x'], target_y))
        
        # 可視化用にハンデ情報を渡して格納
        final_results.append({
            'car': car, 
            'handy': handy,
            'path': history
        })
    return final_results

def run_simulation(df):
    """
    シミュレーションを実行し、画像を生成してDiscordへ送信する。
    """
    # 走行ルート計算
    results = calculate_rail_positions(df)
    
    # 画像生成（内部で黒点線・ハンデ別色分け処理が行われる）
    img_path = visualizer.create_prediction_image(
        results, 
        outer_line=OUTER_LINE, 
        inner_line=INNER_LINE
    )
    
    # Discord送信
    if img_path:
        visualizer.send_to_discord(img_path, WEBHOOK_URL)

if __name__ == "__main__":
    # テスト走行データ: 1〜8号車が異なるハンデ（0m〜110mを含む）で出走
    # 0, 10, 20, 30, 40, 50, 60, 110 のような構成
    test_data = [
        {'車': 1, 'ハンデ': 0},
        {'車': 2, 'ハンデ': 10},
        {'車': 3, 'ハンデ': 20},
        {'車': 4, 'ハンデ': 30},
        {'車': 5, 'ハンデ': 40},
        {'車': 6, 'ハンデ': 50},
        {'車': 7, 'ハンデ': 80},
        {'車': 8, 'ハンデ': 110}
    ]
    run_simulation(pd.DataFrame(test_data))
