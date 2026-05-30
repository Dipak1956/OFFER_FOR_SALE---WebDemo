import re

with open('ofs.py', 'r') as f:
    content = f.read()

# 1. Update login route
login_old = """@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM Users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid Credentials. Please try again.')
    return render_template('login.html')"""

login_new = """@app.route('/login', methods=['GET', 'POST'])
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
    return render_template('login.html')"""

content = content.replace(login_old, login_new)

# 2. Update Users to ClientDetail globally for other queries
content = content.replace('SELECT role FROM Users', 'SELECT role FROM ClientDetail')
content = content.replace("conn.execute('SELECT * FROM Users').fetchall()", "conn.execute('SELECT * FROM ClientDetail').fetchall()")
content = content.replace('DELETE FROM Users', 'DELETE FROM ClientDetail')

# 3. Update add_client
add_client_old = """@app.route('/admin/add_client', methods=['POST'])
@admin_required
def add_client():
    username = request.form['username']
    password = request.form['password']
    
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO Users (username, password, role) VALUES (?, ?, ?)', (username, password, 'client'))
        conn.commit()
    except sqlite3.IntegrityError:
        pass # Handle duplicate username silently for now
    finally:
        conn.close()
        
    return redirect(url_for('admin'))"""

add_client_new = """@app.route('/admin/add_client', methods=['POST'])
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
        
    return redirect(url_for('admin'))"""

content = content.replace(add_client_old, add_client_new)

# 4. Update add_ofs
add_ofs_old = """@app.route('/admin/add_ofs', methods=['POST'])
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
        INSERT INTO OFSDetail (ofs_name, nse_url, bse_url, floor_price, base_quantity, greenshoe_quantity, category, symbol)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (ofs_name, nse_url, bse_url, floor_price, base_quantity, greenShoe_quantity, category, symbol))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))"""

add_ofs_new = """@app.route('/admin/add_ofs', methods=['POST'])
@admin_required
def add_ofs():
    name = request.form['ofs_name']
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
    ''', (name, nse_url, bse_url, floor_price, base_quantity, greenShoe_quantity, category, symbol))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))"""

content = content.replace(add_ofs_old, add_ofs_new)

with open('ofs.py', 'w') as f:
    f.write(content)

print("Backend patched.")
