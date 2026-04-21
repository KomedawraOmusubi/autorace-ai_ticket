import os
import requests
from PIL import Image, ImageDraw

def create_prediction_image(positions, waypoints=None):
    """
    画像を合成する関数
    positions: 車番ごとの最終座標
    waypoints: 赤線で結ぶ基準ルート
    """
    base_path = 'assets/20260420-163135.jpg'
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"背景画像が見つかりません: {base_path}")
        
    base_img = Image.open(base_path).convert('RGBA')
    draw = ImageDraw.Draw(base_img)

    # --- 1. 基準となる走行ルートを赤線で描画 ---
    if waypoints and len(waypoints) >= 2:
        for i in range(len(waypoints) - 1):
            p1, p2 = waypoints[i], waypoints[i+1]
            draw.line([(p1['x'], p1['y']), (p2['x'], p2['y'])], fill="red", width=2)
            # 各ポイントに小さな目印
            r = 2
            draw.ellipse([p1['x']-r, p1['y']-r, p1['x']+r, p1['y']+r], fill="red")

    # --- 2. 各車番アイコンの合成 ---
    for item in positions:
        car_num = item['car']
        x, y = item['x'], item['y']
        
        icon_path = f'assets/car_icons/{car_num}.png'
        if os.path.exists(icon_path):
            car_icon = Image.open(icon_path).convert('RGBA')
            
            # アイコンサイズ (10x10程度が見やすい)
            icon_size = (10, 10)
            car_icon.thumbnail(icon_size, Image.Resampling.LANCZOS)
            
            # 座標(x,y)がアイコンの中心になるように貼り付け
            paste_x = x - (icon_size[0] // 2)
            paste_y = y - (icon_size[1] // 2)
            base_img.paste(car_icon, (paste_x, paste_y), car_icon)
        else:
            print(f"警告: アイコンが見つかりません {icon_path}")
            
    output_path = 'prediction_output.png'
    base_img.save(output_path)
    return output_path

def send_to_discord(image_path, webhook_url):
    if not webhook_url: return
    with open(image_path, 'rb') as f:
        payload = {'content': '【第1コーナー：ライン分散シミュレーション】'}
        files = {'file': ('prediction.png', f, 'image/png')}
        requests.post(webhook_url, data=payload, files=files)
