import os
import visualizer

# --- 設定値（微調整用） ---
TIME_GRAVITY = 1000  # 試走0.01秒 = 10px
ST_GRAVITY = 2000    # ST 0.01秒 = 20px (STの重要度を高めに設定)

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

def calculate_positions(race_data):
    """
    race_data: [{'car': 1, 'time': 3.32, 'st': 0.12}, ...]
    """
    calculated = []
    for data in race_data:
        car = data['car']
        base = DEFAULT_LAYOUT[car]
        
        # 1. 試走タイムによる上下 (3.30基準)
        time_diff = (data['time'] - 3.30) * TIME_GRAVITY
        
        # 2. STによる上下 (0.15基準)
        # STが早い(0.12など)と、(0.12 - 0.15) * 2000 = -60px (上へ)
        st_offset = (data['st'] - 0.15) * ST_GRAVITY
        
        final_y = base['y'] + time_diff + st_offset
        
        calculated.append({
            'car': car,
            'x': base['x'],
            'y': int(final_y)
        })
    return calculated

# --- メイン処理 ---
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def main():
    # テストデータ（試走タイム と 平均ST を入力）
    test_race_data = [
        {'car': 1, 'time': 3.35, 'st': 0.18}, # 試走遅め・ST遅め = かなり下がる
        {'car': 2, 'time': 3.32, 'st': 0.11}, # STが早いので、1号車を飲み込む予想
        {'car': 3, 'time': 3.30, 'st': 0.15},
        {'car': 4, 'time': 3.30, 'st': 0.15},
        {'car': 5, 'time': 3.30, 'st': 0.15},
        {'car': 6, 'time': 3.30, 'st': 0.15},
        {'car': 7, 'time': 3.30, 'st': 0.15},
        {'car': 8, 'time': 3.28, 'st': 0.12}, # 試走もSTも最強 = 圧倒的な追い上げ
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
