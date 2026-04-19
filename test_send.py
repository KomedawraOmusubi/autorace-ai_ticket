import os
import visualizer

# ご要望に合わせて調整した座標データ
# 1号車: そのまま (100)
# 2,3号車: 1個分左 (-30)
# 4,5,6号車: 2個分左 (-60)
# 7,8号車: 3個分左 (-90)
test_positions = [
    {'car': 1, 'x': 100, 'y': 100},
    {'car': 2, 'x': 100, 'y': 130}, # 130-30
    {'car': 3, 'x': 130, 'y': 160}, # 160-30
    {'car': 4, 'x': 130, 'y': 190}, # 190-60
    {'car': 5, 'x': 160, 'y': 220}, # 220-60
    {'car': 6, 'x': 190, 'y': 250}, # 250-60
    {'car': 7, 'x': 190, 'y': 280}, # 280-90
    {'car': 8, 'x': 220, 'y': 310}, # 310-90
]

# 環境変数から取得
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def main():
    try:
        print("画像生成中...")
        # 座標データを渡して画像を生成
        img_path = visualizer.create_prediction_image(test_positions)
        
        print("Discord送信中...")
        visualizer.send_to_discord(img_path, WEBHOOK_URL)
        print("送信完了しました！Discordを確認してください。")
    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    main()
