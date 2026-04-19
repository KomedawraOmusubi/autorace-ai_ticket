import os
import visualizer

# ご要望に合わせて調整した座標データ
# 開始位置(1号車)を道路に重ならないよう x:200, y:400 に設定
# そこから指定の数だけ左（xをマイナス）にずらしています
test_positions = [
    {'car': 1, 'x': 230,             'y': 400}, # そのまま
    {'car': 2, 'x': 260 - 90,        'y': 520}, # 1個左へ
    {'car': 3, 'x': 300 - 90,        'y': 600}, # 1個左へ
    {'car': 4, 'x': 320 - (30 * 6),  'y': 680}, # 2個左へ
    {'car': 5, 'x': 350 - (30 * 6),  'y': 760}, # 2個左へ
    {'car': 6, 'x': 390 - (30 * 6),  'y': 840}, # 2個左へ
    {'car': 7, 'x': 390 - (30 * 9),  'y': 930}, # 3個左へ
    {'car': 8, 'x': 430 - (30 * 9),  'y': 1010}, # 3個左へ
]

# 環境変数から取得
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def main():
    try:
        print("画像生成中...")
        # visualizer.py の縮小処理(90, 90)が適用された状態で生成されます
        img_path = visualizer.create_prediction_image(test_positions)
        
        print("Discord送信中...")
        visualizer.send_to_discord(img_path, WEBHOOK_URL)
        print("送信完了しました！Discordを確認してください。")
    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    main()
