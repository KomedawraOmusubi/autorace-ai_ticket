import os
import requests
from PIL import Image, ImageDraw

def create_prediction_image(positions, waypoints=None):
    base_path = 'assets/20260420-163135.jpg'
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"背景画像が見つかりません: {base_path}")
        
    base_img = Image.open(base_path).convert('RGBA')
    draw = ImageDraw.Draw(base_img)

    # --- 走行ルートを赤線で描画 ---
    if waypoints and len(waypoints) >= 2:
        for i in range(len(waypoints) - 1):
            p1 = waypoints[i]
            p2 = waypoints[i+1]
            draw.line([(p1['x'], p1['y']), (p2['x'], p2['y'])], fill="red", width=3)
            r = 3
            draw.ellipse([p1['x']-r, p1['y']-r, p1['x']+r, p1['y']+r], fill="red")

    # 2. 各車番アイコンを読み込む
    for item in positions:
        car_num = item['car']
        x, y = item['x'], item['y']
        
        icon_path = f'assets/car_icons/{car_num}.png'
        if os.path.exists(icon_path):
            car_icon = Image.open(icon_path).convert('RGBA')
            icon_size = (7, 7)
            car_icon.thumbnail(icon_size, Image.Resampling.LANCZOS)
            
            # 中心合わせ
            paste_x = x - (icon_size[0] // 2)
            paste_y = y - (icon_size[1] // 2)
            base_img.paste(car_icon, (paste_x, paste_y), car_icon)
            
    output_path = 'prediction_output.png'
    base_img.save(output_path)
    return output_path

def send_to_discord(image_path, webhook_url):
    if not webhook_url: return
    with open(image_path, 'rb') as f:
        payload = {'content': '【物理走行ルート可視化：B1追加版】'}
        files = {'file': ('prediction.png', f, 'image/png')}
        requests.post(webhook_url, data=payload, files=files)
