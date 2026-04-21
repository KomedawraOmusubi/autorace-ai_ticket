import os
import requests
from PIL import Image, ImageDraw

def create_prediction_image(positions_with_path, waypoints=None):
    base_path = 'assets/20260420-163135.jpg'
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"背景画像が見つかりません: {base_path}")
        
    base_img = Image.open(base_path).convert('RGBA')
    draw = ImageDraw.Draw(base_img)

    # オートレース公式車番色
    CAR_COLORS = {
        1: (255, 255, 255, 255), 2: (0, 0, 0, 255), 3: (255, 0, 0, 255),
        4: (0, 0, 255, 255), 5: (255, 255, 0, 255), 6: (0, 128, 0, 255),
        7: (255, 165, 0, 255), 8: (255, 105, 180, 255),
    }

    # 1. 基準の赤線（薄く）
    if waypoints:
        for i in range(len(waypoints) - 1):
            p1, p2 = waypoints[i], waypoints[i+1]
            draw.line([(p1['x'], p1['y']), (p2['x'], p2['y'])], fill=(255, 0, 0, 60), width=1)

    # 2. 各車の走行軌跡
    for item in positions_with_path:
        car_num = item['car']
        path = item['path']
        color = CAR_COLORS.get(car_num, (200, 200, 200, 255))
        if len(path) >= 2:
            draw.line(path, fill=color, width=2)

    # 3. 各車アイコン（最前面）
    for item in positions_with_path:
        car_num = item['car']
        x, y = item['last_pos']
        icon_path = f'assets/car_icons/{car_num}.png'
        if os.path.exists(icon_path):
            car_icon = Image.open(icon_path).convert('RGBA')
            icon_size = (10, 10)
            car_icon.thumbnail(icon_size, Image.Resampling.LANCZOS)
            paste_x, paste_y = int(x - icon_size[0]//2), int(y - icon_size[1]//2)
            base_img.paste(car_icon, (paste_x, paste_y), car_icon)

    output_path = 'prediction_output.png'
    base_img.save(output_path)
    return output_path

def send_to_discord(image_path, webhook_url):
    if not webhook_url: return
    with open(image_path, 'rb') as f:
        payload = {'content': '【物理走行ルート可視化：POINT_A絞り込みモデル】'}
        files = {'file': ('prediction.png', f, 'image/png')}
        requests.post(webhook_url, data=payload, files=files)
