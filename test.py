import os
import requests
import sys

def main():
    # GitHubのSecretsに登録した DISCORD_WEBHOOK_URL を読み込む
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    
    # URLが取得できなかった場合のチェック
    if not url or url == "あなたのWebhook URL":
        print("エラー: Webhook URLが正しく設定されていません。GitHubのSettingsを確認してください。")
        sys.exit(1)

    message = {
        "content": "🚀 **GitHub Actions からの送信成功！**\nオートレース予想の準備が整いました。"
    }

    try:
        response = requests.post(url, json=message)
        response.raise_for_status()
        print("Discordへの送信に成功しました！")
    except Exception as e:
        print(f"送信失敗: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
