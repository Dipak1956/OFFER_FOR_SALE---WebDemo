# import requests
# import json

# base_url =  "https://trades.lakshmishree.com/"

# def get_ltp(symbol):
#     import yfinance as yf

#     # components = symbol.split(".")
    
#     # if components[1] == 'BO':
#     #     task = {"secretKey": "Lssh034#ZU",
#     #         "appKey": "3d6a8611256720484f1288",
#     #         "source": "WebAPI"}
#     #     resp = requests.post(
#     #     base_url+'apimarketdata/auth/login', json=task)
#     #     j=resp.status_code
        
#     #     j = resp.json()
#     #     token = j['result']['token']
#     #     url = base_url+"apimarketdata/instruments/quotes"
#     #     js = {
#     #         "instruments": [
#     #             {
#     #                 "exchangeSegment": 11,
#     #                 "exchangeInstrumentID": 544021
#     #             }
#     #         ],
#     #         "xtsMessageCode": 1512,
#     #         "publishFormat": "JSON"
#     #     }
        
#     #     js = json.dumps(js)
        
#     #     response = requests.post(url, headers={
#     #                         'Authorization': token, "content-type": "application/json"}, data=js)
        
#     #     t1 = response.json()
        
#     #     list_quotes = t1['result']['listQuotes']
#     #     quote = json.loads(list_quotes[0])

#     #     last_traded_price_now = quote['LastTradedPrice']
#     #     last_traded_price_fut = "-"
#     #     return last_traded_price_now, last_traded_price_fut
        
#     # else:
        
#     try:
#         stock = yf.Ticker(symbol)
#         last_traded_price_now = stock.history(period='1d').tail(1)["Close"].values[0]
#         last_traded_price_fut = "-"
#         return last_traded_price_now, last_traded_price_fut
#     except:
#         try:
#             stock = yf.Ticker(symbol)
#             last_traded_price_now = stock.history().tail(1)["Close"].values[0]
#             last_traded_price_fut = "-"
#             return last_traded_price_now, last_traded_price_fut
#         except Exception as e:
#             print(f"Error fetching data for {symbol}: {e}")
#             return "-", "-"
    
# get_ltp('WENDT.NS')

import requests
import yfinance as yf
from bs4 import BeautifulSoup

def get_bse_scripcode(symbol_name):
    """
    Searches BSE website to find the numeric Scripcode from a symbol name.
    Example: 'RELIANCE' -> '500325'
    """
    try:
        # Clean the symbol (remove .BO or .NS if present)
        clean_name = symbol_name.split('.')[0]
        url = f"https://api.bseindia.com/Msource/1D/getQouteSearch.aspx?Type=EQ&text={clean_name}&flag=site"
        # https://api.bseindia.com/Msource/1D/getQouteSearch.aspx?Type=EQ&text=TIMEX&flag=site
        headers = {
            "referer":"https://www.bseindia.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        # print(response.text)
        if response.status_code == 200 and response.text:
            soup = BeautifulSoup(response.text, 'html.parser')
            # The search usually returns list items <li> with <a> tags containing the scripcode
            # Example: <a href="..." ...>Reliance Industries Ltd. 500325</a>
            
            # We look for the first valid link that contains a digit
            for a_tag in soup.find_all('a'):
                href_parts = a_tag.get('href', '').split('/')
                text = a_tag.get_text()
                # print(text)
                # Extract the last word which is usually the scripcode (digits)
                scripcodes = [part for part in href_parts if part.isdigit()]
                if scripcodes :
                    return scripcodes[0]
                    
    except Exception as e:
        print(f"DEBUG: Error searching scripcode for {symbol_name}: {e}")
    
    return None

def get_price_from_bse(scripcode):
    """
    Fetches the Latest Traded Price (LTP) directly from BSE API using Scripcode.
    """
    try:
        url = "https://api.bseindia.com/BseIndiaAPI/api/EQPeerGp/w"
        params = {"scripcode": scripcode, "scripcomare": ""}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://www.bseindia.com/",
            "Accept": "application/json"
        }

        response = requests.get(url, params=params, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data and "Table" in data and len(data["Table"]) > 0:
                ltp = data["Table"][0].get("LTP")
                return float(ltp) if ltp else None
    except Exception as e:
        print(f"DEBUG: BSE Fetch failed for {scripcode}: {e}")
    
    return None


def get_ltp(symbol):
    price = None
    source = "None"
    
    if '.BO' in symbol:
        scripcode = get_bse_scripcode(symbol)
        
        if scripcode:
            # 2. Get the Price using Scripcode
            price = get_price_from_bse(scripcode)
            if price:
                source = "-"
                return price, source
    
    try:
        stock = yf.Ticker(symbol)
        last_traded_price_now = stock.history(period='1d').tail(1)["Close"].values[0]
        last_traded_price_fut = "-"
        return last_traded_price_now, last_traded_price_fut
    except:
        try:
            stock = yf.Ticker(symbol)
            last_traded_price_now = stock.history().tail(1)["Close"].values[0]
            last_traded_price_fut = "-"
            return last_traded_price_now, last_traded_price_fut
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return "-", "-"