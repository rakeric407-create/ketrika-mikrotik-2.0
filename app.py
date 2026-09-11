# -*- coding: utf-8 -*-
"""KETRIKA MIKROTIK v3.0.1 - Application Flask avec téléchargement ZIP"""

from flask import Flask, render_template, request, jsonify, Response, redirect, url_for, send_file
from database import (
    db, Order, init_db, generate_license_key, generate_router_name,
    generate_random_mac, get_model_info, get_plan_price, MIKROTIK_MODELS, PLAN_PRICES
)
from warp_api import generate_rsc, generate_tutorial_txt
from datetime import datetime
import json
import os
import io
import zipfile

MVOLA_NUMBER = "038 28 171 00"
WHATSAPP_NUMBER = "261382817100"
WHATSAPP_LINK = "https://wa.me/261382817100"
ADMIN_PASSWORD = "ketrika2024"
APP_VERSION = "3.0.1"

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ketrika.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "ketrika-v3-secret")

init_db(app)


@app.route("/")
def index():
    return render_template(
        "index.html",
        mvola_number=MVOLA_NUMBER,
        whatsapp_number=WHATSAPP_NUMBER,
        whatsapp_link=WHATSAPP_LINK,
        models=MIKROTIK_MODELS,
        version=APP_VERSION,
    )


@app.route("/api/models")
def api_models():
    return jsonify(MIKROTIK_MODELS)


@app.route("/api/check-license", methods=["POST"])
def api_check_license():
    data = request.get_json(force=True, silent=True) or {}
    key = (data.get("license_key") or "").strip().upper()
    if not key:
        return jsonify({"success": False, "error": "Veuillez saisir une cle de licence."}), 400

    order = Order.query.filter_by(license_key=key).first()
    if not order:
        return jsonify({"success": False, "error": "Licence introuvable."}), 404

    result = {
        "success": True,
        "license_key": order.license_key,
        "client_name": order.client_name,
        "plan_type": order.plan_type,
        "payment_status": order.payment_status,
        "router_name": order.router_name,
        "mikrotik_model": order.mikrotik_model,
        "amount": order.payment_amount,
        "created_at": order.created_at.strftime("%d/%m/%Y %H:%M"),
    }

    if order.payment_status == "validated":
        result["download_url"] = f"/api/download/{order.license_key}.zip"
        result["download_rsc_url"] = f"/api/download/{order.license_key}.rsc"
        result["validated_at"] = order.validated_at.strftime("%d/%m/%Y %H:%M") if order.validated_at else ""
    elif order.payment_status == "pending":
        result["mvola_number"] = MVOLA_NUMBER
        result["whatsapp_link"] = f"{WHATSAPP_LINK}?text=Bonjour%20KETRIKA%20!%20Paiement%20{order.license_key}"

    return jsonify(result)


@app.route("/api/order", methods=["POST"])
def api_order():
    try:
        data = request.get_json(force=True, silent=True) or {}

        plan = data.get("plan_type", "essentiel")
        if plan not in ("essentiel", "performance", "business"):
            return jsonify({"success": False, "error": "Plan invalide."}), 400

        client_name = (data.get("client_name") or "").strip()
        whatsapp = (data.get("whatsapp_number") or "").strip()
        if not client_name:
            return jsonify({"success": False, "error": "Le nom est obligatoire."}), 400
        if not whatsapp or len(whatsapp) < 9:
            return jsonify({"success": False, "error": "Numero WhatsApp invalide."}), 400

        model_key = data.get("mikrotik_model", "hap_ac2")
        if model_key not in MIKROTIK_MODELS:
            model_key = "hap_ac2"

        license_key = generate_license_key()
        router_name = (data.get("router_name") or "").strip() or generate_router_name(license_key)

        mac_spoof = bool(data.get("mac_spoof", False))
        mac_address = (data.get("mac_address") or "").strip()
        if mac_spoof and not mac_address:
            mac_address = generate_random_mac()

        def safe_int(val, default=0):
            try:
                return int(val) if val else default
            except (ValueError, TypeError):
                return default

        order = Order(
            license_key=license_key,
            client_name=client_name,
            whatsapp_number=whatsapp,
            plan_type=plan,
            mikrotik_model=model_key,
            router_name=router_name,
            ssid_2g=(data.get("ssid_2g") or "").strip(),
            ssid_5g=(data.get("ssid_5g") or "").strip(),
            wifi_password=(data.get("wifi_password") or "").strip(),
            wan_interface=data.get("wan_interface") or "ether1",
            lan_gateway=data.get("lan_gateway") or "192.168.10.1",
            lan_network=data.get("lan_network") or "192.168.10.0/24",
            dhcp_pool_start=data.get("dhcp_pool_start") or "192.168.10.10",
            dhcp_pool_end=data.get("dhcp_pool_end") or "192.168.10.250",
            ttl_value=safe_int(data.get("ttl_value"), 0),
            mac_spoof=mac_spoof,
            mac_address=mac_address,
            dl_limit=safe_int(data.get("dl_limit"), 0),
            ul_limit=safe_int(data.get("ul_limit"), 0),
            client_limit=safe_int(data.get("client_limit"), 0),
            sleep_mode=data.get("sleep_mode") or "off",
            sleep_start=(data.get("sleep_start") or "").strip(),
            sleep_end=(data.get("sleep_end") or "").strip(),
            hotspot_tickets_count=safe_int(data.get("hotspot_tickets_count"), 0),
            hotspot_profiles=json.dumps(data.get("hotspot_profiles", [])),
            payment_status="pending",
            payment_amount=get_plan_price(plan),
            terms_accepted=bool(data.get("terms_accepted", False)),
        )

        db.session.add(order)
        db.session.commit()

        return jsonify({
            "success": True,
            "order_id": order.id,
            "license_key": order.license_key,
            "amount": order.payment_amount,
            "plan_type": order.plan_type,
            "router_name": order.router_name,
            "mvola_number": MVOLA_NUMBER,
            "whatsapp_link": (
                f"{WHATSAPP_LINK}?text=Bonjour%20KETRIKA%20!%20Preuve%20paiement%20"
                f"commande%20%23{order.id}%20Licence%20{order.license_key}%20"
                f"Montant%20{order.payment_amount}%20Ar"
            ),
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": f"Erreur: {str(e)}"}), 500


@app.route("/api/download/<license_key>.rsc")
def api_download_rsc(license_key):
    """Télécharge le .rsc seul"""
    clean_key = license_key.strip().upper()
    order = Order.query.filter_by(license_key=clean_key).first()
    if not order:
        return "Licence introuvable", 404
    if order.payment_status != "validated":
        return "Paiement non valide", 403

    model_info = get_model_info(order.mikrotik_model)
    rsc = generate_rsc(order, model_info)
    filename = f"ketrika_{clean_key}.rsc"

    return Response(
        rsc,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.route("/api/download/<license_key>.zip")
def api_download_zip(license_key):
    """Télécharge le ZIP contenant .rsc + tutoriel .txt"""
    clean_key = license_key.strip().upper()
    order = Order.query.filter_by(license_key=clean_key).first()
    if not order:
        return "Licence introuvable", 404
    if order.payment_status != "validated":
        return "Paiement non valide", 403

    model_info = get_model_info(order.mikrotik_model)
    rsc_content = generate_rsc(order, model_info)
    rsc_filename = f"ketrika_{clean_key}.rsc"
    tutorial_content = generate_tutorial_txt(order, rsc_filename)

    # Créer le ZIP en mémoire
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(rsc_filename, rsc_content)
        zf.writestr("LISEZ-MOI-INSTALLATION.txt", tutorial_content)
        # Fichier commande à copier-coller
        cmd_content = f"/import file-name={rsc_filename}\n"
        zf.writestr("COMMANDE-A-COPIER.txt", cmd_content)

    zip_buffer.seek(0)

    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"KETRIKA_{clean_key}.zip"
    )


@app.route("/api/status/<license_key>")
def api_status(license_key):
    order = Order.query.filter_by(license_key=license_key.upper()).first()
    if not order:
        return jsonify({"error": "Introuvable"}), 404
    return jsonify({
        "status": order.payment_status,
        "client": order.client_name,
        "plan": order.plan_type,
        "amount": order.payment_amount,
    })


@app.route("/admin")
def admin():
    pwd = request.args.get("pwd", "")
    if pwd != ADMIN_PASSWORD:
        return render_admin_login()

    pending = Order.query.filter_by(payment_status="pending").order_by(Order.created_at.desc()).all()
    validated = Order.query.filter_by(payment_status="validated").order_by(Order.validated_at.desc()).limit(100).all()
    expired = Order.query.filter_by(payment_status="expired").order_by(Order.created_at.desc()).limit(50).all()

    return render_admin_panel(pending, validated, expired)


def render_admin_login():
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KETRIKA Admin</title><style>
*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#0a0f1a;color:#e2e8f0;font-family:system-ui;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px;}}
.box{{background:#111827;border:1px solid #1e293b;border-radius:16px;padding:40px;max-width:400px;width:100%;text-align:center;}}
h1{{color:#38bdf8;margin-bottom:8px;font-size:24px;}}p{{color:#94a3b8;margin-bottom:24px;}}
input{{width:100%;padding:14px;background:#0a0f1a;border:1px solid #1e293b;border-radius:8px;color:#e2e8f0;font-size:16px;margin-bottom:16px;}}
button{{width:100%;padding:14px;background:linear-gradient(135deg,#38bdf8,#8b5cf6);color:#fff;border:none;border-radius:8px;font-weight:700;cursor:pointer;font-size:16px;}}
</style></head><body><div class="box"><h1>🔒 KETRIKA Admin</h1><p>v{APP_VERSION}</p>
<form method="get"><input type="password" name="pwd" placeholder="Mot de passe" required autofocus><button>Entrer</button></form>
</div></body></html>"""


def render_admin_panel(pending, validated, expired):
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KETRIKA Admin</title><style>
*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#0a0f1a;color:#e2e8f0;font-family:system-ui;padding:16px;}}
.h{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #1e293b;}}
h1{{color:#38bdf8;font-size:22px;}}h2{{margin:24px 0 12px;font-size:18px;}}
.b{{padding:6px 14px;border-radius:20px;font-size:12px;font-weight:700;}}
.bw{{background:#f59e0b22;color:#f59e0b;border:1px solid #f59e0b;}}.bo{{background:#10b98122;color:#10b981;border:1px solid #10b981;}}
.c{{background:#111827;border:1px solid #1e293b;border-radius:12px;padding:16px;margin-bottom:12px;}}
.ct{{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:10px;}}
.cn{{font-weight:700;font-size:16px;}}.cm{{font-size:13px;color:#94a3b8;display:grid;gap:4px;}}.cm a{{color:#10b981;}}
.ck{{font-family:monospace;font-size:11px;color:#64748b;word-break:break-all;}}
.ca{{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;}}
button,.dl{{padding:10px 16px;border:none;border-radius:8px;font-weight:700;cursor:pointer;font-size:14px;text-decoration:none;display:inline-block;}}
.bv{{background:#10b981;color:#000;}}.br{{background:#ef4444;color:#fff;}}.dl{{background:#38bdf8;color:#000;}}.dz{{background:#8b5cf6;color:#fff;}}
</style></head><body>
<div class="h"><h1>⚡ KETRIKA Admin v{APP_VERSION}</h1><div>
<span class="b bw">⏳ {len(pending)}</span> <span class="b bo">✅ {len(validated)}</span></div></div>

<h2>⏳ En attente</h2>"""

    if not pending:
        html += '<p style="color:#94a3b8;padding:20px;">Aucune commande en attente.</p>'
    for o in pending:
        html += f"""<div class="c"><div class="ct"><div>
<div class="cn">{o.client_name} — #{o.id}</div>
<div class="cm"><span>📱 <a href="https://wa.me/{o.whatsapp_number}" target="_blank">{o.whatsapp_number}</a></span>
<span>📦 {o.plan_type.upper()} — <b>{o.payment_amount:,} Ar</b></span>
<span>🔧 {o.mikrotik_model} → {o.router_name}</span>
<span>📅 {o.created_at.strftime('%d/%m/%Y %H:%M')}</span></div>
<div class="ck">🔑 {o.license_key}</div></div></div>
<div class="ca">
<form method="post" action="/api/admin/validate/{o.id}?pwd={ADMIN_PASSWORD}" style="display:inline;"><button class="bv">✅ Valider</button></form>
<form method="post" action="/api/admin/reject/{o.id}?pwd={ADMIN_PASSWORD}" style="display:inline;"><button class="br">❌ Rejeter</button></form>
</div></div>"""

    html += f'<h2>✅ Validées ({len(validated)})</h2>'
    if not validated:
        html += '<p style="color:#94a3b8;padding:20px;">Aucune commande validée.</p>'
    for o in validated:
        html += f"""<div class="c" style="border-color:#10b98133;"><div class="ct"><div>
<div class="cn">{o.client_name} — #{o.id}</div>
<div class="cm"><span>📱 <a href="https://wa.me/{o.whatsapp_number}" target="_blank">{o.whatsapp_number}</a></span>
<span>📦 {o.plan_type.upper()}</span></div>
<div class="ck">🔑 {o.license_key}</div></div></div>
<div class="ca">
<a class="dz" href="/api/download/{o.license_key}.zip" target="_blank">📦 ZIP Complet</a>
<a class="dl" href="/api/download/{o.license_key}.rsc" target="_blank">📥 .rsc seul</a>
</div></div>"""

    html += '</body></html>'
    return html


@app.route("/api/admin/validate/<int:order_id>", methods=["POST"])
def api_admin_validate(order_id):
    if request.args.get("pwd", "") != ADMIN_PASSWORD:
        return "Non autorise", 403
    order = Order.query.get(order_id)
    if not order:
        return "Introuvable", 404
    order.payment_status = "validated"
    order.validated_at = datetime.utcnow()
    db.session.commit()
    return redirect(f"/admin?pwd={ADMIN_PASSWORD}")


@app.route("/api/admin/reject/<int:order_id>", methods=["POST"])
def api_admin_reject(order_id):
    if request.args.get("pwd", "") != ADMIN_PASSWORD:
        return "Non autorise", 403
    order = Order.query.get(order_id)
    if not order:
        return "Introuvable", 404
    order.payment_status = "expired"
    db.session.commit()
    return redirect(f"/admin?pwd={ADMIN_PASSWORD}")


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Introuvable"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Erreur serveur"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
