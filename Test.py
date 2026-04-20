import os
import math
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定と定数定義
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# ターゲット（1〜2コーナー間のイン）
TARGET_X = 650
TARGET_Y = 265

# 芝生侵入禁止ライン
INNER_BOUNDARY_TOP = 140
INNER_BOUNDARY_BOTTOM = 390

# ハンデ位置
HANDE_CONFIG = {
    0:   {'x': 175, 'y': 400}, 10:  {'x': 120, 'y': 380}, 20:  {'x': 87,  'y': 354},
    30:  {'x': 65,  'y': 323}, 40:  {'x': 45,  'y': 285}, 50:  {'x': 35,  'y': 245},
    60:  {'x': 36,  'y': 202}, 70:  {'x': 48,  'y': 163}, 80:  {'x': 68,  'y': 125},
    90:  {'x': 93,  'y': 92},  100: {'x': 125, 'y': 66}
}

# ==========================================
# 2. シミュレーション（旋回制限モデル）
# ==========================================
def simulate_motion(df, steps=150, speed=6.0, omega_max=0.08):

    cars = []

    # 初期化
    for _, row in df.iterrows():
        handy = int(row['ハンデ'])
        config = HANDE_CONFIG[(handy // 10) * 10]

        cars.append({
            'car': int(row['車']),
            'x': float(config['x']),
            'y': float(config['y']),
            'theta': 0.0,
            'sy': float(config['y']),
            'arrived': False
        })

    for step in range(int(steps)):  # ★ int化
        frame = []

        for c in cars:
            if c['arrived']:
                frame.append({
                    'car': c['car'],
                    'x': int(c['x']),
                    'y': int(c['y'])
                })
                continue

            x, y, theta = c['x'], c['y'], c['theta']

            # =========================
            # 目標方向
            # =========================
            target_angle = math.atan2(TARGET_Y - y, TARGET_X - x)

            dtheta = target_angle - theta
            dtheta = (dtheta + math.pi) % (2 * math.pi) - math.pi

            # 旋回制限
            dtheta = max(-omega_max, min(omega_max, dtheta))
            theta += dtheta

            # =========================
            # 移動
            # =========================
            nx = x + speed * math.cos(theta)
            ny = y + speed * math.sin(theta)

            # =========================
            # 外に膨らまない制約
            # =========================
            if c['sy'] > 265:
                ny = min(ny, c['sy'])
            else:
                ny = max(ny, c['sy'])

            # =========================
            # 芝生侵入禁止（方向補正）
            # =========================
            if ny > INNER_BOUNDARY_BOTTOM:
                ny = INNER_BOUNDARY_BOTTOM
                theta = -abs(theta)

            if ny < INNER_BOUNDARY_TOP:
                ny = INNER_BOUNDARY_TOP
                theta = abs(theta)

            # =========================
            # 到達判定
            # =========================
            dist = math.hypot(TARGET_X - nx, TARGET_Y - ny)
            if dist < 8:
                c['arrived'] = True

            # 更新
            c['x'], c['y'], c['theta'] = nx, ny, theta

            # ★ int化（ここ重要）
            frame.append({
                'car': c['car'],
                'x': int(nx),
                'y': int(ny)
            })

        # =========================
        # 誰か1人でも到達した瞬間
        # =========================
        if any(c['arrived'] for c in cars):
            return frame

    return frame


# ==========================================
# 3. 実行
# ==========================================
def run_simulation_and_send(df):
    try:
        positions = simulate_motion(df)

        img_path = visualizer.create_prediction_image(positions)
        if img_path:
            visualizer.send_to_discord(img_path, WEBHOOK_URL)
            print("最初にイン到達した瞬間を送信しました")

    except Exception as e:
        print(f"エラー: {e}")


# ==========================================
# 4. テスト実行
# ==========================================
if __name__ == "__main__":
    handicaps = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    test_data = [{'車': (i % 8) + 1, 'ハンデ': h} for i, h in enumerate(handicaps)]

    df = pd.DataFrame(test_data)
    run_simulation_and_send(df)
