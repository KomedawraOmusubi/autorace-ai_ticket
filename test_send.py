import visualizer

# テスト用の座標データ (x, y は後で調整するので、今は適当な値です)
# 1号車から8号車まで階段状に並べてみます
test_positions = [
    {'car': 1, 'x': 100, 'y': 100},
    {'car': 2, 'x': 130, 'y': 130},
    {'car': 3, 'x': 160, 'y': 160},
    {'car': 4, 'x': 190, 'y': 190},
    {'car': 5, 'x': 220, 'y': 220},
    {'car': 6, 'x': 250, 'y': 250},
    {'car': 7, 'x': 280, 'y': 280},
    {'car': 8, 'x': 310, 'y': 310},
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
