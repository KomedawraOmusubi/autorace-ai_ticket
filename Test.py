import os
import math
import pandas as pd
import visualizer

# ==========================================
# 1. 環境設定
# ==========================================
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or "YOUR_WEBHOOK_URL_HERE"

# ターゲット（イン）
TARGET_X = 650
TARGET_Y = 265

# コーナー（円として扱う）
CORNER_CENTER_X = 650
CORNER_CENTER_Y = 265
CORNER_RADIUS_INNER = 125   # 芝生外周
CORNER_RADIUS_OUTER = 200   # 外側壁

# ハンデ位置
HANDE_CONFIG = {
    0:   {'x': 175, 'y': 400}, 10:  {'x': 120, 'y': 380}, 20:  {'x': 87,  'y': 354},
    30:  {'x': 65,  'y': 323}, 40:  {'x': 45,  'y': 285}, 50:  {'x': 35,  'y': 245},
    60:  {'x': 36,  'y': 202}, 70:  {'x': 48,  'y': 163}, 80:  {'x': 68,  'y': 125},
    90:  {'x': 93,  'y': 92},  100: {'x': 125, 'y': 66}
}

# ==========================================
# 2. 円拘束関数（これが核心）
# ==========================================
def project_to_corner(nx, ny):
    dx = nx - CORNER_CENTER_X
    dy = ny - CORNER_CENTER_Y
    r = math.hypot(dx, dy)

    # 半径制限
    if r < CORNER_RADIUS_INNER:
        r = CORNER_RADIUS_INNER
    if r > CORNER_RADIUS_OUTER:
        r = CORNER_RADIUS_OUTER

    angle = math.atan2(dy, dx)

    nx = CORNER_CENTER_X + r * math.cos(angle)
    ny = CORNER_CENTER_Y + r * math.sin(angle)

    return nx, ny


# ==========================================
# 3. シミュレーション
# ==========================================
def simulate_motion(df, steps=150, speed=6.0, omega_max=0.08):

    cars = []

    for _, row in df.iterrows():
        handy = int(row['ハンデ'])
        config = HANDE_CONFIG[(handy // 10) * 10]

        cars.append({
            'car': int(row['車']),
            'x': float(config['x']),
            'y': float(config['y']),
            'theta': 0.0,
            'arrived': False
        })

    for step in range(int(steps)):
        frame = []

        for c in cars:
            x, y, theta = c['x'], c['y'], c['theta']

            if c['arrived']:
                frame.append({
                    'car': c['car'],
                    'x': int(x),
                    'y': int(y)
                })
                continue

            # =========================
            # 目標方向
            # =========================
            target_angle = math.atan2(TARGET_Y - y, TARGET_X - x)

            dtheta = target_angle - theta
            dtheta = (dtheta + math.pi) % (2 * math.pi) - math.pi
            dtheta = max(-omega_max, min(omega_max, dtheta))
            theta += dtheta

            # =========================
            # 移動
            # =========================
            nx = x + speed * math.cos(theta)
            ny = y + speed * math.sin(theta)

            # =========================
            # コーナー拘束（超重要）
            # =========================
            if nx < CORNER_CENTER_X:
                nx, ny = project_to_corner(nx, ny)

            # =========================
            # 到達判定
            # =========================
            if math.hypot(TARGET_X - nx, TARGET_Y - ny) < 8:
                c['arrived'] = True

            c['x'], c['y'], c['theta'] = nx, ny, theta

            frame.append({
                'car': c['car'],
                'x': int(nx),
                'y': int(ny)
            })

        # =========================
        # 誰か到達した瞬間で止める
        # =========================
        if any(c['arrived'] for c in cars):
            return frame

    return frame


# ==========================================
# 4. 実行
# ==========================================
def run_simulation_and_send(df):
    try:
        positions = simulate_motion(df)

        img_path = visualizer.create_prediction_image(positions)
        if img_path:
            visualizer.send_to_discord(img_path, WEBHOOK_URL)
            print("円拘束で芝生侵入なし送信完了")

    except Exception as e:
        print(f"エラー: {e}")


# ==========================================
# 5. テスト
# ==========================================
if __name__ == "__main__":
    handicaps = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    test_data = [{'車': (i % 8) + 1, 'ハンデ': h} for i, h in enumerate(handicaps)]

    df = pd.DataFrame(test_data)
    run_simulation_and_send(df)
