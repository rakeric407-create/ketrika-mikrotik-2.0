import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

basedir = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(basedir, "ketrika.db")


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    license_key = db.Column(db.String(32), unique=True, nullable=False, index=True)

    # Identité
    customer_name = db.Column(db.String(120), nullable=False)
    whatsapp = db.Column(db.String(40), nullable=False)

    # Plan
    plan = db.Column(db.String(20), nullable=False)  # essentiel|performance|business
    price = db.Column(db.Integer, nullable=False)

    # Matériel
    model = db.Column(db.String(60), nullable=False)
    router_name = db.Column(db.String(60), default="KETRIKA-RB")
    wan_port = db.Column(db.String(20), default="ether1")

    # Réseau
    lan_ip = db.Column(db.String(20), default="192.168.10.1")
    lan_mask = db.Column(db.String(20), default="24")
    dhcp_start = db.Column(db.String(20), default="192.168.10.100")
    dhcp_end = db.Column(db.String(20), default="192.168.10.250")

    # Wi-Fi
    wifi_enabled = db.Column(db.Boolean, default=True)
    ssid_24 = db.Column(db.String(60), default="KETRIKA_2G")
    ssid_5 = db.Column(db.String(60), default="KETRIKA_5G")
    wifi_password = db.Column(db.String(60), default="ketrika2024")

    # Veille Wi-Fi
    sleep_enabled = db.Column(db.Boolean, default=False)
    sleep_start = db.Column(db.String(10), default="23:00:00")
    sleep_stop = db.Column(db.String(10), default="06:00:00")

    # Plan 2+
    ttl_value = db.Column(db.Integer, default=0)  # 0=off, 64, 65, 128
    mac_spoof = db.Column(db.String(20), default="off")  # off|auto|manuel
    mac_manual = db.Column(db.String(40), default="")
    limit_down = db.Column(db.Integer, default=0)  # kbps
    limit_up = db.Column(db.Integer, default=0)
    limit_per_client = db.Column(db.Integer, default=0)

    # WARP réel
    warp_private_key = db.Column(db.String(120), default="")
    warp_public_key = db.Column(db.String(120), default="")
    warp_ipv4 = db.Column(db.String(40), default="")

    # Hotspot (plan 3)
    hotspot_tickets = db.Column(db.Integer, default=0)
    hotspot_profile = db.Column(db.String(20), default="1h")

    # Statut
    status = db.Column(db.String(20), default="pending")  # pending|validated|rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    validated_at = db.Column(db.DateTime, nullable=True)


def init_db(app):
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
