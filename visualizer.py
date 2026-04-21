import os
import requests
from PIL import Image, ImageDraw

def create_prediction_image(positions_with_path, waypoints=None, outer_line=None, inner_line=None):
    base_path = 'assets/20260420-163135.jpg'
    if not os.path.exists(base_path):
        # 背景がない場合にエラーで落ちないよう、デバッグ用に新規画像作成
        base_img = Image.new('RGBA', (800, 500), (50, 50, 50, 255))
    else:
        base_img = Image.open(base_path).convert('RGBA')
    
    draw = ImageDraw.Draw(base_img)

    # 点線描画用の補助関数
    def draw_dashed_line(points, fill, width=1, dash_length=5):
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i+1]
            # 2点間の距離と角度を計算
            dist = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
            angle = math.atan2(p2[1]-p1[1], p2[0]-p1[0])
            for d in range(0, int(dist), dash_length * 2):
                start = (p1[0] + math.cos(angle) * d, p1[1] + math.sin(angle) * d)
                end = (p1[0] + math.cos(angle) * min(d + dash_length, dist), 
                       p1[1] + math.sin(angle) * min(d + dash_length, dist))
                draw.line([start, end], fill=fill, width=width)

    import math # 距離計算用

    # --- 輪郭点線の描画 ---
    if outer_line:
        draw_dashed_line(outer_line, fill=(200, 200, 200, 150), width=1)
    if inner_line:
        draw_dashed_line(inner_line, fill=(200, 200, 200, 150), width=1)

    # 公式カラー
    CAR_COLORS = {
        1: (255, 255, 255, 255), 2: (0, 0, 0, 255), 3: (255, 0, 0, 255),
        4: (0, 0, 255, 255), 5: (255, 255, 0, 255), 6: (0, 128, 0, 255),
        7: (255, 165, 0, 255), 8: (255, 105, 180, 255),
    }

    # 各車の走行軌跡
    for item in positions_with_path:
        car_num = item['car']
        path = item['path']
        color = CAR_COLORS.get(car_num, (200, 200, 200, 255))
        if len(path) >= 2:
            draw.line(path, fill=color, width=2)

    # 各車アイコン
    for item in positions_with_path:
        car_num = item['car']
        x, y = item['path'][-1] # last_posの代わりにpathの最後を使用
        icon_path = f'assets/car_icons/{car_num}.png'
        if os.path.exists(icon_path):
            car_icon = Image.open(icon_path).convert('RGBA')
            icon_size = (12, 12)
            car_icon.thumbnail(icon_size, Image.Resampling.LANCZOS)
            paste_x, paste_y = int(x - icon_size[0]//2), int(y - icon_size[1]//2)
            base_img.paste(car_icon, (paste_x, paste_y), car_icon)

    output_path = 'prediction_output.png'
    base_img.save(output_path)
    return output_path

def send_to_discord(image_path, webhook_url):
    if not webhook_url or webhook_url == "YOUR_WEBHOOK_URL_HERE": return
    with open(image_path, 'rb') as f:
        payload = {'content': '【物理走行ルート可視化：輪郭点線ガイド付き】'}
        files = {'file': ('prediction.png', f, 'image/png')}
        requests.post(webhook_url, data=payload, files=files)
