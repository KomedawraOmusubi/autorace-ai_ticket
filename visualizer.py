import os
import requests
import math
from PIL import Image, ImageDraw

def create_prediction_image(positions_with_path, waypoints=None, outer_line=None, inner_line=None, **kwargs):
    base_path = 'assets/20260420-163135.jpg'
    if not os.path.exists(base_path):
        # 背景がない場合はグレーのキャンバスを作成
        base_img = Image.new('RGBA', (800, 500), (50, 50, 50, 255))
    else:
        base_img = Image.open(base_path).convert('RGBA')
    
    draw = ImageDraw.Draw(base_img)

    # 点線描画用の補助関数
    def draw_dashed_line(points, fill, width=1, dash_length=7):
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i+1]
            dist = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
            angle = math.atan2(p2[1]-p1[1], p2[0]-p1[0])
            for d in range(0, int(dist), dash_length * 2):
                start = (p1[0] + math.cos(angle) * d, p1[1] + math.sin(angle) * d)
                end = (p1[0] + math.cos(angle) * min(d + dash_length, dist), 
                       p1[1] + math.sin(angle) * min(d + dash_length, dist))
                draw.line([start, end], fill=fill, width=width)

    # --- 1. 輪郭点線の描画（白から黒に変更） ---
    # fillを (0, 0, 0, 200) に変更して黒の点線に
    if outer_line:
        draw_dashed_line(outer_line, fill=(0, 0, 0, 200), width=2)
    if inner_line:
        draw_dashed_line(inner_line, fill=(0, 0, 0, 200), width=2)

    # --- 2. 各車の走行軌跡（ハンデ色分けで再有効化） ---
    # ハンデに応じた色（グラデーション）を定義
    def get_handy_color(handy):
        # 0m(白) -> 100m(濃いグレー) への変化例
        val = int(255 - (handy * 1.5)) # ハンデが大きいほど暗く
        return (val, val, val, 255)

    for item in positions_with_path:
        path = item['path']
        handy = item.get('handy', 0) # calculate_rail_positionsから渡されたハンデ値
        color = get_handy_color(handy)
        
        if len(path) >= 2:
            # 走行ラインを描画
            draw.line(path, fill=color, width=2)

    # --- 3. 各車アイコンの描画（現在地のみ） ---
    for item in positions_with_path:
        car_num = item['car']
        x, y = item['path'][-1]
        icon_path = f'assets/car_icons/{car_num}.png'
        if os.path.exists(icon_path):
            car_icon = Image.open(icon_path).convert('RGBA')
            icon_size = (14, 14)
            car_icon.thumbnail(icon_size, Image.Resampling.LANCZOS)
            paste_x, paste_y = int(x - icon_size[0]//2), int(y - icon_size[1]//2)
            base_img.paste(car_icon, (paste_x, paste_y), car_icon)

    output_path = 'prediction_output.png'
    base_img.save(output_path)
    return output_path

def send_to_discord(image_path, webhook_url):
    if not webhook_url or webhook_url == "YOUR_WEBHOOK_URL_HERE": return
    with open(image_path, 'rb') as f:
        payload = {'content': '【物理走行予測：ハンデ別走行ラインモデル】'}
        files = {'file': ('prediction.png', f, 'image/png')}
        try:
            response = requests.post(webhook_url, data=payload, files=files)
            response.raise_for_status()
        except Exception as e:
            print(f"Discord送信エラー: {e}")
