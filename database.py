# -*- coding: utf-8 -*-
"""KETRIKA MIKROTIK 301 - Base de donnees"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import secrets
import random

db = SQLAlchemy()


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    license_key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    client_name = db.Column(db.String(120), nullable=False)
    whatsapp_number = db.Column(db.String(30), nullable=False)
    plan_type = db.Column(db.String(20), nullable=False)
    mikrotik_model = db.Column(db.String(80), nullable=False)
    router_name = db.Column(db.String(80), nullable=False)
    ssid_2g = db.Column(db.String(64), default="")
    ssid_5g = db.Column(db.String(64), default="")
    wifi_password = db.Column(db.String(64), default="")
    wan_interface = db.Column(db.String(30), default="ether1")
    lan_gateway = db.Column(db.String(30), default="192.168.10.1")
    lan_network = db.Column(db.String(30), default="192.168.10.0/24")
    dhcp_pool_start = db.Column(db.String(30), default="192.168.10.10")
    dhcp_pool_end = db.Column(db.String(30), default="192.168.10.250")
    ttl_value = db.Column(db.Integer, default=0)
    mac_spoof = db.Column(db.Boolean, default=False)
    mac_address = db.Column(db.String(30), default="")
    dl_limit = db.Column(db.Integer, default=0)
    ul_limit = db.Column(db.Integer, default=0)
    client_limit = db.Column(db.Integer, default=0)
    sleep_mode = db.Column(db.String(30), default="off")
    sleep_start = db.Column(db.String(10), default="")
    sleep_end = db.Column(db.String(10), default="")
    hotspot_tickets_count = db.Column(db.Integer, default=0)
    hotspot_profiles = db.Column(db.Text, default="[]")
    payment_status = db.Column(db.String(20), default="pending")
    payment_amount = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    validated_at = db.Column(db.DateTime, nullable=True)
    terms_accepted = db.Column(db.Boolean, default=False)
    # Cles WARP generees par l API Cloudflare
    warp_private_key = db.Column(db.String(100), default="")
    warp_public_key = db.Column(db.String(100), default="")
    warp_ipv4 = db.Column(db.String(30), default="")
    warp_ipv6 = db.Column(db.String(60), default="")
    warp_client_id = db.Column(db.String(20), default="")


def generate_license_key():
    return "LIC-" + secrets.token_hex(16).upper()


def generate_router_name(license_key):
    return "KETRIKA-" + license_key.replace("LIC-", "")[:6]


def generate_random_mac():
    prefixes = ["00:12:FB", "AC:37:43", "F0:25:B7", "34:CE:00", "00:1B:B1"]
    oui = random.choice(prefixes)
    tail = ":".join(f"{random.randint(0, 255):02X}" for _ in range(3))
    return f"{oui}:{tail}"


MIKROTIK_MODELS = {
    "hap_lite": {"name": "hAP lite (RB941-2nD)", "ports": 4, "wifi_24ghz": True, "wifi_5ghz": False, "wifi_type": "n", "description": "4 ports, Wi-Fi 2.4GHz N"},
    "hap": {"name": "hAP (RB951Ui-2nD)", "ports": 5, "wifi_24ghz": True, "wifi_5ghz": False, "wifi_type": "n", "description": "5 ports, Wi-Fi 2.4GHz N"},
    "hap_ac_lite": {"name": "hAP ac lite (RB952Ui-5ac2nD)", "ports": 5, "wifi_24ghz": True, "wifi_5ghz": True, "wifi_type": "ac", "description": "5 ports, Wi-Fi AC Dual-Band"},
    "hap_ac2": {"name": "hAP ac2", "ports": 5, "wifi_24ghz": True, "wifi_5ghz": True, "wifi_type": "ac", "description": "5 ports Gigabit, Wi-Fi AC Dual-Band"},
    "hap_ac3": {"name": "hAP ac3", "ports": 5, "wifi_24ghz": True, "wifi_5ghz": True, "wifi_type": "ac", "description": "5 ports Gigabit, Wi-Fi AC Dual-Band"},
    "hap_ax2": {"name": "hAP ax2", "ports": 5, "wifi_24ghz": True, "wifi_5ghz": True, "wifi_type": "ax", "description": "5 ports Gigabit, Wi-Fi 6 AX"},
    "hap_ax3": {"name": "hAP ax3", "ports": 5, "wifi_24ghz": True, "wifi_5ghz": True, "wifi_type": "ax", "description": "5 ports Gigabit, Wi-Fi 6 AX"},
    "hap_ax_lite": {"name": "hAP ax lite", "ports": 4, "wifi_24ghz": True, "wifi_5ghz": False, "wifi_type": "ax", "description": "4 ports, Wi-Fi 6 AX 2.4GHz"},
    "rb750gr3": {"name": "RB750Gr3 (hEX)", "ports": 5, "wifi_24ghz": False, "wifi_5ghz": False, "wifi_type": None, "description": "5 ports Gigabit"},
    "rb750r2": {"name": "RB750r2 (hEX lite)", "ports": 5, "wifi_24ghz": False, "wifi_5ghz": False, "wifi_type": None, "description": "5 ports 100Mbps"},
    "rb760igs": {"name": "RB760iGS (hEX S)", "ports": 5, "wifi_24ghz": False, "wifi_5ghz": False, "wifi_type": None, "description": "5 ports Gigabit + SFP"},
    "rb4011": {"name": "RB4011iGS+", "ports": 10, "wifi_24ghz": False, "wifi_5ghz": False, "wifi_type": None, "description": "10 ports Gigabit + SFP+"},
    "rb5009": {"name": "RB5009UG+S+", "ports": 8, "wifi_24ghz": False, "wifi_5ghz": False, "wifi_type": None, "description": "7G + 2.5G + SFP+"},
    "rb3011": {"name": "RB3011UiAS", "ports": 10, "wifi_24ghz": False, "wifi_5ghz": False, "wifi_type": None, "description": "10 ports Gigabit + SFP"},
    "ccr1009": {"name": "CCR1009-7G-1C-1S+", "ports": 7, "wifi_24ghz": False, "wifi_5ghz": False, "wifi_type": None, "description": "7 Gigabit + SFP+"},
    "ccr1036": {"name": "CCR1036-12G-4S", "ports": 12, "wifi_24ghz": False, "wifi_5ghz": False, "wifi_type": None, "description": "12 Gigabit + 4 SFP"},
    "ccr2004": {"name": "CCR2004-1G-12S+2XS", "ports": 1, "wifi_24ghz": False, "wifi_5ghz": False, "wifi_type": None, "description": "1G + 12 SFP+"},
    "chr": {"name": "CHR (Cloud Hosted Router)", "ports": 4, "wifi_24ghz": False, "wifi_5ghz": False, "wifi_type": None, "description": "Routeur virtuel"},
}


def get_model_info(model_key):
    return MIKROTIK_MODELS.get(model_key, MIKROTIK_MODELS["hap_ac2"])


PLAN_PRICES = {"essentiel": 30000, "performance": 50000, "business": 80000}


def get_plan_price(plan_type):
    return PLAN_PRICES.get(plan_type, 30000)


def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()
