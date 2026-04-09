# test.py
import requests
url = "あなたのWebhook URL"
requests.post(url, json={"content": "テスト送信成功！オートレース予想準備完了。"})
