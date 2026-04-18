import os
import requests
from PIL import Image

def create_prediction_image(positions):
    """
    positions: [{'car': 1, 'x': 100, 'y': 200}, ...] のようなリスト
    """
    # 1. 背景画像を読み込む
    base_img = Image.open('assets/background.png').convert('RGBA')
    
    for item in positions:
        car_num = item['car']
        x, y = item['x'], item['y']
        
        # 2. 各車番アイコンを読み込む
        icon_path = f'assets/car_icons/{car_num}.png'
        if os.path.exists(icon_path):
            car_icon = Image.open(icon_path).convert('RGBA')
            # 指定した座標(x, y)に貼り付け
            base_img.paste(car_icon, (x, y), car_icon)
            
    # 3. 合成した画像を一時保存
    output_path = 'prediction_output.png'
    base_img.save(output_path)
    return output_path

def send_to_discord(image_path, webhook_url):
    """Discordへ画像を送信"""
    with open(image_path, 'rb') as f:
        payload = {'content': '【オートレース展開予想】'}
        files = {'file': ('prediction.png', f, 'image/png')}
        requests.post(webhook_url, data=payload, files=files)
