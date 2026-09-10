# database.py
import sqlite3
import secrets
import string
import hashlib
import time
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
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT UNIQUE,
                pack_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                phone TEXT,
                status TEXT DEFAULT 'pending',
                license_key TEXT DEFAULT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Base de données initialisée")


class LicenseManager:
    def __init__(self, db: Database):
        self.db = db
    
    def generate_license(self, pack_id, valid_days=365):
        """Génère une clé de licence unique"""
        prefix = {1: 'KM-CL', 2: 'KM-WP', 3: 'KM-HP'}
        pack_prefix = prefix.get(pack_id, 'KM-XX')
        
        chars = string.ascii_uppercase + string.digits
        key_parts = []
        for _ in range(3):
            part = ''.join(secrets.choice(chars) for _ in range(4))
            key_parts.append(part)
        
        license_key = f"{pack_prefix}-{''.join(key_parts[0])}-{''.join(key_parts[1])}-{''.join(key_parts[2])}"
        
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
        """Active une licence pour un routeur spécifique"""
        conn = self.db.get_conn()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
        lic = cursor.fetchone()
        
        if not lic:
            conn.close()
            return {'success': False, 'message': 'Clé invalide'}
        
        if lic['is_activated'] and lic['router_serial'] != router_serial:
            conn.close()
            return {
                'success': False, 
                'message': 'Cette clé est déjà liée à un autre routeur'
            }
        
        if lic['expires_at']:
            expires = datetime.fromisoformat(lic['expires_at'])
            if datetime.now() > expires:
                conn.close()
                return {'success': False, 'message': 'Clé expirée'}
        
        # Activer ou réactiver
        if not lic['is_activated']:
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
            'message': 'Licence activée avec succès'
        }
    
    def check_license(self, license_key):
        """Vérifie le statut d'une licence"""
        conn = self.db.get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
        lic = cursor.fetchone()
        conn.close()
        
        if not lic:
            return {'valid': False, 'message': 'Clé introuvable'}
        
        return {
            'valid': True,
            'pack_id': lic['pack_id'],
            'is_activated': bool(lic['is_activated']),
            'router_serial': lic['router_serial'],
            'created_at': lic['created_at'],
            'expires_at': lic['expires_at']
        }
    
    def log_generation(self, license_key, pack_id, config_hash, router_identity):
        """Log chaque génération de script"""
        conn = self.db.get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO generations (license_key, pack_id, config_hash, router_identity)
            VALUES (?, ?, ?, ?)
        ''', (license_key, pack_id, config_hash, router_identity))
        
        cursor.execute('''
            UPDATE licenses SET usage_count = usage_count + 1 
            WHERE license_key = ?
        ''', (license_key,))
        
        conn.commit()
        conn.close()