import os
import visualizer

# --- 設定値（微調整用） ---
# 試走タイム 0.01秒の差を何ピクセル上下させるか
TIME_GRAVITY = 1000  # 0.01秒 = 10px

# 初期配置（あなたが決めた座標をベースに、ここを「基準」とします）
# ここには「ハンデ0m・試走3.30」だった場合の理想の位置を入れます
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

def calculate_positions(race_data):
    """
    race_data: [{'car': 1, 'time': 3.32, 'handicap': 0}, ...]
    """
    calculated = []
    for data in race_data:
        car = data['car']
        base = DEFAULT_LAYOUT[car]
        
        # 1. 試走タイムによる上下 (3.30を基準とする)
        # 3.29なら上(-10px)、3.31なら下(+10px)
        time_diff = (data['time'] - 3.30) * TIME_GRAVITY
        
        # 2. ハンデによる上下 (10mにつき30px下げると仮定)
        # ※初期配置にすでにハンデ分が含まれているならここは 0 でOK
        handi_offset = (data['handicap'] / 10) * 0 
        
        final_y = base['y'] + time_diff + handi_offset
        
        calculated.append({
            'car': car,
            'x': base['x'],
            'y': int(final_y)
        })
    return calculated

# --- メイン処理 ---
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def main():
    # テストデータ（ここを変えて試せます）
    test_race_data = [
        {'car': 1, 'time': 3.35, 'handicap': 0},  # 試走が少し遅いので y400より下がる
        {'car': 2, 'time': 3.30, 'handicap': 10},
        {'car': 3, 'time': 3.30, 'handicap': 20},
        {'car': 4, 'time': 3.30, 'handicap': 30},
        {'car': 5, 'time': 3.30, 'handicap': 40},
        {'car': 6, 'time': 3.30, 'handicap': 50},
        {'car': 7, 'time': 3.30, 'handicap': 60},
        {'car': 8, 'time': 3.25, 'handicap': 70}, # 爆速試走なので y1010より上に上がる
    ]

    try:
        positions = calculate_positions(test_race_data)
        print("画像生成中...")
        img_path = visualizer.create_prediction_image(positions)
        
        print("Discord送信中...")
        visualizer.send_to_discord(img_path, WEBHOOK_URL)
        print("送信完了しました！")
    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    main()
