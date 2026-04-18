import os
import requests
from PIL import Image

def create_prediction_image(positions):
    """
    画像を合成する関数
    positions: [{'car': 1, 'x': 100, 'y': 200}, ...] のようなリスト
    """
    # 1. 背景画像を読み込む
    base_path = 'assets/background.png'
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"背景画像が見つかりません: {base_path}")
        
    base_img = Image.open(base_path).convert('RGBA')
    
    for item in positions:
        car_num = item['car']
        x, y = item['x'], item['y']
        
        # 2. 各車番アイコンを読み込む
        icon_path = f'assets/car_icons/{car_num}.png'
        if os.path.exists(icon_path):
            car_icon = Image.open(icon_path).convert('RGBA')
            
            # --- 画像を縮小する処理を追加 ---
            icon_size = (80, 80)  # ここでサイズを指定（幅, 高さ）
            car_icon.thumbnail(icon_size, Image.Resampling.LANCZOS)
            # ------------------------------
            
            # 指定した座標(x, y)に貼り付け
            base_img.paste(car_icon, (x, y), car_icon)
        else:
            print(f"警告: アイコンが見つかりません {icon_path}")
            
    # 3. 合成した画像を一時保存
    output_path = 'prediction_output.png'
    base_img.save(output_path)
    return output_path

def send_to_discord(image_path, webhook_url):
    """Discordへ画像を送信する関数"""
    if not webhook_url:
        print("Webhook URLが設定されていないため、送信をスキップします。")
        return

    with open(image_path, 'rb') as f:
        payload = {'content': '【オートレース展開予想テスト】'}
        files = {'file': ('prediction.png', f, 'image/png')}
        response = requests.post(webhook_url, data=payload, files=files)
        
        if response.status_code in [200, 204]:
            print("Discordへの送信に成功しました。")
        else:
            print(f"送信失敗。ステータスコード: {response.status_code}")

# --- このファイル単体で実行（テスト）する場合の処理 ---
if __name__ == "__main__":
    # GitHubのSecretsに登録した名前から取得6
    WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
    
    # テスト用の配置データ
    test_positions = [
        {'car': 1, 'x': 100, 'y': 200},
        {'car': 2, 'x': 150, 'y': 250},
        {'car': 3, 'x': 200, 'y': 300},
        {'car': 4, 'x': 250, 'y': 350},
        {'car': 5, 'x': 300, 'y': 400},
        {'car': 6, 'x': 350, 'y': 450},
        {'car': 7, 'x': 400, 'y': 500},
        {'car': 8, 'x': 450, 'y': 550},
    ]
    
    try:
        print("画像生成を開始...")
        path = create_prediction_image(test_positions)
        
        print("Discordへの送信を開始...")
        send_to_discord(path, WEBHOOK_URL)
        
    except Exception as e:
        print(f"実行中にエラーが発生しました: {e}")
