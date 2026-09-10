# database.py
import sqlite3
import secrets
import string
from datetime import datetime, timedelta

class Database:
    def __init__(self, db_path='ketrika.db'):
        self.db_path = db_path
    
    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        conn = self.get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_key TEXT UNIQUE NOT NULL,
                pack_id INTEGER NOT NULL,
                router_serial TEXT DEFAULT NULL,
                is_activated INTEGER DEFAULT 0,
                activated_at TEXT DEFAULT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT DEFAULT NULL,
                usage_count INTEGER DEFAULT 0,
                max_usage INTEGER DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS generations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_key TEXT NOT NULL,
                pack_id INTEGER NOT NULL,
                config_hash TEXT,
                generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                router_identity TEXT
            )
        ''')
        
        # 🔑 CLÉS DE TEST INSÉRÉES AUTOMATIQUEMENT
        test_keys = [
            ('KM-CL-TEST-1111-2222', 1),
            ('KM-WP-TEST-3333-4444', 2),
            ('KM-HP-TEST-5555-6666', 3),
        ]
        
        for key, pack_id in test_keys:
            cursor.execute('SELECT id FROM licenses WHERE license_key = ?', (key,))
            if not cursor.fetchone():
                expires_at = (datetime.now() + timedelta(days=365)).isoformat()
                cursor.execute('''
                    INSERT INTO licenses (license_key, pack_id, expires_at, is_activated)
                    VALUES (?, ?, ?, 0)
                ''', (key, pack_id, expires_at))
        
        conn.commit()
        conn.close()


class LicenseManager:
    def __init__(self, db: Database):
        self.db = db
    
    def generate_license(self, pack_id, valid_days=365):
        prefix = {1: 'KM-CL', 2: 'KM-WP', 3: 'KM-HP'}
        pack_prefix = prefix.get(pack_id, 'KM-XX')
        
        chars = string.ascii_uppercase + string.digits
        part1 = ''.join(secrets.choice(chars) for _ in range(4))
        part2 = ''.join(secrets.choice(chars) for _ in range(4))
        part3 = ''.join(secrets.choice(chars) for _ in range(4))
        
        license_key = f"{pack_prefix}-{part1}-{part2}-{part3}"
        expires_at = (datetime.now() + timedelta(days=valid_days)).isoformat()
        
        conn = self.db.get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO licenses (license_key, pack_id, expires_at)
            VALUES (?, ?, ?)
        ''', (license_key, pack_id, expires_at))
        conn.commit()
        conn.close()
        
        return license_key
    
    def activate_license(self, license_key, router_serial):
        license_key = license_key.strip().upper()
        router_serial = router_serial.strip()
        
        conn = self.db.get_conn()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
        lic = cursor.fetchone()
        
        if not lic:
            conn.close()
            return {'success': False, 'message': 'Clé invalide ou inexistante !'}
        
        if lic['is_activated'] and lic['router_serial'] and lic['router_serial'] != router_serial:
            conn.close()
            return {
                'success': False, 
                'message': 'Cette clé est déjà utilisée sur un autre routeur !'
            }
        
        cursor.execute('''
            UPDATE licenses 
            SET is_activated = 1, 
                router_serial = ?,
                activated_at = ?
            WHERE license_key = ?
        ''', (router_serial, datetime.now().isoformat(), license_key))
        
        conn.commit()
        conn.close()
        
        return {
            'success': True, 
            'pack_id': lic['pack_id'],
            'message': 'Licence activée avec succès !'
        }
