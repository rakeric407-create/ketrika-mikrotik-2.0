# -*- coding: utf-8 -*-
"""
KETRIKA MIKROTIK v3.0.1 - Module base de données
Gère les modèles, commandes, licences et utilitaires
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import secrets
import random
import json

db = SQLAlchemy()


# ============================================================
# MODÈLE ORDER : commande client complète
# ============================================================
class Order(db.Model):
    """Représente une commande complète avec tous les paramètres de configuration"""
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    license_key = db.Column(db.String(64), unique=True, nullable=False, index=True)

    # Informations client
    client_name = db.Column(db.String(120), nullable=False)
    whatsapp_number = db.Column(db.String(30), nullable=False)

    # Plan choisi : essentiel / performance / business
    plan_type = db.Column(db.String(20), nullable=False)

    # Matériel
    mikrotik_model = db.Column(db.String(80), nullable=False)
    router_name = db.Column(db.String(80), nullable=False)

    # Wi-Fi
    ssid_2g = db.Column(db.String(64), default="")
    ssid_5g = db.Column(db.String(64), default="")
    wifi_password = db.Column(db.String(64), default="")

    # Réseau LAN / WAN
    wan_interface = db.Column(db.String(30), default="ether1")
    lan_gateway = db.Column(db.String(30), default="192.168.10.1")
    lan_network = db.Column(db.String(30), default="192.168.10.0/24")
    dhcp_pool_start = db.Column(db.String(30), default="192.168.10.10")
    dhcp_pool_end = db.Column(db.String(30), default="192.168.10.250")

    # Options avancées (plan performance + business)
    ttl_value = db.Column(db.Integer, default=0)
    mac_spoof = db.Column(db.Boolean, default=False)
    mac_address = db.Column(db.String(30), default="")

    # Limites de débit (en Mbps, 0 = illimité)
    dl_limit = db.Column(db.Integer, default=0)
    ul_limit = db.Column(db.Integer, default=0)
    client_limit = db.Column(db.Integer, default=0)

    # Mise en veille Wi-Fi
    sleep_mode = db.Column(db.String(30), default="off")
    sleep_start = db.Column(db.String(10), default="")
    sleep_end = db.Column(db.String(10), default="")

    # Hotspot (plan business uniquement)
    hotspot_tickets_count = db.Column(db.Integer, default=0)
    hotspot_profiles = db.Column(db.Text, default="[]")

    # Paiement et statut
    payment_status = db.Column(db.String(20), default="pending")
    payment_amount = db.Column(db.Integer, default=0)

    # Dates
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    validated_at = db.Column(db.DateTime, nullable=True)

    # Acceptation des conditions
    terms_accepted = db.Column(db.Boolean, default=False)


# ============================================================
# GÉNÉRATION DE CLÉ DE LICENCE UNIQUE
# ============================================================
def generate_license_key():
    """Génère une clé unique au format LIC-XXXXXXXXXXXXXXXX (32 caractères hex)"""
    return "LIC-" + secrets.token_hex(16).upper()


# ============================================================
# NOM AUTOMATIQUE DU ROUTEUR
# ============================================================
def generate_router_name(license_key):
    """Crée un nom court à partir de la licence : KETRIKA-XXXX"""
    suffix = license_key.replace("LIC-", "")[:6]
    return "KETRIKA-" + suffix


# ============================================================
# ADRESSE MAC ALÉATOIRE (style téléphone Android)
# ============================================================
def generate_random_mac():
    """Génère une MAC aléatoire avec OUI de constructeurs courants"""
    prefixes = [
        "00:12:FB", "AC:37:43", "F0:25:B7",  # Samsung
        "34:CE:00", "00:1B:B1", "28:6C:07",  # Xiaomi
        "A4:77:33", "70:3A:CB", "E8:61:7E",  # Huawei
    ]
    oui = random.choice(prefixes)
    tail = ":".join(f"{random.randint(0, 255):02X}" for _ in range(3))
    return f"{oui}:{tail}"


# ============================================================
# BASE DE DONNÉES COMPLÈTE DES MODÈLES MIKROTIK
# ============================================================
MIKROTIK_MODELS = {
    # ---------- hAP série (avec Wi-Fi) ----------
    "hap_lite": {
        "name": "hAP lite (RB941-2nD)",
        "ports": 4,
        "wifi_24ghz": True,
        "wifi_5ghz": False,
        "wifi_type": "n",
        "description": "4 ports, Wi-Fi 2.4GHz N",
    },
    "hap": {
        "name": "hAP (RB951Ui-2nD)",
        "ports": 5,
        "wifi_24ghz": True,
        "wifi_5ghz": False,
        "wifi_type": "n",
        "description": "5 ports, Wi-Fi 2.4GHz N",
    },
    "hap_ac_lite": {
        "name": "hAP ac lite (RB952Ui-5ac2nD)",
        "ports": 5,
        "wifi_24ghz": True,
        "wifi_5ghz": True,
        "wifi_type": "ac",
        "description": "5 ports, Wi-Fi 2.4GHz N + 5GHz AC",
    },
    "hap_ac2": {
        "name": "hAP ac² (RB962UiGS-5HacT2HnT)",
        "ports": 5,
        "wifi_24ghz": True,
        "wifi_5ghz": True,
        "wifi_type": "ac",
        "description": "5 ports Gigabit, Wi-Fi 2.4GHz + 5GHz AC",
    },
    "hap_ac3": {
        "name": "hAP ac³",
        "ports": 5,
        "wifi_24ghz": True,
        "wifi_5ghz": True,
        "wifi_type": "ac",
        "description": "5 ports Gigabit, Wi-Fi 2.4GHz + 5GHz AC",
    },
    "hap_ax2": {
        "name": "hAP ax²",
        "ports": 5,
        "wifi_24ghz": True,
        "wifi_5ghz": True,
        "wifi_type": "ax",
        "description": "5 ports Gigabit, Wi-Fi 6 AX Dual-Band",
    },
    "hap_ax3": {
        "name": "hAP ax³",
        "ports": 5,
        "wifi_24ghz": True,
        "wifi_5ghz": True,
        "wifi_type": "ax",
        "description": "5 ports Gigabit, Wi-Fi 6 AX Dual-Band",
    },
    "hap_ax_lite": {
        "name": "hAP ax lite",
        "ports": 4,
        "wifi_24ghz": True,
        "wifi_5ghz": False,
        "wifi_type": "ax",
        "description": "4 ports, Wi-Fi 6 AX 2.4GHz",
    },

    # ---------- RB série (sans Wi-Fi) ----------
    "rb750gr3": {
        "name": "RB750Gr3 (hEX)",
        "ports": 5,
        "wifi_24ghz": False,
        "wifi_5ghz": False,
        "wifi_type": None,
        "description": "5 ports Gigabit, sans Wi-Fi",
    },
    "rb750r2": {
        "name": "RB750r2 (hEX lite)",
        "ports": 5,
        "wifi_24ghz": False,
        "wifi_5ghz": False,
        "wifi_type": None,
        "description": "5 ports 100Mbps, sans Wi-Fi",
    },
    "rb760igs": {
        "name": "RB760iGS (hEX S)",
        "ports": 5,
        "wifi_24ghz": False,
        "wifi_5ghz": False,
        "wifi_type": None,
        "description": "5 ports Gigabit + SFP, sans Wi-Fi",
    },
    "rb4011": {
        "name": "RB4011iGS+",
        "ports": 10,
        "wifi_24ghz": False,
        "wifi_5ghz": False,
        "wifi_type": None,
        "description": "10 ports Gigabit + SFP+, sans Wi-Fi",
    },
    "rb5009": {
        "name": "RB5009UG+S+",
        "ports": 8,
        "wifi_24ghz": False,
        "wifi_5ghz": False,
        "wifi_type": None,
        "description": "7 Gigabit + 1x 2.5G + SFP+, sans Wi-Fi",
    },
    "rb3011": {
        "name": "RB3011UiAS",
        "ports": 10,
        "wifi_24ghz": False,
        "wifi_5ghz": False,
        "wifi_type": None,
        "description": "10 ports Gigabit + SFP, sans Wi-Fi",
    },

    # ---------- Cloud Core Router ----------
    "ccr1009": {
        "name": "CCR1009-7G-1C-1S+",
        "ports": 7,
        "wifi_24ghz": False,
        "wifi_5ghz": False,
        "wifi_type": None,
        "description": "7 ports Gigabit + SFP+, sans Wi-Fi",
    },
    "ccr1036": {
        "name": "CCR1036-12G-4S",
        "ports": 12,
        "wifi_24ghz": False,
        "wifi_5ghz": False,
        "wifi_type": None,
        "description": "12 Gigabit + 4 SFP, sans Wi-Fi",
    },
    "ccr2004": {
        "name": "CCR2004-1G-12S+2XS",
        "ports": 1,
        "wifi_24ghz": False,
        "wifi_5ghz": False,
        "wifi_type": None,
        "description": "1 Gigabit + 12 SFP+ + 2x 25G, sans Wi-Fi",
    },

    # ---------- Virtuel ----------
    "chr": {
        "name": "CHR (Cloud Hosted Router)",
        "ports": 4,
        "wifi_24ghz": False,
        "wifi_5ghz": False,
        "wifi_type": None,
        "description": "Routeur virtuel, ports variables, sans Wi-Fi",
    },
}


def get_model_info(model_key):
    """Retourne les spécifications d'un modèle MikroTik donné"""
    return MIKROTIK_MODELS.get(model_key, MIKROTIK_MODELS["hap_ac2"])


# ============================================================
# TARIFS PAR PLAN
# ============================================================
PLAN_PRICES = {
    "essentiel": 30000,
    "performance": 50000,
    "business": 80000,
}


def get_plan_price(plan_type):
    """Retourne le prix en Ariary pour un type de plan donné"""
    return PLAN_PRICES.get(plan_type, 30000)


# ============================================================
# INITIALISATION DE LA BASE DE DONNÉES
# ============================================================
def init_db(app):
    """Crée les tables SQLite dans le contexte Flask"""
    db.init_app(app)
    with app.app_context():
        db.create_all()
