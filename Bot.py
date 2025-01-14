import pandas as pd
import time
import os
from dotenv import load_dotenv
from binance.client import Client
from binance.enums import *
import requests
load_dotenv()

api_key         = os.getenv('KEY_BINANCE')
secret_key      = os.getenv('SECRET_BINANCE')
chat_id         = '-1002409710683'#os.getenv('CHAT_ID')
token           = os.getenv('TOKEN_TELEGRAM')

client = Client(api_key, secret_key)

class Bot:
    def __init__(self, api_key, secret_key, chat_id, token, symbol, asset, quantity, interval, min_gain):
        self.client = Client(api_key, secret_key)
        self.chat_id = chat_id
        self.token = token
        self.symbol = symbol
        self.asset = asset
        self.quantity = quantity
        self.min_gain = min_gain
        self.last_buy_price = 0
        self.gain = 0
        self.alert_price = 0
        self.read_to_sell = False
        self.position = False
        self.interval = interval
        self.last_fast_average_sell = 0
        
    def write_log(self, msg):
        with open("log.txt", "a") as f:
            f.write(f"{msg}\n")

    def send_message(self, message):    
        url = f'https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={message}'
        try:        
            requests.post(url)
        except Exception as e:
            print(e)        

    def get_candles(self, symbol, interval):
        candles = self.client.get_klines(symbol=symbol, interval=interval, limit = 500)   
        prices = pd.DataFrame(candles)    
        prices.columns=["open_time",
                        "open_price",
                        "high_price",
                        "low_price",
                        "close_price",
                        "volume",
                        "close_time",
                        "asset_volume",
                        "trades",
                        "base_asset_volume",
                        "quote_asset_volume",
                        "-"]
        prices = prices[["close_time","close_price"]]
        prices["close_time"] = pd.to_datetime(prices["close_time"],unit="ms").dt.tz_localize("UTC")
        prices["close_time"] = prices["close_time"].dt.tz_convert("America/Sao_Paulo")
        return prices

    def execute_order(self, symbol, side, quantity, order_type):
        try:
            order = self.client.create_order(
                symbol=symbol,
                side=side,
                type=order_type,
                quantity=quantity,
                newOrderRespType=ORDER_TYPE_MARKET
            )
            return order
        except Exception as e:
            print(e)
    
    def teste_strategy_trade_ma(self,candles):        
        candles["fast_average"] = candles["close_price"].rolling(window=7).mean()
        candles["slow_average"] = candles["close_price"].rolling(window=40).mean()
        if candles["fast_average"].iloc[-1] > candles["slow_average"].iloc[-1]:
            last_price= float(candles["close_price"].iloc[-1])        
            self.last_fast_average_sell = candles["fast_average"].iloc[-1]
                            
            last_fast_average = candles["fast_average"].iloc[-2]
            last_slow_average = candles["slow_average"].iloc[-2]    
            print(f"Fast_sell: {self.last_fast_average_sell:.2f}, Fast: {last_fast_average:.2f}, Last_price: {last_price:.2f}")
            if self.last_fast_average_sell < last_fast_average:
                print(f"Vendendo - Fast_sell: {self.last_fast_average_sell:.2f}, Fast: {last_fast_average:.2f}, Last_price: {last_price:.2f}")
                x=input()
           
    
    def strategy_trade_ma(self,candles, asset, symbol, quantity, position):
        candles["fast_average"] = candles["close_price"].rolling(window=7).mean()
        candles["slow_average"] = candles["close_price"].rolling(window=40).mean()
        last_fast_average = candles["fast_average"].iloc[-1]
        last_slow_average = candles["slow_average"].iloc[-1]    
        asset_free = float(client.get_asset_balance(asset=asset).get('free'))
        asset_free = int(asset_free * 1000) / 1000
        last_price = float(candles["close_price"].iloc[-1])
        
        if last_fast_average > last_slow_average:
            if position:
                print("Já está posicionado - verificando o lucro mínimo")                
                if not self.read_to_sell:
                    self.gain = ((last_price - last_buy_price) / last_buy_price) * 100                
                    if self.gain >= self.min_gain:
                        self.alert_price = self.last_price
                        self.read_to_sell = True
                        
                elif self.last_price > self.alert_price:
                    self.alert_price = self.last_price
                                                    
                elif self.last_price < self.alert_price:
                    print("Vendendo")
                    order = self.execute_order(symbol, SIDE_SELL, asset_free, ORDER_TYPE_MARKET)
                    fills = order.get('fills')
                    price = fills[0].get('price')
                    qty = fills[0].get('qty')
                    msg = f'Venda de {qty} do ativo {symbol} realizada com sucesso ao preço de {price}. Média rápida: {last_fast_average:.2f}, Média lenta: {last_slow_average:.2f}'
                    self.write_log(msg)
                    self.send_message(msg)                
                    self.read_to_sell = False
                    self.last_buy_price = 0
            else:
                print("Comprando")
                order = self.execute_order(symbol, SIDE_BUY, quantity, ORDER_TYPE_MARKET)
                fills = order.get('fills')
                price = fills[0].get('price')
                qty = fills[0].get('qty')            
                msg = f'Compra de {qty} do ativo {symbol} realizada com sucesso ao preço de {price}. Média rápida: {last_fast_average:.2f}, Média lenta: {last_slow_average:.2f}'
                self.write_log(msg)
                self.send_message(msg)
                self.last_buy_price = self.last_price
                position = True
                
        elif last_fast_average < last_slow_average:
            if position:
                print("Vendendo")            
                order = self.execute_order(symbol, SIDE_SELL, asset_free, ORDER_TYPE_MARKET)
                fills = order.get('fills')
                price = fills[0].get('price')
                qty = fills[0].get('qty')
                msg = f'Venda de {qty} do ativo {symbol} realizada com sucesso ao preço de {price}. Média rápida: {last_fast_average:.2f}, Média lenta: {last_slow_average:.2f}'
                self.write_log(msg)
                self.send_message(msg)
                last_buy_price = 0
                position = False
            
    def execute_bot(self):               
        while True:
            candles = self.get_candles(self.symbol, self.interval)                                 
            #self.strategy_trade_ma(candles, self.asset, self.symbol, self.quantity, self.position)     
            self.teste_strategy_trade_ma(candles)     
            time.sleep(1)        

bot = Bot(api_key, secret_key, chat_id, token, "SOLUSDT", "SOL", 0.076, client.KLINE_INTERVAL_15MINUTE, 2)
bot.send_message("Bot started")
bot.execute_bot()
