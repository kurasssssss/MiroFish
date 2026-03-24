import requests
import json

class TelegramService:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f'https://api.telegram.org/bot{self.token}/'

    def send_message(self, text):
        url = f'{self.base_url}sendMessage'
        payload = {'chat_id': self.chat_id, 'text': text}
        response = requests.post(url, data=payload)
        return response.json()

    def send_live_monitoring_update(self, data):
        message = f'Live monitoring update: {json.dumps(data, indent=2)}'
        return self.send_message(message)

    def set_webhook(self, url):
        webhook_url = f'{self.base_url}setWebhook'
        payload = {'url': url}
        response = requests.post(webhook_url, data=payload)
        return response.json()