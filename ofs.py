from datetime import datetime
import requests
import pandas as pd
import json
from flask import Flask, request, redirect, render_template, jsonify, url_for, session
from collections import defaultdict
import ltp
import sqlite3
from functools import wraps
import os
import base64, sys, time, atexit
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization, hashes
from io import StringIO
from requests.exceptions import RequestException
from bs4 import BeautifulSoup
import random
import re
import traceback
from selenium import webdriver
from selenium.webdriver.common.by import By
import codecs

import asyncio
import threading
from threading import Lock

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_login'

base_dir = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = 'Ofs Bidding'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
update_lock = Lock()
excel_filepath = r'Ofs Bidding\Ofs_Upload.xlsx'

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def load_private_key(file_path):
    with open(file_path, 'rb') as f:
        return serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())

try:
    private_key = load_private_key('private_key.pem')
except:
    private_key = None

def read_file(ofs_id=1):
    global nse_url, bse_url, floor_price, base_quantity, greenShoe_quantity, ofs_name, category, Rtime, symbol, Company_Id, Price_Alert, Qty_Alert, TickSize
    
    conn = get_db_connection()
    ofs = conn.execute('SELECT * FROM OFSDetail WHERE id = ?', (ofs_id,)).fetchone()
    conn.close()
    if ofs:
        ofs_name = ofs['name']
        nse_url = ofs['nse_url']
        bse_url = ofs['bse_url']
        floor_price = float(ofs['floor_price'])
        base_quantity = int(ofs['base_quantity'])
        greenShoe_quantity = int(ofs['greenShoe_quantity'])
        category = ofs['Category']
        symbol = ofs['Symbol']
    else:
        ofs_name = 'NOT FOUND'
        nse_url = ''
        bse_url = ''
        floor_price = 0
        base_quantity = 0
        greenShoe_quantity = 0
        category = 'Retail'
        symbol = 'UNKNOWN'
        
    Rtime = '15:30:00'
    Company_Id = '1'
    Price_Alert = '0'
    Qty_Alert = '0'
    TickSize = 0.01

read_file()

def read_pastofsdata():
    global Historical_OFS_Data, Historical_Data
    Historical_Data = pd.DataFrame()
    Historical_OFS_Data = ''

read_pastofsdata()

s = requests.Session()
baseurl = 'https://www.nseindia.com/market-data/ofs-information'
headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36', 'accept-language': 'en,gu;q=0.9,hi;q=0.8', 'accept-encoding': 'gzip, deflate, br'}
try:
    nse_res_cokies = s.get(baseurl, headers=headers, timeout=15)
    cookies = dict(nse_res_cokies.cookies)
except:
    cookies = {}

existing_data = {'Conservative': [{}], 'Moderate': [{}], 'Aggressive': [{}]}

#RECORD LAST PRICE AND TIME CHANGE
global last_price
global last_quan_nse
global last_quan_bse
global timee_all
global timee_bse
global timee_nse
global Old_nse_df
global Old_bse_df
global Old_bse_time
global Old_nse_time
global bse_lastupdate , O_Category
global last_Dd_value
global Old_conservative,Old_moderate,Old_aggressve
global excel_file_Df,Csv_filepath,Csv_dataDf
global last_radio_btn
global Old_radio_btn
global ltp_sym
global top_Qtytable
top_Qtytable = None
ltp_sym = None
excel_file_Df = None
Csv_filepath = None
excel_filepath = None
Csv_dataDf = None
last_Dd_value = None
last_radio_btn = None
Old_radio_btn = None
Old_nse_time = None
Old_bse_time = None
last_price = 0
last_quan_nse = 0
last_quan_bse = 0
Old_conservative = 0
Old_moderate = 0
Old_aggressve = 0
Old_nse_df = None
Old_bse_df = None
O_Category = None
timee_all = datetime.now()
timee_bse = datetime.now()
timee_nse = datetime.now()



#FETCH JSON DATA FROM NSE
def nse(url):
    retries = 5
    for attempt in range(retries):
        # proxy = random.choice(proxy_list)
        try:
            headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
                    'accept-language': 'en,gu;q=0.9,hi;q=0.8','accept-encoding': 'gzip, deflate, br'
                }
            
            response = s.get(url, headers=headers,
                                timeout=10, cookies=cookies)
            data = response.json()
            return data
        except RequestException as e:
            # traceback.print_exc()
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(0.5)  # Wait before retrying
            else:
                return None

# FETCH TABLE DATA FROM BSE AND CONVERT IT TO JSON FORMAT FOR ONLY FISRST AND THIRD COLUMN
def bse(url,category):
    global bse_lastupdate
    retries = 5
    for attempt in range(retries):
        try:
            x = requests.get(url, headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36','referer': 'https://www.bseindia.com/'})
            data = x.json()

            json_data = []
            bse_lastupdate = None
            bse_ytbc_qty = 0

            # Optimization: Rebuild the data format using list comprehension instead of a for loop
            if 'Table' in data and data['Table']:
                table_data = data['Table']
                if category == "Retail":
                    json_data = [
                        {
                            'Price Interval': row.get('OE_PRICE'),
                            'No. of Bids': row.get('BIDCOUNT'),
                            'Confirmed': row.get('CONFIRMEDQTY')
                        } for row in table_data
                    ]
                else:
                    json_data = [
                        {
                            'Price Interval': row.get('OE_PRICE'),
                            'No. of Bids': row.get('BIDS'),
                            'Confirmed': row.get('CONFIRMEDQTY')
                        } for row in table_data
                    ]
                
                # Extract and parse timestamp safely
                raw_dttm = table_data[0].get('DTTM')
                if raw_dttm:
                    dt_obj = datetime.fromisoformat(raw_dttm.split('.')[0])
                    bse_lastupdate = dt_obj.strftime('%I:%M %p')

            # Extract "Yet to be Confirmed" quantity
            if 'Table2' in data and data['Table2']:
                bse_ytbc_qty = data['Table2'][0].get('CUM_UNC_QTY', 0)
            
            return json_data,bse_ytbc_qty,bse_lastupdate
        
        except (requests.exceptions.RequestException, IndexError, ValueError) as e:
            print(f"Attempt {attempt + 1} failed with error: {e}")
            if attempt < retries - 1:
                time.sleep(0.5)  # Wait for 2 seconds before retrying
            else:
                return None
        except Exception as e:
            print(traceback.format_exc())
            return None,None

#MAIN ANALYSIS FUNCTION WHICH TAKES NSE AND BSE DATA AND CUT OFF PRICE AND QUANTITY AS INPUT
def analysis(nse_df1, bse_df1, cut, Qty ,e4_get):
    global cutprice
    all_data_df = []
    #APPEND CUT OFF PRICE AND QUANTITY IN NSE DATA
    new_nse_df = []
    nse_ytbc_qty = 0
    if nse_df1 :
        for itm in nse_df1:
            x = itm["pri"]
            if itm["pri"] == "Cut Off price":
                x = cut
                
                new_nse = {
                    "price" : x,
                    "quantity" : itm["conQty"]
                }
                new_data = {
                    "price" : float(x),
                    "Nse No of bids" :int(itm["bids"]),
                    "Nse Bid Qty" : itm["conQty"]
                }
                nse_ytbc_qty = nse_ytbc_qty + int(itm["uCQty"])
                new_nse_df.append(new_nse)
                all_data_df.append(new_data)
                continue

            new_nse = {
                "price" : x,
                "quantity" : itm["conQty"]
            }
            new_data = {
                "price" : float(x.replace(",","")),
                "Nse No of bids" : int(itm["bids"]),
                "Nse Bid Qty" : itm["conQty"]
            }
            nse_ytbc_qty = nse_ytbc_qty + int(itm["uCQty"])
            
            new_nse_df.append(new_nse)
            all_data_df.append(new_data)

    else:
        new_data = {
            "price" : cut,
            "Nse No of bids" : None,
            "Nse Bid Qty" : None,
        }
        all_data_df.append(new_data)
        
    #APPEND CUT OFF PRICE AND QUANTITY IN BSE DATA
    new_bse_df = []
    # cn_bse = 0
    if bse_df1:
        
        for itm in bse_df1:
            # cn_bse += 1
            # if cn_bse <=2:
            #     continue
            x = itm["Price Interval"]
            if x == "Cut-off":
                x = cut
                new_bse = {
                    "price" : x,
                    "quantity" : itm["Confirmed"]
                }
                new_data = {
                    "price" : float(x),
                    "Bse No of Bids": int(itm["No. of Bids"]),
                    "Bse Bid Qty" : itm["Confirmed"]
                }
                new_bse_df.append(new_bse)
                all_data_df.append(new_data)
                continue

            if x == "Total":
                break

            new_bse = {
                "price" : x,
                "quantity" : itm["Confirmed"]
            }
            new_data = {
                "price" : float(x),
                "Bse No of Bids": int(itm["No. of Bids"]),
                "Bse Bid Qty" : itm["Confirmed"]
            }

            new_bse_df.append(new_bse)
            all_data_df.append(new_data)
            
    else:
        new_data = {
            "price" : cut,
            "Bse No of Bids": None,
            "Bse Bid Qty" : None,
        }
        all_data_df.append(new_data)
    #MERGE NSE AND BSE DATA
    all_data = []
    all_data.extend(new_nse_df)
    all_data.extend(new_bse_df)
    
    # Create a defaultdict to store prices as keys and quantities as values
    price_quantities = defaultdict(int)

    #BELOW CODE REMOVES DUPLICATE PRICE AND ADDS QUANTITY TO SHOW ACTUAL DATA
    # Iterate over the data
    for item in all_data:
        price = item["price"]
        if isinstance(price, str):
            price = float(price.replace(",", ""))
        if item["quantity"] != None:
            quantity = int(item["quantity"])
        else:
            quantity = 0
        price_quantities[price] += quantity

    # Create a new list to store the updated data
    updated_data = []
    new_updated_data = []

    # Iterate over the price_quantities dictionary and create updated data items
    for price, quantity in price_quantities.items():
        updated_data.append({"price": str(price), "quantity": str(quantity)})
    
    # new_updated_data = updated_data
    updated_data = sorted(updated_data, key=lambda x: float(x['price']))
    new_updated_data = updated_data
    #UPDATE CUT OFF PRICE WHEN OFS TIMES CROSSES 1
    total = 0
    num = 0
    
    AvgToTheCompany = float(cut)
    AvgToTheCompanyMul = 0
    for i in range(len(updated_data) - 1, -1, -1):
        item = updated_data[i]
        x = float(item["quantity"])
        AvgToTheCompanyMul = (AvgToTheCompanyMul) + (float(item["price"]) * float(item["quantity"]))
        total = total + x
        if total >= Qty:
            AvgToTheCompany = AvgToTheCompanyMul / total
            num = 1
            break

    if(num == 1):
        try:
            prize = updated_data[i+1]["price"]
        except:
            prize = updated_data[i]["price"]
    else:
        prize = cut
        
    greenqty = 0
    total = 0
    for i in range(len(new_updated_data) - 1, -1, -1):
        item = new_updated_data[i]
        x = float(item["quantity"])
        total = total + x
        if e4_get != 0:
            if total >= e4_get:
                greenqty = 1
                break
            
    if (greenqty==1):
        try:
            cutprice = new_updated_data[i+1]["price"]
        except:
            cutprice = new_updated_data[i]["price"]
        # cutprice = float(new_updated_data[i+1]["price"])
    else:
        cutprice = cut 

    #TOTAL "quantity" for nse data
    total_nse = 0
    for i, item in enumerate(new_nse_df):
        x = float(item["quantity"])
        total_nse = total_nse + x
    
    #TOTAL "quantity" for bse data
    total_bse = 0
    for i, item in enumerate(new_bse_df):
        if item["quantity"] != None:
            x = float(item["quantity"])
        else:
            x = 0
        total_bse = total_bse + x

    #TOTAL "quantity" for all data
    total_all = 0
    for i, item in enumerate(updated_data):
        x = float(item["quantity"])
        total_all = total_all + x

    # max_all_quan = 0
    # second_max_quan = 0
    # third_max_quan = 0
    # max_all_price = 0
    # second_max_price = 0
    # third_max_price = 0

    # for i, item in enumerate(updated_data):
    #     x = float(item["quantity"])
        
    #     if x > max_all_quan and float(item["price"]) > float(prize):
    #         third_max_quan = second_max_quan
    #         third_max_price = second_max_price
    #         second_max_quan = max_all_quan
    #         second_max_price = max_all_price
    #         max_all_quan = x
    #         max_all_price = float(item["price"])
    #     elif x > second_max_quan and float(item["price"]) > float(prize):
    #         third_max_quan = second_max_quan
    #         third_max_price = second_max_price
    #         second_max_quan = x
    #         second_max_price = float(item["price"])
    #     elif x > third_max_quan and float(item["price"]) > float(prize):
    #         third_max_quan = x
    #         third_max_price = float(item["price"])

    # max_all_quan1 = second_max_quan
    # max_all_price1 = second_max_price
    # max_all_quan2 = third_max_quan
    # max_all_price2 = third_max_price

    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    
    # Create Nse BSe Data Table    
    Data_df = pd.DataFrame(all_data_df)
    # excel_file_data = r'Ofs_dataa\SAGILITY\2025-05-27_15-31-03.xlsx'
    # Data_df = pd.read_excel(excel_file_data, engine='openpyxl')
    Data_df['Nse Bid Qty'] = Data_df['Nse Bid Qty'].astype(float).fillna(0)
    Data_df.fillna(0,inplace=True)
    Data_df['Nse Bid Qty'] = Data_df['Nse Bid Qty'].astype(str).str.replace(',', '')
    Data_df['Bse Bid Qty'] = Data_df['Bse Bid Qty'].astype(str).str.replace(',', '')
    
    Data_df['Nse Bid Qty'] = Data_df['Nse Bid Qty'].astype(float).astype(int)
    Data_df['Bse Bid Qty'] = Data_df['Bse Bid Qty'].astype(float).astype(int)
    Data_df['Nse + Bse No of Bids'] = Data_df['Bse No of Bids'].astype(int) + Data_df['Nse No of bids'].astype(int)
    Data_df = Data_df.groupby('price', as_index=False).agg({'Nse + Bse No of Bids':'sum' ,'Bse Bid Qty': 'sum' , 'Nse Bid Qty':'sum' })
    
    Data_df_filtered = Data_df
    Data_df_filtered["Total Qty"] = Data_df["Nse Bid Qty"] + Data_df["Bse Bid Qty"]
    Data_df_filtered = Data_df_filtered[Data_df_filtered["price"].astype(float) > float(prize)]
    Data_df_sorted = Data_df_filtered.sort_values(by="Total Qty", ascending=False)

    # Get top 10
    top_10 = Data_df_sorted.head(10)

    Data_df = Data_df.groupby("price").first().reset_index()
    Data_df['Nse + Bse Bid Qty'] = Data_df['Nse Bid Qty'] + Data_df['Bse Bid Qty']
    Data_df['Nse + Bse Bid Qty'] = Data_df['Nse + Bse Bid Qty'].astype(int)
    
    Data_df = Data_df.sort_values(by='price', ascending=False)
    Data_df['Nse Bse Cumulative Qty'] = Data_df['Nse + Bse Bid Qty'].cumsum()
    
    def format_in_indian_style(x):
        if isinstance(x, (int, float)):
            x_str = str(int(x))[::-1]
            parts = []
            parts.append(x_str[:3])  # First three digits
            x_str = x_str[3:]
            while x_str:
                parts.append(x_str[:2])  # Next two digits
                x_str = x_str[2:]
            return ','.join(parts)[::-1]
        return x

    Data_df = Data_df.sort_values(by='price', ascending=True)
    columns_to_format = ['Nse Bse Cumulative Qty', 'Nse + Bse Bid Qty','Nse Bid Qty','Bse Bid Qty']
    Data_df[columns_to_format] = Data_df[columns_to_format].map(format_in_indian_style)
    
    new_data_df = Data_df.sort_values(by='price', ascending=False)
    total_bids = new_data_df['Nse + Bse No of Bids'].sum()
    # new_data_df['Nse + Bse No of Bids'] = new_data_df['Nse + Bse No of Bids'].astype(str) + '(100%)'
    new_data_df['cumsum'] = new_data_df['Nse + Bse No of Bids'].cumsum()
    
    cutoff_row = new_data_df[new_data_df['price'] == float(prize)]
    if not cutoff_row.empty:
        cutoff_cumsum = cutoff_row['cumsum'].values[0]
    else:
        cutoff_cumsum = 0
    
    
    def Bids_custom_label(row):
        row_cumsum = row['cumsum']
        if pd.notnull(row_cumsum) and total_bids != 0:
            percent = (row_cumsum / total_bids * 100)
            first_diff = total_bids - row_cumsum
            second_diff = total_bids - cutoff_cumsum
            final_diff = first_diff - second_diff
            final_diff_percent = (final_diff / total_bids * 100)
            if final_diff_percent >= 0:
                return f"{int(row['Nse + Bse No of Bids'])} ({final_diff_percent:.1f}%)"
            else:
                return f"{int(row['Nse + Bse No of Bids'])}"
        return "0 (0%)"
    
    new_data_df['Nse + Bse No of Bids'] = new_data_df.apply(Bids_custom_label, axis=1)
    
    # new_data_df['Nse + Bse No of Bids'] = new_data_df.apply(
    #     lambda row: f"{int(row['Nse + Bse No of Bids'])}({(row['cumsum'] / total_bids * 100):.2f}%)",
    #     axis=1
    # )
    new_data_df.drop(columns=['cumsum'], inplace=True)
    
    new_data_df['Cleaned Qty'] = new_data_df['Nse Bse Cumulative Qty'].str.replace(',', '')
    new_data_df['Cleaned Qty'] = pd.to_numeric(new_data_df['Cleaned Qty'], errors='coerce')
    total_Qty = new_data_df['Cleaned Qty'].iloc[-1]
    
    cutoff_row = new_data_df[new_data_df['price'] == float(prize)]  # You can change this condition
    if not cutoff_row.empty:
        cutoff_cumsum = cutoff_row['Cleaned Qty'].values[0]
    else:
        cutoff_cumsum = 0  # Default to 0 if not found
    
    def custom_label(row):
        row_cumsum = row['Cleaned Qty']
        if pd.notnull(row_cumsum) and total_Qty != 0:
            first_diff = total_Qty - row_cumsum
            second_diff = total_Qty - cutoff_cumsum
            final_diff = first_diff - second_diff
            final_diff_percent = (final_diff / total_Qty * 100)
            percent = (row_cumsum / total_Qty * 100)
            if final_diff_percent >= 0:
                return f"{format_in_indian_style(row_cumsum)} ({final_diff_percent:.1f}%)"
            else:
                return f"{format_in_indian_style(row_cumsum)}"
        return "0 (0%)"

    # new_data_df['Nse Bse Cumulative Qty'] = new_data_df['Cleaned Qty'].apply(
    #     lambda x: f"({(x / total_Qty * 100):.1f}%){int(x)}(%)" if pd.notnull(x) and total_Qty != 0 else "0 (0%)"
    # )
    new_data_df['Nse Bse Cumulative Qty'] = new_data_df.apply(custom_label, axis=1)
    new_data_df.drop(columns=['Cleaned Qty'], inplace=True)
    new_data_df = new_data_df.sort_values(by='price', ascending=True)
    new_data_df.drop(columns=['Total Qty'], inplace=True)
    htmlTable = new_data_df.to_html(index=False, table_id="liveTable", classes="display")
    
    return prize ,cutprice, current_time, total_bse, total_nse, total_all,top_10, AvgToTheCompany ,htmlTable,nse_ytbc_qty,Data_df

#LOGIN ROUTES
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM ClientDetail WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        
        if user:
            if user['role'] != 'admin':
                # Check ExpiryDate
                if user['ExpiryDate']:
                    try:
                        expiry = datetime.strptime(user['ExpiryDate'], '%Y-%m-%d').date()
                        if datetime.now().date() > expiry:
                            return render_template('login.html', error='Your account has expired. Please contact the administrator.')
                    except ValueError:
                        pass
                
                # Check Status
                if user['Status'] != 'Active':
                    return render_template('login.html', error='Your account is not active.')

            session['user_id'] = user['ID']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid Credentials. Please try again.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        conn = get_db_connection()
        user = conn.execute('SELECT role FROM ClientDetail WHERE id = ?', (session['user_id'],)).fetchone()
        conn.close()
        if not user or user['role'] != 'admin':
            return "Unauthorized. Admin access required.", 403
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin')
@admin_required
def admin_panel():
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM ClientDetail').fetchall()
    ofs_list = conn.execute('SELECT * FROM OFSDetail').fetchall()
    conn.close()
    return render_template('admin.html', users=users, ofs_list=ofs_list)

@app.route('/admin/add_ofs', methods=['POST'])
@admin_required
def add_ofs():
    ofs_name = request.form['ofs_name']
    nse_url = request.form['nse_url']
    bse_url = request.form['bse_url']
    floor_price = request.form['floor_price']
    base_quantity = request.form['base_quantity']
    greenShoe_quantity = request.form.get('greenshoe_quantity', 0)
    category = request.form['category']
    symbol = request.form['symbol']
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO OFSDetail (name, nse_url, bse_url, floor_price, base_quantity, greenShoe_quantity, Category, Symbol, Status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active')
    ''', (ofs_name, nse_url, bse_url, floor_price, base_quantity, greenShoe_quantity, category, symbol))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_ofs/<int:id>')
@admin_required
def delete_ofs(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM OFSDetail WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))
    
@app.route('/admin/add_client', methods=['POST'])
@admin_required
def add_client():
    username = request.form['username']
    password = request.form['password']
    client_name = request.form.get('ClientName', '')
    expiry_date = request.form.get('ExpiryDate', None)
    delay_time = request.form.get('DelayTime', 0)
    status = request.form.get('Status', 'Pending')
    
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO ClientDetail (username, password, role, ClientName, ExpiryDate, DelayTime, Status) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (username, password, 'client', client_name, expiry_date, delay_time, status))
        conn.commit()
    except sqlite3.IntegrityError:
        pass # Handle duplicate username silently for now
    finally:
        conn.close()
        
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_client/<int:id>')
@admin_required
def delete_client(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM ClientDetail WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

#RETURN A WEBPAGE WHICH DISPLAYS DATA
@app.route('/')
@login_required
def index():
    conn = get_db_connection()
    active_ofs = conn.execute("SELECT * FROM OFSDetail WHERE status = 'Active'").fetchall()
    user = conn.execute("SELECT role FROM ClientDetail WHERE id = ?", (session['user_id'],)).fetchone()
    conn.close()
    return render_template('dashboard.html', ofs_list=active_ofs, role=user['role'])

@app.route('/ofs/<int:id>')
@login_required
def view_ofs(id):
    session['current_ofs_id'] = id
    read_file(id)
    contex = {
        'category': category,
        'ofs_id': id
    }
    return render_template('a.html', **contex)

def format_indian_number(n):
    # Manually format for systems that may not support 'en_IN' (like Windows)
    s = str(n)
    if len(s) <= 3:
        return s
    else:
        return s[-3:] if len(s) <= 3 else ','.join([s[:-3][::-1][i:i+2][::-1] for i in range(0, len(s[:-3]), 2)][::-1]) + ',' + s[-3:]

ui_font = ("Calibri", 14)
tk_root = None
tree= None
last_updated_label = None

def open_tkinter_screen(data):
    global tk_root, tree,last_updated_label

    def create_window():
        global tk_root, tree,last_updated_label
        tk_root = tk.Tk()
        tk_root.title("Top 10 Qty and Strike Price Above Cut-off")
        
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(family=ui_font[0], size=ui_font[1])
        tk_root.option_add("*Font", ui_font)
        
        top_frame = tk.Frame(tk_root)
        top_frame.pack(fill="x")

        # Empty space on the left (optional)
        tk.Label(top_frame, text="").pack(side="left", expand=True)
        last_updated_label = tk.Label(top_frame, text="Last Updated: --")
        last_updated_label.pack(side="right")
        
        style = ttk.Style()
        style.configure("Treeview.Heading", font=("Arial", 14, "bold"))
        
        # Customize row appearance
        style.configure("Treeview",
            font=("Arial", 12),
            rowheight=28,
            bordercolor="black",
            borderwidth=1
        )

        # Add border to each row (like a table look)
        style.map("Treeview",
            background=[("selected", "#ececec")],
            foreground=[("selected", "black")]
        )
        
        tree = ttk.Treeview(tk_root, columns=("Price", "Bids", "Qty"), show="headings")
        tree.heading("Price", text="Price")
        tree.heading("Bids", text="Bids")
        tree.heading("Qty", text="Qty")
        tree.column("Price", anchor="center")
        tree.column("Bids", anchor="center")
        tree.column("Qty", anchor="center")
        tree.pack(padx=5, pady=5, fill="both", expand=True)

        # Handle window close
        def on_close():
            global tk_root, tree, last_updated_label
            tk_root.destroy()
            tk_root = None
            tree = None
            last_updated_label = None

        tk_root.protocol("WM_DELETE_WINDOW", on_close)
        update_table(data)
        tk_root.mainloop()

    def update_table(data):
        global tree
        if not tree:
            return
        # Clear existing rows
        for row in tree.get_children():
            tree.delete(row)
        # Insert new rows
        for row in data:
            price, bids, qty = row
            try:
                qty = int(qty)
            except ValueError:
                pass  # Skip formatting if not an integer
            formatted_qty = format_indian_number(qty)
            tree.insert("", tk.END, values=(price, bids, formatted_qty))
            
        if last_updated_label:
            last_updated_label.config(text=f"Last Updated: {datetime.now().strftime('%H:%M:%S')}")

    if tk_root is None or not tk_root.winfo_exists():
        # Create a new window
        import threading
        threading.Thread(target=create_window, daemon=True).start()
    else:
        # Update the existing window
        update_table(data)

@app.route("/details", methods=["POST"])
def show_details():
    data = request.form.get("data", "No data")
    data = top_Qtytable
    threading.Thread(target=open_tkinter_screen, args=(data,), daemon=True).start()
    return redirect(url_for("index"))

@app.route('/save-pricing', methods=['POST'])
def save_pricing():
    global existing_data
    category = request.form.get('category')
    base_prices = request.form.getlist('basePrice[]')
    diffs = request.form.getlist('diff[]')
    units = request.form.getlist('unit[]')
    strategies = request.form.getlist('strategy[]')

    # data = []
    conn = dbconnection()
    cursor = conn.cursor()
    cursor.execute("SELECT Conservative, Moderate, Aggressive FROM AutoBiddingLogic WHERE ID = %s", (User_ID,))
    row = cursor.fetchone()
    
    if row:
        conservative_json, moderate_json, aggressive_json = row
        existing_data = {
            "Conservative": json.loads(conservative_json) if conservative_json else [{}],
            "Moderate": json.loads(moderate_json) if moderate_json else [{}],
            "Aggressive": json.loads(aggressive_json) if aggressive_json else [{}]
        }
    else:
        existing_data = {"Conservative": [{}], "Moderate": [{}], "Aggressive": [{}]}
    
    for i in range(len(strategies)):
        strategy = strategies[i]
        category = category
        base_price = base_prices[i]
        diff = diffs[i]
        unit = units[i]

        if strategy not in existing_data:
            continue

        # Get the first (and only) dict inside the list
        if not existing_data[strategy]:
            existing_data[strategy] = [{}]

        existing_data[strategy][0][category] = {
            "base_price_type": base_price,
            "diff_percent": diff,
            "unit": unit
        }
        
    conservative_json = json.dumps(existing_data["Conservative"])
    moderate_json = json.dumps(existing_data["Moderate"])
    aggressive_json = json.dumps(existing_data["Aggressive"])
    
    
    if row:
        cursor.execute("""
            UPDATE AutoBiddingLogic
            SET Conservative = %s,
                Moderate = %s,
                Aggressive = %s
            WHERE ID = %s
        """, (conservative_json, moderate_json, aggressive_json, User_ID))
    else:
        cursor.execute("""
            INSERT INTO AutoBiddingLogic (ID, Conservative, Moderate, Aggressive)
            VALUES (%s, %s, %s, %s)
        """, (User_ID, conservative_json, moderate_json, aggressive_json))

    conn.commit()
    # cursor.close()

    return jsonify({"status": "success", "message": "Pricing saved"})

#RETURN JSON DATA FOR API CALLS FROM FRONTEND
@app.route('/data', methods=['GET'])
def get_data():
    read_file(session.get('current_ofs_id', 1))
    global top_Qtytable,excel_file_Df,Old_conservative,Old_moderate,Old_aggressve,O_Category,last_Dd_value,last_radio_btn,last_price,last_quan_nse,last_quan_bse,timee_all,Old_bse_time,Bse_ytbc_Qty,timee_bse,timee_nse,base_quantity,greenShoe_quantity,floor_price,symbol,aggressve,moderate,conservative,withoutghq,cutprice,Old_bse_df,Old_nse_df,bse_lastupdate,Old_radio_btn,ltp_sym,update_lock
    
    # acquired = update_lock.acquire(blocking=False)
    
    if not update_lock.acquire(blocking=False):
        return jsonify({'status': 'busy'})
    try:
        excel_filepath = r'Ofs Bidding\Ofs_Upload.xlsx'
        
        with open("pricing_config.json") as f:
            config = json.load(f)
        
        
        modified = False
        
        radio_btn = request.args.get('cutoff', last_radio_btn)
        DropDown_value = request.args.get('dropdown', last_Dd_value)
        
        if DropDown_value != last_Dd_value and DropDown_value != '' and DropDown_value != None:
            last_Dd_value = DropDown_value
            
        if radio_btn != last_radio_btn and radio_btn != '' and radio_btn != None:
            last_radio_btn = radio_btn
        
        e4_get = float(base_quantity)
        e5_get = float(greenShoe_quantity)
        symbol_get = symbol
        O_Category = category
        
        retailsQty =  int(round(0.1 * (base_quantity + greenShoe_quantity)))
        
        hniQty = int(round(0.9 * (base_quantity + greenShoe_quantity)))
        
        if category =='HNI':
            sum = float(e4_get+e5_get)
            per = float(sum*90/100)
            withoutghq = float(e4_get*90/100)
            # hniQty = 0.9 * (base_quantity + greenShoe_quantity)
        else:
            #RETAILS
            sum = float(e4_get+e5_get)
            per = float(sum*10/100)
            withoutghq = float(e4_get*10/100)
            # retailsQty = 0.1 * (base_quantity + greenShoe_quantity)
        #GET LTP FROM NSE

        if nse_url != '':
            symbol_get = f'{symbol}.NS'
            try:
                nse_df = nse(nse_url)
                if nse_df is not None:
                    Old_nse_df = nse_df
                elif nse_df is None:
                    nse_df = Old_nse_df
            except:
                nse_df = Old_nse_df
        else:
            symbol_get = f'{symbol}.BO'
            nse_df = None
            
        if symbol != '' and symbol != None:
            ltp_sym,ltp_fut = ltp.get_ltp(symbol_get)
            # ltp_sym = '-'
            # ltp_fut = '-'
        else:
            ltp_sym = '-'
            ltp_fut = '-'

        try:
            bse_df,Bse_ytbc_Qty,bse_lastupdate = bse(bse_url,category)

            if bse_df is not None:
                Old_bse_df = bse_df
            elif bse_df is None:
                bse_df = Old_bse_df
        except :
            bse_df = Old_bse_df
            Bse_ytbc_Qty = None
            bse_lastupdate = None
            
        price,cutprice, current_time, totalbse,totalnse,totalall,top_10,AvgToTheCompany,Data_df,Nse_ytbc_QTY,Excel_datadf = analysis(nse_df, bse_df, floor_price , per,(e4_get*90/100))

        if Bse_ytbc_Qty == None or Bse_ytbc_Qty == 'NaN' or Bse_ytbc_Qty == '':
            Bse_ytbc_Qty = 0
        
        Bse_ytbc_Qty = 0 if pd.isna(Bse_ytbc_Qty) else int(Bse_ytbc_Qty)
        ytbc_Qty = int(Nse_ytbc_QTY) + int(Bse_ytbc_Qty)
        
        #CALCULATE DIFFERENCE IN AMOUNT AND PERCENTAGE FROM CUT OFF PRICE and LTP
        try:
            diffinamt = float(ltp_sym) - float(price)
            diffinpercent = (diffinamt*100)/float(ltp_sym)
        except:
            diffinamt = 0
            diffinpercent = 0
        
        ofstime = round((totalall / per),2)
        current_time = datetime.now().time()
        current_time = current_time.strftime("%H:%M:%S")

        target_time = "15:20:00"
        target_time1 = "00:00:00"
        

        # Compare current time with target times
        if current_time < target_time1:
            if (ofstime < 1):
                conservative = floor_price
                moderate = conservative
                aggressve = moderate
            elif (ofstime >= 1):
                if (diffinpercent < 5):
                    conservative = AvgToTheCompany+(AvgToTheCompany*0.5/100)
                    moderate = conservative+(conservative*0.3/100)
                    aggressve = moderate+(moderate*0.3/100)
                elif (diffinpercent >= 5):
                    if (ofstime > 2):
                        conservative = AvgToTheCompany+(AvgToTheCompany*1/100)
                        moderate = conservative+(conservative*0.3/100)
                        aggressve = moderate+(moderate*0.3/100)
                    else:
                        conservative = AvgToTheCompany+(AvgToTheCompany*0.5/100)
                        moderate = conservative+(conservative*0.3/100)
                        aggressve = moderate+(moderate*0.3/100)
                        
                        
        elif current_time >= target_time1:
            if category == 'HNI':
                conservative_cfg = existing_data["Conservative"][0].get("HNI", {})
                moderate_cfg = existing_data["Moderate"][0].get("HNI", {})
                aggressive_cfg = existing_data["Aggressive"][0].get("HNI", {})
            else:
                conservative_cfg = existing_data["Conservative"][0].get("Retail", {})
                moderate_cfg = existing_data["Moderate"][0].get("Retail", {})
                aggressive_cfg = existing_data["Aggressive"][0].get("Retail", {})

            if ofstime < 1:
                conservative = floor_price
                moderate = floor_price
                aggressve = floor_price

            elif ofstime >= 1:
                price = float(price)
                # --- Conservative ---
                if conservative_cfg.get('base_price_type') == 'cutoff':
                    if conservative_cfg.get('unit') == 'rupees':
                        conservative = price + float(conservative_cfg['diff_percent'])
                    else:
                        conservative = price + (price * float(conservative_cfg['diff_percent']) / 100)
                elif conservative_cfg.get('base_price_type') == 'indicative':
                    if conservative_cfg.get('unit') == 'rupees':
                        conservative = AvgToTheCompany + float(conservative_cfg['diff_percent'])
                    else:
                        conservative = AvgToTheCompany + (AvgToTheCompany * float(conservative_cfg['diff_percent']) / 100)
                else:
                    conservative = AvgToTheCompany

                # --- Moderate ---
                if moderate_cfg.get('base_price_type') == 'cutoff':
                    if moderate_cfg.get('unit') == 'rupees':
                        moderate = price + float(moderate_cfg['diff_percent'])
                    else:
                        moderate = price + (price * float(moderate_cfg['diff_percent']) / 100)
                elif moderate_cfg.get('base_price_type') == 'indicative':
                    if moderate_cfg.get('unit') == 'rupees':
                        moderate = AvgToTheCompany + float(moderate_cfg['diff_percent'])
                    else:
                        moderate = AvgToTheCompany + (AvgToTheCompany * float(moderate_cfg['diff_percent']) / 100)
                else:
                    moderate = AvgToTheCompany

                # --- Aggressive ---
                if aggressive_cfg.get('base_price_type') == 'cutoff':
                    if aggressive_cfg.get('unit') == 'rupees':
                        aggressve = price + float(aggressive_cfg['diff_percent'])
                    else:
                        aggressve = price + (price * float(aggressive_cfg['diff_percent']) / 100)
                elif aggressive_cfg.get('base_price_type') == 'indicative':
                    if aggressive_cfg.get('unit') == 'rupees':
                        aggressve = AvgToTheCompany + float(aggressive_cfg['diff_percent'])
                    else:
                        aggressve = AvgToTheCompany + (AvgToTheCompany * float(aggressive_cfg['diff_percent']) / 100)
                else:
                    aggressve = AvgToTheCompany
                
                    
        price = float(price)
        
        if ltp_sym == '-' or ltp_sym == None:
            below_ltp = 0
        else:
            below_ltp = round(ltp_sym * (1-0.005),2)
        
        def round_to_tick(price, tick=TickSize):
            return round(round(price / tick) * tick, 2)
        
        if radio_btn == '':
            pass
        
        if price != last_price:
            last_price = price
            timee_all = datetime.now()
        
        if totalnse != last_quan_nse:
            last_quan_nse = totalnse
            timee_nse = datetime.now()
            directory  = fr'Ofs_dataa/{symbol}'
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            file_name = os.path.join(directory, f"{timestamp}.xlsx")
            if not os.path.exists(directory):
                os.makedirs(directory)
            Excel_datadf.to_excel(file_name, index=False)
        
        if bse_lastupdate is not None:
            Old_bse_time = bse_lastupdate
        else:
            bse_lastupdate = Old_bse_time
            
        if bse_lastupdate == None and  Old_bse_time == None:
            if totalbse != last_quan_bse:
                last_quan_bse = totalbse
                bse_lastupdate = datetime.now()
                timee_bse = bse_lastupdate
                directory  = fr'Ofs_dataa/{symbol}'
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                file_name = os.path.join(directory, f"{timestamp}.xlsx")
                if not os.path.exists(directory):
                    os.makedirs(directory)
                Excel_datadf.to_excel(file_name, index=False)
                
            else:
                try:
                    timee_bse = timee_bse.strftime('%H:%M:%S')
                except:
                    timee_bse = datetime.now().strftime('%I:%M %p')
        else:
            timee_bse = bse_lastupdate
        try:
            #CHECK IF LTP IS GREATER THAN 1% OF CUT OFF PRICE
            if (ltp_sym - price)/ltp_sym > 0.015:
                flagg0 = 1
            else:
                flagg0 = 0
            
            #CHECK IF LTP IS GREATER THAN 1% OF CUT OFF PRICE
            if (ltp_sym - (price+(0.005*price)))/ltp_sym > 0.015:
                flagg1 = 1
            else:
                flagg1 = 0

            #CHECK IF LTP IS GREATER THAN 1% OF CUT OFF PRICE
            if (ltp_sym - (price+(0.01*price)))/ltp_sym > 0.015:
                flagg2 = 1
            else:
                flagg2 = 0

            #CHECK IF LTP IS GREATER THAN 1% OF CUT OFF PRICE
            if (ltp_sym - (price+(0.015*price)))/ltp_sym > 0.015:
                flagg3 = 1
            else:
                flagg3 = 0
            
            #CHECK IF LTP IS GREATER THAN 1% OF CUT OFF PRICE
            if (ltp_sym - (price+(0.0175*price)))/ltp_sym > 0.015:
                flagg4 = 1
            else:
                flagg4 = 0

            #CHECK IF LTP IS GREATER THAN 1% OF CUT OFF PRICE
            if (ltp_sym - (price+(0.02*price)))/ltp_sym > 0.015:
                flagg5 = 1
            else:
                flagg5 = 0
                
            if (ltp_sym - (conservative))/ltp_sym > 0.015:
                flagg6 = 1
            else:
                flagg6 = 0
            
            if (ltp_sym - (moderate))/ltp_sym > 0.015:
                flagg7 = 1
            else:
                flagg7 = 0
                
            if (ltp_sym - (aggressve))/ltp_sym > 0.015:
                flagg8 = 1
            else:
                flagg8 = 0
            
            if e5_get == 0:
                cutprice =  round(price,2)      
            
            if  e5_get != 0:  
                # print((totalall / withoutghq)) 
                if ((totalall / withoutghq)>=1):
                    flagg9 = 1
                else:
                    flagg9 = 0
            else:
                flagg9 = 1
                
        except:
            flagg0 = 0
            flagg1 = 0
            flagg2 = 0
            flagg3 = 0
            flagg4 = 0
            flagg5 = 0
            flagg6 = 0
            flagg7 = 0
            flagg8 = 0
            flagg9 = 1
            cutprice = round(price,2)
        
        if nse_url != '':
            nse_update_time = timee_nse.strftime('%H:%M:%S')
        else:
            nse_update_time = "-"
            
        def parse_time_safe(time_str, fmt):
            try:
                if time_str in ('-', '', None):
                    return None
                return datetime.strptime(time_str, fmt).time()
            except ValueError:
                return None
        
        live_price = round(price,2)
        time1 =  '15:27:00'
        time2 =  '15:28:00'
        time3 =  '15:29:00'
        time4 =  '15:29:30'
        time1_obj = datetime.strptime(time1, '%H:%M:%S').time()
        time2_obj = datetime.strptime(time2, '%H:%M:%S').time()
        time3_obj = datetime.strptime(time3, '%H:%M:%S').time()
        time4_obj = datetime.strptime(time4, '%H:%M:%S').time()
        nse_time_obj = parse_time_safe(nse_update_time, '%H:%M:%S')
        bse_time_obj = parse_time_safe(timee_bse, '%I:%M %p')
        
        if nse_time_obj and bse_time_obj:
            latest_time = max(nse_time_obj, bse_time_obj)
        elif nse_time_obj:
            latest_time = nse_time_obj
        elif bse_time_obj:
            latest_time = bse_time_obj
        else:
            latest_time = None  # Or set a default like time.min
        
        if time1_obj <= latest_time < time2_obj:
            cut_range_1 =  live_price + (live_price*0.0045)
            live_AvgToTheCompany = round(AvgToTheCompany,2)
            cut_range_2 =  live_AvgToTheCompany + (live_AvgToTheCompany*0.0035)
            
        elif time2_obj <= latest_time < time3_obj:
            cut_range_1 =  live_price + (live_price*0.0045)
            live_AvgToTheCompany = round(AvgToTheCompany,2)
            cut_range_2 =  live_AvgToTheCompany + (live_AvgToTheCompany*0.003)
            
        elif time3_obj <= latest_time < time4_obj:
            cut_range_1 =  live_price + (live_price*0.0045)
            live_AvgToTheCompany = round(AvgToTheCompany,2)
            cut_range_2 =  live_AvgToTheCompany + (live_AvgToTheCompany*0.002)
        
        elif latest_time >= time4_obj:
            cut_range_1 =  live_price + (live_price*0.0045)
            live_AvgToTheCompany = round(AvgToTheCompany,2)
            cut_range_2 =  live_AvgToTheCompany  + (live_AvgToTheCompany*0.001)
            
        else:
            cut_range_1 =  live_price + (live_price*0.0095)
            live_AvgToTheCompany = round(AvgToTheCompany,2)
            cut_range_2 =  live_AvgToTheCompany + (live_AvgToTheCompany*0.005)
        
        ofs_time = round((totalall / per),2)
        cut_price = round(price,2)
        # ofs_ltp = round(ltp_sym,2)
        
        cutoff1 = round(price+(0.005*price),2)
        cutoff2 = round(price+(0.01*price),2)
        cutoff3 = round(price+(0.015*price),2)
        cutoff4 = round(price+(0.0175*price),2)
        cutoff5 = round(price+(0.02*price),2)
        
        new_Excel_datadf = Excel_datadf
        new_Excel_datadf = new_Excel_datadf.sort_values(by='price', ascending=False)
        new_Excel_datadf['Nse + Bse No of Bids'] = (
            new_Excel_datadf['Nse + Bse No of Bids']
            .astype(str)                       # Convert to string (in case of mixed types)
            .str.replace(',', '')             # Remove commas
            .astype(int)                      # Convert to integer
        )
        
        new_Excel_datadf['Nse Bse Cumulative Bids'] = new_Excel_datadf['Nse + Bse No of Bids'].cumsum()
        new_Excel_datadf['Cleaned Qty'] = new_Excel_datadf['Nse Bse Cumulative Qty'].str.replace(',', '')
        new_Excel_datadf['Cleaned Qty'] = pd.to_numeric(new_Excel_datadf['Cleaned Qty'], errors='coerce')
        total_Qty = new_Excel_datadf['Cleaned Qty'].iloc[-1]
        total_bids = new_Excel_datadf['Nse + Bse No of Bids'].sum()
        cuttoff_qty =  int(str(new_Excel_datadf.loc[(new_Excel_datadf['price'] - price).abs().idxmin()]['Nse Bse Cumulative Qty']).replace(',', ''))
        cuttoff_bids = int(str(new_Excel_datadf.loc[(new_Excel_datadf['price'] - price).abs().idxmin()]['Nse Bse Cumulative Bids']).replace(',', ''))
        
        def Qty_Per_map(Cum_qty):
            first_diff = total_Qty - Cum_qty
            second_diff = total_Qty - cuttoff_qty
            final_diff = first_diff - second_diff
            final_diff_percent = (final_diff * 100) / total_Qty
            return final_diff_percent
        
        def Bids_Per(Cum_qty,Cum_bids,Cutt_Off_Price):
            CumSum_Qty = Cum_qty
            per = Qty_Per_map(CumSum_Qty)
            first_diff = total_bids - Cum_bids
            second_diff = total_bids - cuttoff_bids
            final_diff = first_diff - second_diff
            final_diff_percent = (final_diff * 100) / total_bids
            return f'{Cutt_Off_Price} <span class="cutoff-details">(Bid:{final_diff_percent:.1f}%) (Sh:{per:.1f}%)</span>'
            # pass
        
        
        def Bids_Per_map(Cum_bids):
            first_diff = total_bids - Cum_bids
            second_diff = total_bids - cuttoff_bids
            final_diff = first_diff - second_diff
            final_diff_percent = (final_diff * 100) / total_bids
            return final_diff_percent
            pass
        
        cuttoff_per_qty = Qty_Per_map(cuttoff_qty)
        cuttoff_bids_per = Bids_Per_map(cuttoff_bids)
        cutoff1_qty =  int(str(new_Excel_datadf.loc[(new_Excel_datadf['price'] - cutoff1).abs().idxmin()]['Nse Bse Cumulative Qty']).replace(',', ''))
        cutoff1_bids = int(str(new_Excel_datadf.loc[(new_Excel_datadf['price'] - cutoff1).abs().idxmin()]['Nse Bse Cumulative Bids']).replace(',', ''))
        cutoff1_bids_per = Bids_Per(cutoff1_qty,cutoff1_bids,cutoff1)
        cutoff2_qty =  int(str(new_Excel_datadf.loc[(new_Excel_datadf['price'] - cutoff2).abs().idxmin()]['Nse Bse Cumulative Qty']).replace(',', ''))
        cutoff2_bids = int(str(new_Excel_datadf.loc[(new_Excel_datadf['price'] - cutoff2).abs().idxmin()]['Nse Bse Cumulative Bids']).replace(',', ''))
        cutoff2_bids_per = Bids_Per(cutoff2_qty,cutoff2_bids,cutoff2)
        cutoff3_qty =  int(str(new_Excel_datadf.loc[(new_Excel_datadf['price'] - cutoff3).abs().idxmin()]['Nse Bse Cumulative Qty']).replace(',', ''))
        cutoff3_bids = int(str(new_Excel_datadf.loc[(new_Excel_datadf['price'] - cutoff3).abs().idxmin()]['Nse Bse Cumulative Bids']).replace(',', ''))
        cutoff3_bids_per = Bids_Per(cutoff3_qty,cutoff3_bids,cutoff3)
        cutoff4_qty =  int(str(new_Excel_datadf.loc[(new_Excel_datadf['price'] - cutoff4).abs().idxmin()]['Nse Bse Cumulative Qty']).replace(',', ''))
        cutoff4_bids = int(str(new_Excel_datadf.loc[(new_Excel_datadf['price'] - cutoff4).abs().idxmin()]['Nse Bse Cumulative Bids']).replace(',', ''))
        cutoff4_bids_per = Bids_Per(cutoff4_qty,cutoff4_bids,cutoff4)
        cutoff5_qty =  int(str(new_Excel_datadf.loc[(new_Excel_datadf['price'] - cutoff5).abs().idxmin()]['Nse Bse Cumulative Qty']).replace(',', ''))
        cutoff5_bids = int(str(new_Excel_datadf.loc[(new_Excel_datadf['price'] - cutoff5).abs().idxmin()]['Nse Bse Cumulative Bids']).replace(',', ''))
        cutoff5_bids_per = Bids_Per(cutoff5_qty,cutoff5_bids,cutoff5)

        conservative_qty = int(str(new_Excel_datadf.loc[(new_Excel_datadf['price'] - conservative).abs().idxmin()]['Nse Bse Cumulative Qty']).replace(',', '')) 
        conservative_bids = int(str(new_Excel_datadf.loc[(new_Excel_datadf['price'] - conservative).abs().idxmin()]['Nse Bse Cumulative Bids']).replace(',', ''))
        conservative_qty_per = Qty_Per_map(conservative_qty)
        conservative_bids_per = Bids_Per_map(conservative_bids)
        
        moderate_qty = int(str(new_Excel_datadf.loc[(new_Excel_datadf['price'] - moderate).abs().idxmin()]['Nse Bse Cumulative Qty']).replace(',', ''))
        moderate_bids = int(str(new_Excel_datadf.loc[(new_Excel_datadf['price'] - moderate).abs().idxmin()]['Nse Bse Cumulative Bids']).replace(',', ''))
        moderate_qty_per = Qty_Per_map(moderate_qty)
        moderate_bids_per = Bids_Per_map(moderate_bids)
        
        aggressive_qty = int(str(new_Excel_datadf.loc[(new_Excel_datadf['price'] - aggressve).abs().idxmin()]['Nse Bse Cumulative Qty']).replace(',', ''))
        aggressive_bids = int(str(new_Excel_datadf.loc[(new_Excel_datadf['price'] - aggressve).abs().idxmin()]['Nse Bse Cumulative Bids']).replace(',', ''))
        aggressive_qty_per = Qty_Per_map(aggressive_qty)
        aggressive_bids_per = Bids_Per_map(aggressive_bids)
        
        AdditionalQty = round(totalall,2) - per
        if AdditionalQty >= 0 :
            AdditionalQty = AdditionalQty
        else :
            AdditionalQty = 0
        
        top_qty_data = {}
        top_Qtytable = list(zip(top_10['price'].astype(float), top_10['Total Qty']))
        for idx, (top_price, qty) in enumerate(top_Qtytable[:3]):
            suffix = '' if idx == 0 else str(idx)
            top_qty_data[f"max_all_price{suffix}"] = round(top_price, 2)
            top_qty_data[f"max_all_quan{suffix}"] = round(qty, 2)
        
        #RETURN JSON DATA TO FRONTEND
        data = {
            'ofsName': ofs_name,
            'modified': modified,
            # "modify_cut_price": modify_cut_price,
            'category':category,
            'Rtime' : Rtime,
            'price': round(price,2),
            'Ytbc_Qty': ytbc_Qty,
            'time': current_time,
            'ofstimes': round((totalall / per),2),
            'withoutghq':round((totalall / withoutghq),2),
            'total_quantity': round(totalall,2),
            'floor_price': floor_price,
            'cutprice': cutprice,
            'Data_df': Data_df,
            'base_quantity': base_quantity,
            'greenShoe_quantity': greenShoe_quantity,
            'LTP' : round(float(ltp_sym), 2) if ltp_sym != '-' else '-',
            "Diff_in_Amount" : round(diffinamt,2),
            "Diff_in_Percent" : round(diffinpercent,2),
            "cutoff1" : cutoff1_bids_per,
            "cutoff2" : cutoff2_bids_per, 
            "cutoff3" : cutoff3_bids_per,
            "cutoff4" : cutoff4_bids_per,
            "cutoff5" : cutoff5_bids_per,
            "max_all_quan" : top_qty_data.get('max_all_quan', 0),
            "max_all_price" : top_qty_data.get('max_all_price', 0),
            "max_all_quan1": top_qty_data.get('max_all_quan1', 0),
            "max_all_price1": top_qty_data.get('max_all_price1', 0),
            "max_all_quan2": top_qty_data.get('max_all_quan2', 0),
            "max_all_price2": top_qty_data.get('max_all_price2', 0),
            "last_price_change": timee_all.strftime('%H:%M:%S'),
            "last_price_change_nse": nse_update_time,
            "last_price_change_bse": timee_bse,
            "flagg0" : flagg0,
            "flagg1" : flagg1,
            "flagg2" : flagg2,
            "flagg3" : flagg3,
            "flagg4" : flagg4,
            "flagg5" : flagg5,
            "flagg6" : flagg6,
            "flagg7" : flagg7,
            "flagg8" : flagg8,
            "flagg9" : flagg9,
            "ltp_fut" : ltp_fut,
            "AvgToTheCompany" : round(AvgToTheCompany,2),
            "conservative" : round(conservative,2),
            "moderate" : round(moderate,2),
            "aggressve" : round(aggressve,2),
            'cut_range_1': round(cut_range_1,2),
            'cut_range_2': round(cut_range_2,2),
            # 'dropdown': dropdown_value,
            # 'radio_button': radio_btn,
            # 'Modify_price': modify_price
            'cuttoff_qty_per':round(cuttoff_per_qty,2),
            'cuttoff_bids_per':round(cuttoff_bids_per,2),
            'conservative_qty_per':round(conservative_qty_per,2),
            'moderate_qty_per':round(moderate_qty_per,2),
            'aggressve_qty_per':round(aggressive_qty_per,2),
            'conservative_bids_per':round(conservative_bids_per,2),
            'moderate_bids_per':round(moderate_bids_per,2),
            'aggressve_bids_per':round(aggressive_bids_per,2),
            'Price_config': existing_data,
        }
        
        if modified:
            data['modify_cut_price'] = modify_cut_price
        
        if category == 'HNI':
            available_quantity = totalall - (hniQty)
        else:
            available_quantity = totalall - (retailsQty)
        
        if available_quantity < 0:
            available_quantity = 0
        
        top_Qtytable = list(zip(top_10['price'].astype(float),top_10['Nse + Bse No of Bids'],top_10['Total Qty']))
        
        
        if tk_root is None or not tk_root.winfo_exists():
            print("Tkinter window is not open")
        else:
            open_tkinter_screen(top_Qtytable)
        
        return jsonify(data)
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)})
    
    finally:
        # if acquired:
            update_lock.release()

@app.route('/Ofs_Data')
def get_OfsDetails():
    Ofs_data = {
       "Historical_OFS_Data" : Historical_OFS_Data, 
    }
    
    return jsonify(Ofs_data)
# #RUN THE WEBSITE ON LOCALHOST

@app.route('/ofsbid', methods=['POST'])
def submit_form():
    global excel_file_Df,Csv_dataDf,excel_filepath,Csv_filepath,ltp_sym
    # if request.method == 'POST':
    def round_to_tick(price, tick=TickSize):
        return round(round(price / tick) * tick, 2)
    
    # below_ltp = round(ltp_sym *(1-0.005),2)
    
    M_Price = request.form.get('Modify_price')
    if M_Price == None and M_Price == '':
        Price = float(last_price)
    else:
        Price = float(M_Price)
        
    dropdown = request.form.get('dropdown')
    radio_button = 'radio_PriceModify'
    file = request.files['csv_file']
    
    # if Price > below_ltp:
    #     Price = below_ltp
    
    Price = round_to_tick(Price)
    
    if file and file.filename.endswith(('.xls', '.xlsx')):
        Up_filename = 'Ofs_Upload.xlsx'  
        excel_filepath = os.path.join(UPLOAD_FOLDER,Up_filename)
        file.save(excel_filepath)
        
        if category == 'HNI':
            S_category = 'NII'
        elif category == 'Retail':
            S_category = 'RI'
        
        excel_file_Df = pd.read_excel(excel_filepath)
            
        excel_df_len = len(excel_file_Df)
        
        Csv_file_convert  = {
            "OFS Symbol": [symbol] * excel_df_len,
            "Category": [S_category] * excel_df_len,
            "Client/CP Code": [None] * excel_df_len,
            "UCC": excel_file_Df["TradingCode"],
            "Custody Code": [None] * excel_df_len,
            "Qty": excel_file_Df["Quantity"],
            "Price": [last_price] * excel_df_len,
            "Margin Type": ['2'] * excel_df_len,
            "Bid Id": ['0'] * excel_df_len,
            "Action Code": ['N'] * excel_df_len,
        }
        Csv_dataDf = pd.DataFrame(Csv_file_convert)
        Csv_filepath = os.path.join(UPLOAD_FOLDER,'Ofs_Upload.csv')
        Csv_dataDf.to_csv(Csv_filepath, index=False,header=False)
        
    else:
        excel_filepath = f'{base_dir}\Ofs Bidding\Ofs_Upload.xlsx'
        Csv_filepath = f'{base_dir}\Ofs Bidding\Ofs_Upload.csv'
    
    excel_file_Df = pd.read_excel(excel_filepath)
    Csv_dataDf = pd.read_csv(Csv_filepath,index_col=False,header=None)

    if M_Price != '':
        if excel_file_Df is not None and isinstance(excel_file_Df, pd.DataFrame):
            if excel_file_Df['BID ID'].isna().any():
                excel_file_Df = pd.DataFrame(excel_file_Df)
                if dropdown == 'Normal_BseBid':
                    Bse_ofsbid.Ofs_bid(Company_Id,Price_Alert,Qty_Alert,Price,O_Category,floor_price,excel_file_Df,excel_filepath,Csv_filepath)
                elif dropdown == 'Async_BseBid':
                    asyncio.run(async_OfsBid.Place_OfsBid(Company_Id,Price_Alert,Qty_Alert,Price,O_Category,floor_price,excel_file_Df,excel_filepath,Csv_filepath))
            if dropdown == 'Normal_BseBid' :
                Bse_Ofsmodify.modify_ofsbid(Price,O_Category,floor_price,excel_file_Df,excel_filepath)
            elif dropdown == 'Async_BseBid' :
                asyncio.run(async_Ofsmodify.Order_OfsModify(Price,O_Category,floor_price,excel_file_Df,excel_filepath))
        else:
            print("No Data is Excel file")
        if Csv_dataDf is not None and isinstance(Csv_dataDf, pd.DataFrame):
            col8 = Csv_dataDf.iloc[:, 8]
            if ((col8 == 0) | (col8 == '0')).all():
                Csv_dataDf.iloc[:, 9] = 'N'
            else:
                Csv_dataDf.iloc[:, 9] = 'M'
                
            if dropdown == 'Csv_100upload' :
                Bse_Ofscsvupload.upload100records_file(Price,O_Category,Csv_dataDf,Csv_filepath)
            elif dropdown == 'Csv_1000upload' :
                Bse_Ofs1000recordCSVupload.upload_1000recordsfile(Price,O_Category,Csv_dataDf,Csv_filepath)
        else:
            print("No Data is Csv file")
    # return render_template('a.html', Modify_price=Price, dropdown=dropdown, radio_button=radio_button)
    data = {
        "status": "success",
        "message": "Bids submitted successfully",
        "price": Price,
        "dropdown": dropdown,
    }
    return jsonify(data)

@app.route('/cancel-order')
def Cancel_order():
    Price = last_price
    if last_Dd_value == 'Normal_BseBid': 
        if excel_file_Df is not None and isinstance(excel_file_Df, pd.DataFrame):
            Bse_Ofscancel.Cancel_Ofsbid(Price,O_Category,floor_price,excel_file_Df,excel_filepath)
    elif last_Dd_value == 'Async_BseBid':
        if excel_file_Df is not None and isinstance(excel_file_Df, pd.DataFrame):
            async_Ofscancel.Cancel_Ofsbid(Price,O_Category,floor_price,excel_file_Df,excel_filepath)
        
    elif last_Dd_value == 'Csv_100upload':
        if Csv_dataDf is not None and isinstance(Csv_dataDf, pd.DataFrame):
            if Csv_dataDf.iloc[:, 8] != 0 and Csv_dataDf.iloc[:, 8] != '0'  and Csv_dataDf.iloc[:, 8] != '' :
                Csv_dataDf.iloc[:, 9] = 'D'    
            Bse_Ofscsvupload.upload100records_file(Price,O_Category,Csv_dataDf,Csv_filepath)
            
    elif last_Dd_value == 'Csv_1000upload':
        if Csv_dataDf is not None and isinstance(Csv_dataDf, pd.DataFrame):
            if Csv_dataDf.iloc[:, 8] != 0 and Csv_dataDf.iloc[:, 8] != '0'  and Csv_dataDf.iloc[:, 8] != '' :
                Csv_dataDf.iloc[:, 9] = 'D'    
            Bse_Ofs1000recordCSVupload.upload_1000recordsfile(Price,O_Category,Csv_dataDf,Csv_filepath)
    
    return redirect("/")

if __name__ == '__main__':
    app.run(host="0.0.0.0")