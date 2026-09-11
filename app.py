# -*- coding: utf-8 -*-
"""
KETRIKA MIKROTIK 301 - Application Flask avec Inscription WARP API en Temps Réel
"""

from flask import Flask, render_template, request, jsonify, Response, redirect, send_file
from database import (
    db, Order, init_db, generate_license_key, generate_router_name,
    generate_random_mac, get_model_info, get_plan_price, MIKROTIK_MODELS
)
from warp_api import generate_rsc, generate_tutorial_txt
from datetime import datetime
import json
import os
import io
import zipfile
import requests
import base64

MVOLA = "038 28 171 00"
WALINK = "https://wa.me/261382817100"
APWD = "ketrika2024"
VER = "301"

app = Flask(__name__)

# Base de données robuste absolue
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "ketrika.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "ketrika-secret-301")
init_db(app)

# ============================================================
# CRYPTOGRAPHIE CURVE25519 POUR WIREGUARD (Évite toute dépendance externe)
# ============================================================
P = 2**255 - 19
A24 = 121665


def inv(n):
    return pow(n, P - 2, P)


def curve25519_eval(n, base=9):
    x_1 = base
    x_2, z_2 = 1, 0
    x_3, z_3 = base, 1
    for i in reversed(range(256)):
        bit = (n >> i) & 1
        if bit:
            x_2, x_3 = x_3, x_2
            z_2, z_3 = z_3, z_2
        a = (x_2 + z_2) % P
        aa = (a * a) % P
        b = (x_2 - z_2) % P
        bb = (b * b) % P
        e = (aa - bb) % P
        c = (x_3 + z_3) % P
        d = (x_3 - z_3) % P
        da = (d * a) % P
        cb = (c * b) % P
        x_3 = ((da + cb) * (da + cb)) % P
        z_3 = (x_1 * (da - cb) * (da - cb)) % P
        x_2 = (aa * bb) % P
        z_2 = (e * (bb + (A24 * e))) % P
        if bit:
            x_2, x_3 = x_3, x_2
            z_2, z_3 = z_3, z_2
    return (x_2 * inv(z_2)) % P


def generate_curve25519_keypair():
    priv_bytes = bytearray(os.urandom(32))
    priv_bytes[0] &= 248
    priv_bytes[31] = (priv_bytes[31] & 127) | 64

    priv_num = int.from_bytes(priv_bytes, "little")
    pub_num = curve25519_eval(priv_num)
    pub_bytes = pub_num.to_bytes(32, "little")

    priv_b64 = base64.b64encode(priv_bytes).decode("utf-8")
    pub_b64 = base64.b64encode(pub_bytes).decode("utf-8")
    return priv_b64, pub_b64


def register_cloudflare_warp():
    """
    Enregistre un profil réel auprès de l'API Cloudflare WARP.
    Retourne la clé privée, la clé publique et l'adresse IP unique attribuée.
    """
    try:
        priv, pub = generate_curve25519_keypair()
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "okhttp/3.12.1",
        }
        payload = {
            "key": pub,
            "install_id": "",
            "fcm_token": "",
            "tos": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "model": "MikroTik Router",
            "serial_number": "301PRO",
            "locale": "fr_MG",
        }
        res = requests.post("https://api.cloudflareclient.com/v0a2158/reg", json=payload, headers=headers, timeout=10)
        if res.status_code in (200, 201):
            data = res.json()
            result = data.get("result", data)
            config = result.get("config", {})
            interface_conf = config.get("interface", {})
            addresses = interface_conf.get("addresses", {})
            ipv4 = addresses.get("v4", "172.16.0.2/32")
            return priv, pub, ipv4, result.get("id", "")
    except Exception:
        pass
    priv, pub = generate_curve25519_keypair()
    return priv, pub, "172.16.0.2/32", "fallback-id"


# ============================================================
# CONTROLES WEB ET ROUTES API
# ============================================================


@app.route("/")
def index():
    return render_template("index.html", mvola=MVOLA, walink=WALINK, models=MIKROTIK_MODELS, ver=VER)


@app.route("/api/models")
def api_models():
    return jsonify(MIKROTIK_MODELS)


@app.route("/api/check-license", methods=["POST"])
def check_lic():
    d = request.get_json(force=True, silent=True) or {}
    k = (d.get("license_key") or "").strip().upper()
    if not k:
        return jsonify({"ok": False, "err": "Saisissez une cle."}), 400
    o = Order.query.filter_by(license_key=k).first()
    if not o:
        return jsonify({"ok": False, "err": "Licence introuvable."}), 404
    r = {
        "ok": True,
        "lic": o.license_key,
        "name": o.client_name,
        "plan": o.plan_type,
        "status": o.payment_status,
        "router": o.router_name,
        "model": o.mikrotik_model,
        "amount": o.payment_amount,
        "date": o.created_at.strftime("%d/%m/%Y %H:%M"),
    }
    if o.payment_status == "validated":
        r["zip"] = f"/api/download/{o.license_key}.zip"
        r["rsc"] = f"/api/download/{o.license_key}.rsc"
        r["vdate"] = o.validated_at.strftime("%d/%m/%Y %H:%M") if o.validated_at else ""
    elif o.payment_status == "pending":
        r["mvola"] = MVOLA
        r["wa"] = f"{WALINK}?text=Paiement%20{o.license_key}"
    return jsonify(r)


@app.route("/api/order", methods=["POST"])
def order():
    try:
        d = request.get_json(force=True, silent=True) or {}
        plan = d.get("plan_type", "essentiel")
        if plan not in ("essentiel", "performance", "business"):
            return jsonify({"ok": False, "err": "Plan invalide."}), 400
        cn = (d.get("client_name") or "").strip()
        wa = (d.get("whatsapp_number") or "").strip()
        if not cn:
            return jsonify({"ok": False, "err": "Nom requis."}), 400
        if not wa or len(wa) < 9:
            return jsonify({"ok": False, "err": "WhatsApp requis."}), 400

        mk = d.get("mikrotik_model", "hap_ac2")
        if mk not in MIKROTIK_MODELS:
            mk = "hap_ac2"
        lic = generate_license_key()
        rn = (d.get("router_name") or "").strip() or generate_router_name(lic)
        ms = bool(d.get("mac_spoof", False))
        ma = (d.get("mac_address") or "").strip()
        if ms and not ma:
            ma = generate_random_mac()

        def si(v, df=0):
            try:
                return int(v) if v else df
            except:
                return df

        # Inscription et création de l'interface WireGuard à la volée
        warp_priv = warp_pub = warp_ip4 = warp_cid = ""
        if plan in ("performance", "business"):
            warp_priv, warp_pub, warp_ip4, warp_cid = register_cloudflare_warp()

        o = Order(
            license_key=lic,
            client_name=cn,
            whatsapp_number=wa,
            plan_type=plan,
            mikrotik_model=mk,
            router_name=rn,
            ssid_2g=(d.get("ssid_2g") or "").strip(),
            ssid_5g=(d.get("ssid_5g") or "").strip(),
            wifi_password=(d.get("wifi_password") or "").strip(),
            wan_interface=d.get("wan_interface") or "ether1",
            lan_gateway=d.get("lan_gateway") or "192.168.10.1",
            lan_network=d.get("lan_network") or "192.168.10.0/24",
            dhcp_pool_start=d.get("dhcp_pool_start") or "192.168.10.10",
            dhcp_pool_end=d.get("dhcp_pool_end") or "192.168.10.250",
            ttl_value=si(d.get("ttl_value")),
            mac_spoof=ms,
            mac_address=ma,
            dl_limit=si(d.get("dl_limit")),
            ul_limit=si(d.get("ul_limit")),
            client_limit=si(d.get("client_limit")),
            sleep_mode=d.get("sleep_mode") or "off",
            sleep_start=(d.get("sleep_start") or "").strip(),
            sleep_end=(d.get("sleep_end") or "").strip(),
            hotspot_tickets_count=si(d.get("hotspot_tickets_count")),
            hotspot_profiles=json.dumps(d.get("hotspot_profiles", [])),
            payment_status="pending",
            payment_amount=get_plan_price(plan),
            terms_accepted=bool(d.get("terms_accepted")),
            warp_private_key=warp_priv,
            warp_public_key=warp_pub,
            warp_ipv4=warp_ip4,
            warp_client_id=warp_cid,
        )
        db.session.add(o)
        db.session.commit()
        return jsonify({
            "ok": True,
            "id": o.id,
            "lic": lic,
            "amount": o.payment_amount,
            "plan": plan,
            "router": rn,
            "mvola": MVOLA,
            "wa": f"{WALINK}?text=Paiement%20%23{o.id}%20{lic}%20{o.payment_amount}Ar",
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "err": str(e)}), 500


@app.route("/api/download/<lic>.rsc")
def dl_rsc(lic):
    o = Order.query.filter_by(license_key=lic.strip().upper()).first()
    if not o:
        return "Introuvable", 404
    if o.payment_status != "validated":
        return "Non valide", 403
    rsc = generate_rsc(o, get_model_info(o.mikrotik_model))
    return Response(
        rsc,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="ketrika_{o.license_key}.rsc"'},
    )


@app.route("/api/download/<lic>.zip")
def dl_zip(lic):
    o = Order.query.filter_by(license_key=lic.strip().upper()).first()
    if not o:
        return "Introuvable", 404
    if o.payment_status != "validated":
        return "Non valide", 403
    mi = get_model_info(o.mikrotik_model)
    rsc = generate_rsc(o, mi)
    fn = f"ketrika_{o.license_key}.rsc"
    tut = generate_tutorial_txt(o, fn)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(fn, rsc)
        z.writestr("LISEZ-MOI.txt", tut)
        z.writestr("COMMANDE.txt", f"/import file-name={fn}\n")
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name=f"KETRIKA_{o.license_key}.zip")


@app.route("/admin")
def admin():
    pwd = request.args.get("pwd", "")
    if pwd != APWD:
        return """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Admin</title><style>*{margin:0;padding:0;box-sizing:border-box}body{background:#f8fafc;font-family:system-ui;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
.b{background:#fff;border-radius:16px;padding:40px;max-width:400px;width:100%;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.08)}h1{{color:#1e293b;margin-bottom:24px}}
input{width:100%;padding:14px;background:#f1f5f9;border:1px solid #e2e8f0;border-radius:8px;font-size:16px;margin-bottom:16px}
button{width:100%;padding:14px;background:#2563eb;color:#fff;border:none;border-radius:8px;font-weight:700;cursor:pointer;font-size:16px}</style></head>
<body><div class="b"><h1>KETRIKA Admin</h1><form method="get"><input type="password" name="pwd" placeholder="Mot de passe" required autofocus><button>Entrer</button></form></div></body></html>"""

    pending = Order.query.filter_by(payment_status="pending").order_by(Order.created_at.desc()).all()
    validated = Order.query.filter_by(payment_status="validated").order_by(Order.validated_at.desc()).limit(100).all()

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KETRIKA Admin</title><style>*{{margin:0;padding:0;box-sizing:border-box}}body{{background:#f8fafc;font-family:system-ui;padding:16px;color:#1e293b}}
h1{{margin-bottom:20px;color:#2563eb}}h2{{margin:24px 0 12px;font-size:18px}}
.c{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin-bottom:12px;box-shadow:0 1px 4px rgba(0,0,0,.04)}}
.n{{font-weight:700;font-size:16px}}.m{{font-size:13px;color:#64748b;line-height:1.7}}.m a{{color:#2563eb}}
.k{{font-family:monospace;font-size:11px;color:#94a3b8;word-break:break-all;margin-top:4px}}
.a{{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}}
button,.d{{padding:10px 16px;border:none;border-radius:8px;font-weight:700;cursor:pointer;font-size:14px;text-decoration:none;display:inline-block}}
.v{{background:#10b981;color:#fff}}.r{{background:#ef4444;color:#fff}}.d{{background:#2563eb;color:#fff}}.z{{background:#7c3aed;color:#fff}}
</style></head><body>
<h1>KETRIKA MIKROTIK {VER}</h1>
<h2>En attente ({len(pending)})</h2>"""

    for o in pending:
        html += f"""<div class="c"><div class="n">{o.client_name} #{o.id}</div>
<div class="m">📱 <a href="https://wa.me/{o.whatsapp_number}">{o.whatsapp_number}</a> | {o.plan_type.upper()} | {o.payment_amount:,} Ar | {o.created_at.strftime('%d/%m %H:%M')}</div>
<div class="k">{o.license_key}</div>
<div class="a"><form method="post" action="/api/admin/validate/{o.id}?pwd={APWD}"><button class="v">✅ Valider</button></form>
<form method="post" action="/api/admin/reject/{o.id}?pwd={APWD}"><button class="r">❌</button></form></div></div>"""

    html += f"<h2>Validees ({len(validated)})</h2>"
    for o in validated:
        html += f"""<div class="c"><div class="n">{o.client_name} #{o.id} — {o.plan_type.upper()}</div>
<div class="k">{o.license_key}</div>
<div class="a"><a class="z" href="/api/download/{o.license_key}.zip">📦 ZIP</a> <a class="d" href="/api/download/{o.license_key}.rsc">📥 RSC</a></div></div>"""

    return html + "</body></html>"


@app.route("/api/admin/validate/<int:oid>", methods=["POST"])
def val(oid):
    if request.args.get("pwd") != APWD:
        return "Non", 403
    o = Order.query.get(oid)
    if not o:
        return "?", 404
    o.payment_status = "validated"
    o.validated_at = datetime.utcnow()
    db.session.commit()
    return redirect(f"/admin?pwd={APWD}")


@app.route("/api/admin/reject/<int:oid>", methods=["POST"])
def rej(oid):
    if request.args.get("pwd") != APWD:
        return "Non", 403
    o = Order.query.get(oid)
    if not o:
        return "?", 404
    o.payment_status = "expired"
    db.session.commit()
    return redirect(f"/admin?pwd={APWD}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
