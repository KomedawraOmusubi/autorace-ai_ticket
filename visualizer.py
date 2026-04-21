import os
import requests
from PIL import Image, ImageDraw

def create_prediction_image(positions_with_path, waypoints=None):
    """
    positions_with_path: 各車の移動履歴を含むデータ
    waypoints: 基準となる赤線ルート
    """
    base_path = 'assets/20260420-163135.jpg'
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"背景画像が見つかりません: {base_path}")
        
    base_img = Image.open(base_path).convert('RGBA')
    draw = ImageDraw.Draw(base_img)

    # --- オートレース公式車番色の定義 ---
    CAR_COLORS = {
        1: (255, 255, 255, 255), # 白
        2: (0, 0, 0, 255),       # 黒
        3: (255, 0, 0, 255),     # 赤
        4: (0, 0, 255, 255),     # 青
        5: (255, 255, 0, 255),   # 黄
        6: (0, 128, 0, 255),     # 緑
        7: (255, 165, 0, 255),   # 橙
        8: (255, 105, 180, 255), # ピンク
    }

    # 1. 基準の赤線を薄く描画
    if waypoints:
        for i in range(len(waypoints) - 1):
            p1, p2 = waypoints[i], waypoints[i+1]
            draw.line([(p1['x'], p1['y']), (p2['x'], p2['y'])], fill=(255, 0, 0, 80), width=1)

    # 2. 各車の走行軌跡（ライン）を描画
    for item in positions_with_path:
        car_num = item['car']
        path = item['path'] # これまでの経由点リスト
        color = CAR_COLORS.get(car_num, (200, 200, 200, 255))
        
        if len(path) >= 2:
            # 軌跡を線で結ぶ
            draw.line(path, fill=color, width=2)

    # 3. 各車番アイコンを最前面に合成
    for item in positions_with_path:
        car_num = item['car']
        x, y = item['last_pos']
        
        icon_path = f'assets/car_icons/{car_num}.png'
        if os.path.exists(icon_path):
            car_icon = Image.open(icon_path).convert('RGBA')
            icon_size = (10, 10)
            car_icon.thumbnail(icon_size, Image.Resampling.LANCZOS)
            
            paste_x = int(x - icon_size[0] // 2)
            paste_y = int(y - icon_size[1] // 2)
            base_img.paste(car_icon, (paste_x, paste_y), car_icon)

    output_path = 'prediction_output.png'
    base_img.save(output_path)
    return output_path

def send_to_discord(image_path, webhook_url):
    if not webhook_url: return
    with open(image_path, 'rb') as f:
        payload = {'content': '【第1コーナー：全車個別走行ライン可視化】'}
        files = {'file': ('prediction.png', f, 'image/png')}
        requests.post(webhook_url, data=payload, files=files)
