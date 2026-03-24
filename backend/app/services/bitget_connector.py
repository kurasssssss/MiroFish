import requests
import hmac
import hashlib
import time

class BitgetConnector:
    def __init__(self, api_key, api_secret, api_passphrase):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.base_url = 'https://api.bitget.com/v1/'

    def _generate_signature(self, method, path, body='', timestamp=None):
        if timestamp is None:
            timestamp = str(int(time.time() * 1000))
        message = f'{method}{path}{timestamp}{body}'
        signature = hmac.new(self.api_secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        return signature, timestamp

    def _send_request(self, method, endpoint, params=None):
        if params is None:
            params = {}
        path = f'{self.base_url}{endpoint}'
        signature, timestamp = self._generate_signature(method, endpoint, str(params))
        headers = {
            'X-BITGET-APIKEY': self.api_key,
            'X-BITGET-PASSPHRASE': self.api_passphrase,
            'X-BITGET-SIGNATURE': signature,
            'X-BITGET-TIMESTAMP': timestamp,
            'Content-Type': 'application/json',
        }
        response = requests.request(method, path, headers=headers, json=params)
        return response.json()

    def spot_trade(self, symbol, side, price, size):
        endpoint = 'spot/order'
        params = {
            'symbol': symbol,
            'side': side,
            'price': price,
            'size': size,
            'type': 'limit',
        }
        return self._send_request('POST', endpoint, params)

    def futures_trade(self, symbol, side, price, size, contract_type='quarter'):  
        endpoint = 'futures/order'
        params = {
            'symbol': symbol,
            'side': side,
            'price': price,
            'size': size,
            'contract_type': contract_type,
            'type': 'limit',
        }
        return self._send_request('POST', endpoint, params)

    def margin_trade(self, symbol, side, price, size):
        endpoint = 'margin/order'
        params = {
            'symbol': symbol,
            'side': side,
            'price': price,
            'size': size,
            'type': 'limit',
        }
        return self._send_request('POST', endpoint, params)

    def get_order(self, order_id):
        endpoint = f'order/{order_id}'
        return self._send_request('GET', endpoint)

    def cancel_order(self, order_id):
        endpoint = f'order/{order_id}/cancel'
        return self._send_request('POST', endpoint) 

# Example usage:
# connector = BitgetConnector(api_key='your_api_key', api_secret='your_api_secret', api_passphrase='your_api_passphrase')
# response = connector.spot_trade('BTCUSDT', 'buy', 45000, 0.01)
# print(response)
