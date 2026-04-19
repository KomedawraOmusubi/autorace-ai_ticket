import os
import visualizer

# テスト用の座標データ
# グレーの道路を避けるため、xとyの開始位置を大きくします
test_positions = [
    {'car': 1, 'x': 200, 'y': 400},
    {'car': 2, 'x': 230, 'y': 440},
    {'car': 3, 'x': 260, 'y': 480},
    {'car': 4, 'x': 290, 'y': 520},
    {'car': 5, 'x': 320, 'y': 560},
    {'car': 6, 'x': 350, 'y': 600},
    {'car': 7, 'x': 380, 'y': 640},
    {'car': 8, 'x': 410, 'y': 680},
]

# 環境変数から取得するように変更
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def main():
    try:
        print("画像生成中...")
        img_path = visualizer.create_prediction_image(test_positions)
        
        print("Discord送信中...")
        visualizer.send_to_discord(img_path, WEBHOOK_URL)
        print("送信完了しました！Discordを確認してください。")
    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    main()
