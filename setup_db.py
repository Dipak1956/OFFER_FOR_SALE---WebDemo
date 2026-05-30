import sqlite3
import os

def init_db():
    if os.path.exists('database.db'):
        os.remove('database.db')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Create ClientDetail table (Replaces 'Users')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ClientDetail (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'client',
            ClientName TEXT,
            ClientDescription TEXT,
            ExpiryDate DATE,
            DelayTime INTEGER DEFAULT 0,
            Status TEXT DEFAULT 'Pending',
            AdvancedPrice TEXT
        )
    ''')

    # Create OFSDetail table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS OFSDetail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            nse_url TEXT,
            bse_url TEXT,
            floor_price REAL,
            base_quantity INTEGER,
            greenShoe_quantity INTEGER DEFAULT 0,
            Category TEXT,
            Symbol TEXT,
            Status TEXT DEFAULT 'Pending'
        )
    ''')

    # Create AutoBiddingLogic table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS AutoBiddingLogic (
            AutoBidding_Id INTEGER PRIMARY KEY AUTOINCREMENT,
            ID INTEGER,
            Conservative TEXT,
            Moderate TEXT,
            Aggressive TEXT
        )
    ''')
    
    # Create ClientLog table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ClientLog (
            LogId INTEGER PRIMARY KEY AUTOINCREMENT,
            ClientID INTEGER,
            LogText TEXT,
            Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create OfsAutoBidding table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS OfsAutoBidding (
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            OfsId INTEGER,
            BidDetails TEXT
        )
    ''')

    # Create PastOfsDetail table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS PastOfsDetail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            Category TEXT,
            Symbol TEXT
        )
    ''')

    # Insert default admin user if not exists
    cursor.execute('''
        INSERT OR IGNORE INTO ClientDetail (username, password, role, ClientName, Status, ExpiryDate)
        VALUES ('admin', 'password123', 'admin', 'System Administrator', 'Active', NULL)
    ''')

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == '__main__':
    init_db()
    print("Database recreated with Users and OFSDetail tables.")
