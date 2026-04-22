import os
import requests
import math
from PIL import Image, ImageDraw

def create_prediction_image(positions_with_path, waypoints=None, outer_line=None, inner_line=None):
    # 背景画像の読み込み
    base_path = 'assets/20260420-163135.jpg'
    if not os.path.exists(base_path):
        # 背景がない場合はグレーのキャンバスを作成
        base_img = Image.new('RGBA', (800, 500), (50, 50, 50, 255))
    else:
        base_img = Image.open(base_path).convert('RGBA')
    
    draw = ImageDraw.Draw(base_img)

    # 点線描画用の補助関数
    def draw_dashed_line(points, fill, width=2, dash_length=7):
        for i in range(len(points) - 1):
            p1, p2 = points[i], points[i+1]
            dist = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
            angle = math.atan2(p2[1]-p1[1], p2[0]-p1[0])
            for d in range(0, int(dist), dash_length * 2):
                start = (p1[0] + math.cos(angle) * d, p1[1] + math.sin(angle) * d)
                end = (p1[0] + math.cos(angle) * min(d + dash_length, dist), 
                       p1[1] + math.sin(angle) * min(d + dash_length, dist))
                draw.line([start, end], fill=fill, width=width)

    # --- 1. 境界線の描画（黒の点線） ---
    # fillの4つ目の値は透明度(0-255)です
    if outer_line:
        draw_dashed_line(outer_line, fill=(0, 0, 0, 255), width=2)
    if inner_line:
        draw_dashed_line(inner_line, fill=(0, 0, 0, 255), width=2)

    # --- 2. ハンデ別色分け定義（0m ～ 110m） ---
    def get_handy_color(handy):
        HANDY_COLORS = {
            0:   (255, 255, 255, 255), # 白
            10:  (200, 255, 200, 255), # 薄緑
            20:  (100, 255, 100, 255), # 緑
            30:  (200, 200, 255, 255), # 薄青
            40:  (100, 100, 255, 255), # 青
            50:  (255, 255, 150, 255), # 黄色
            60:  (255, 200, 0, 255),   # オレンジ
            70:  (255, 100, 100, 255), # 薄赤
            80:  (255, 0, 0, 255),     # 赤
            90:  (150, 0, 0, 255),     # 濃い赤
            100: (80, 80, 80, 255),    # 濃いグレー（黒点線との識別用）
            110: (0, 0, 0, 255)        # 黒
        }
        # 10m刻みのキーに変換（110まで対応）
        key = min(max(0, (handy // 10) * 10), 110)
        return HANDY_COLORS.get(key, (200, 200, 200, 255))

    # --- 3. 走行ラインの描画 ---
    for item in positions_with_path:
        path = item['path']
        handy = item.get('handy', 0)
        color = get_handy_color(handy)
        if len(path) >= 2:
            # width=3 でラインを強調
            draw.line(path, fill=color, width=3)

    # --- 4. 車アイコンの描画（最後に行うことでラインの上に表示） ---
    for item in positions_with_path:
        car_num = item['car']
        # pathの最後（現在地）にアイコンを配置
        x, y = item['path'][-1]
        icon_path = f'assets/car_icons/{car_num}.png'
        if os.path.exists(icon_path):
            car_icon = Image.open(icon_path).convert('RGBA')
            icon_size = (16, 16)
            car_icon.thumbnail(icon_size, Image.Resampling.LANCZOS)
            paste_x, paste_y = int(x - icon_size[0]//2), int(y - icon_size[1]//2)
            base_img.paste(car_icon, (paste_x, paste_y), car_icon)

    # 画像の保存
    output_path = 'prediction_output.png'
    base_img.save(output_path)
    return output_path

def send_to_discord(image_path, webhook_url):
    """
    生成された画像をDiscordのWebhookに送信する。
    """
    if not webhook_url or webhook_url == "YOUR_WEBHOOK_URL_HERE":
        print("Webhook URLが設定されていません。")
        return
    
    with open(image_path, 'rb') as f:
        payload = {'content': '【走行予測：ハンデ別カラー・境界線モデル】'}
        files = {'file': ('prediction.png', f, 'image/png')}
        try:
            response = requests.post(webhook_url, data=payload, files=files)
            response.raise_for_status()
            print("Discordへの送信が完了しました。")
        except Exception as e:
            print(f"Discord送信エラー: {e}")
