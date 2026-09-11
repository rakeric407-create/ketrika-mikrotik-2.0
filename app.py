# -*- coding: utf-8 -*-
"""
KETRIKA MIKROTIK - Application Flask principale
"""

from flask import Flask, render_template, request, jsonify, Response, redirect, url_for
from database import (
    db, Order, init_db,
    generate_license_key, generate_router_name, generate_random_mac,
    get_model_info, get_plan_price, MIKROTIK_MODELS
)
from warp_api import generate_rsc
from datetime import datetime
import json
import os

# ============================================================
# CONFIGURATION
# ============================================================
MVOLA_NUMBER = "038 28 171 00"
WHATSAPP_NUMBER = "261382817100"
WHATSAPP_LINK = "https://wa.me/261382817100"
ADMIN_PASSWORD = "ketrika2024"

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ketrika.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "ketrika-mikrotik-secret-key-2024"

init_db(app)


# ============================================================
# PAGE D'ACCUEIL
# ============================================================
@app.route("/")
def index():
    return render_template(
        "index.html",
        mvola_number=MVOLA_NUMBER,
        whatsapp_number=WHATSAPP_NUMBER,
        whatsapp_link=WHATSAPP_LINK,
        models=MIKROTIK_MODELS,
    )


# ============================================================
# API : LISTE DES MODÈLES
# ============================================================
@app.route("/api/models")
def api_models():
    return jsonify(MIKROTIK_MODELS)


# ============================================================
# API : CRÉATION D'UNE COMMANDE
# ============================================================
@app.route("/api/order", methods=["POST"])
def api_order():
    data = request.get_json(force=True, silent=True) or {}

    plan = data.get("plan_type", "essentiel")
    if plan not in ("essentiel", "performance", "business"):
        return jsonify({"error": "Plan invalide"}), 400

    license_key = generate_license_key()
    router_name = data.get("router_name") or generate_router_name(license_key)

    # MAC : auto ou saisie manuelle
    mac_spoof = bool(data.get("mac_spoof", False))
    mac_address = data.get("mac_address", "").strip()
    if mac_spoof and not mac_address:
        mac_address = generate_random_mac()

    order = Order(
        license_key=license_key,
        client_name=data.get("client_name", "").strip(),
        whatsapp_number=data.get("whatsapp_number", "").strip(),
        plan_type=plan,
        mikrotik_model=data.get("mikrotik_model", "hap_ac2"),
        router_name=router_name,
        ssid_2g=data.get("ssid_2g", "").strip(),
        ssid_5g=data.get("ssid_5g", "").strip(),
        wifi_password=data.get("wifi_password", "").strip(),
        wan_interface=data.get("wan_interface", "ether1"),
        lan_gateway=data.get("lan_gateway", "192.168.10.1"),
        lan_network=data.get("lan_network", "192.168.10.0/24"),
        dhcp_pool_start=data.get("dhcp_pool_start", "192.168.10.10"),
        dhcp_pool_end=data.get("dhcp_pool_end", "192.168.10.250"),
        ttl_value=int(data.get("ttl_value", 0) or 0),
        mac_spoof=mac_spoof,
        mac_address=mac_address,
        dl_limit=int(data.get("dl_limit", 0) or 0),
        ul_limit=int(data.get("ul_limit", 0) or 0),
        client_limit=int(data.get("client_limit", 0) or 0),
        sleep_mode=data.get("sleep_mode", "off"),
        sleep_start=data.get("sleep_start", ""),
        sleep_end=data.get("sleep_end", ""),
        hotspot_tickets_count=int(data.get("hotspot_tickets_count", 0) or 0),
        hotspot_profiles=json.dumps(data.get("hotspot_profiles", [])),
        payment_status="pending",
        payment_amount=get_plan_price(plan),
    )

    # Validation minimale
    if not order.client_name or not order.whatsapp_number:
        return jsonify({"error": "Nom et WhatsApp requis"}), 400

    db.session.add(order)
    db.session.commit()

    return jsonify({
        "success": True,
        "order_id": order.id,
        "license_key": order.license_key,
        "amount": order.payment_amount,
        "mvola_number": MVOLA_NUMBER,
        "whatsapp_link": f"{WHATSAPP_LINK}?text=Bonjour%20KETRIKA%20!%20Voici%20ma%20preuve%20de%20paiement%20pour%20la%20commande%20%23{order.id}%20-%20Licence%20{order.license_key}",
        "router_name": order.router_name,
    })


# ============================================================
# API : STATUT D'UNE COMMANDE
# ============================================================
@app.route("/api/status/<license_key>")
def api_status(license_key):
    order = Order.query.filter_by(license_key=license_key).first()
    if not order:
        return jsonify({"error": "Licence introuvable"}), 404
    return jsonify({
        "status": order.payment_status,
        "client": order.client_name,
        "amount": order.payment_amount,
        "created_at": order.created_at.isoformat(),
    })


# ============================================================
# API : TÉLÉCHARGEMENT DU FICHIER .RSC
# ============================================================
@app.route("/api/download/<license_key>.rsc")
def api_download(license_key):
    order = Order.query.filter_by(license_key=license_key).first()
    if not order:
        return "Licence introuvable", 404
    if order.payment_status != "validated":
        return "Paiement non valide. Contactez KETRIKA au " + WHATSAPP_NUMBER, 403

    model_info = get_model_info(order.mikrotik_model)
    rsc_content = generate_rsc(order, model_info)

    return Response(
        rsc_content,
        mimetype="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="ketrika_{order.license_key}.rsc"'
        },
    )


# ============================================================
# PANEL ADMIN
# ============================================================
@app.route("/admin")
def admin():
    pwd = request.args.get("pwd", "")
    if pwd != ADMIN_PASSWORD:
        return """
        <html><body style="background:#0a0f1a;color:#fff;font-family:sans-serif;padding:40px;">
        <h1>🔒 KETRIKA Admin</h1>
        <form method="get">
            <input type="password" name="pwd" placeholder="Mot de passe admin" 
                   style="padding:10px;font-size:16px;background:#1e293b;color:#fff;border:1px solid #38bdf8;border-radius:6px;">
            <button type="submit" style="padding:10px 20px;background:#38bdf8;color:#000;border:none;border-radius:6px;cursor:pointer;">Entrer</button>
        </form></body></html>
        """

    pending = Order.query.filter_by(payment_status="pending").order_by(Order.created_at.desc()).all()
    validated = Order.query.filter_by(payment_status="validated").order_by(Order.validated_at.desc()).limit(50).all()

    html = """
    <html><head><meta charset="utf-8"><title>KETRIKA Admin</title>
    <style>
      body{background:#0a0f1a;color:#e2e8f0;font-family:system-ui,sans-serif;padding:20px;margin:0;}
      h1,h2{color:#38bdf8;}
      table{width:100%;border-collapse:collapse;margin:20px 0;background:#0f172a;border-radius:8px;overflow:hidden;}
      th,td{padding:12px;text-align:left;border-bottom:1px solid #1e293b;}
      th{background:#1e293b;color:#38bdf8;}
      tr:hover{background:#1e293b;}
      button{padding:6px 12px;border:none;border-radius:4px;cursor:pointer;font-weight:bold;}
      .valid{background:#10b981;color:#000;}
      .reject{background:#ef4444;color:#fff;}
      .plan-essentiel{color:#38bdf8;}
      .plan-performance{color:#10b981;}
      .plan-business{color:#8b5cf6;}
      .lic{font-family:monospace;font-size:12px;color:#94a3b8;}
    </style></head><body>
    <h1>🛡️ KETRIKA MIKROTIK - Administration</h1>
    """

    html += f"<h2>⏳ Commandes en attente ({len(pending)})</h2><table>"
    html += "<tr><th>ID</th><th>Client</th><th>WhatsApp</th><th>Plan</th><th>Modèle</th><th>Montant</th><th>Licence</th><th>Date</th><th>Actions</th></tr>"
    for o in pending:
        html += f"""<tr>
          <td>#{o.id}</td>
          <td>{o.client_name}</td>
          <td><a href='https://wa.me/{o.whatsapp_number}' style='color:#10b981;'>{o.whatsapp_number}</a></td>
          <td class='plan-{o.plan_type}'>{o.plan_type.upper()}</td>
          <td>{o.mikrotik_model}</td>
          <td><b>{o.payment_amount} Ar</b></td>
          <td class='lic'>{o.license_key}</td>
          <td>{o.created_at.strftime('%d/%m %H:%M')}</td>
          <td>
            <form method='post' action='/api/admin/validate/{o.id}?pwd={ADMIN_PASSWORD}' style='display:inline;'>
              <button class='valid' type='submit'>✅ Valider</button>
            </form>
            <form method='post' action='/api/admin/reject/{o.id}?pwd={ADMIN_PASSWORD}' style='display:inline;'>
              <button class='reject' type='submit'>❌ Rejeter</button>
            </form>
          </td>
        </tr>"""
    html += "</table>"

    html += f"<h2>✅ Commandes validées ({len(validated)})</h2><table>"
    html += "<tr><th>ID</th><th>Client</th><th>Plan</th><th>Licence</th><th>Téléchargement</th><th>Validé le</th></tr>"
    for o in validated:
        dl_url = f"/api/download/{o.license_key}.rsc"
        html += f"""<tr>
          <td>#{o.id}</td>
          <td>{o.client_name}</td>
          <td class='plan-{o.plan_type}'>{o.plan_type.upper()}</td>
          <td class='lic'>{o.license_key}</td>
          <td><a href='{dl_url}' style='color:#38bdf8;'>📥 .rsc</a></td>
          <td>{o.validated_at.strftime('%d/%m %H:%M') if o.validated_at else '-'}</td>
        </tr>"""
    html += "</table></body></html>"

    return html


# ============================================================
# API ADMIN : VALIDER
# ============================================================
@app.route("/api/admin/validate/<int:order_id>", methods=["POST"])
def api_admin_validate(order_id):
    if request.args.get("pwd", "") != ADMIN_PASSWORD:
        return "Non autorisé", 403
    order = Order.query.get_or_404(order_id)
    order.payment_status = "validated"
    order.validated_at = datetime.utcnow()
    db.session.commit()
    return redirect(f"/admin?pwd={ADMIN_PASSWORD}")


# ============================================================
# API ADMIN : REJETER
# ============================================================
@app.route("/api/admin/reject/<int:order_id>", methods=["POST"])
def api_admin_reject(order_id):
    if request.args.get("pwd", "") != ADMIN_PASSWORD:
        return "Non autorisé", 403
    order = Order.query.get_or_404(order_id)
    order.payment_status = "expired"
    db.session.commit()
    return redirect(f"/admin?pwd={ADMIN_PASSWORD}")


# ============================================================
# TUTORIEL
# ============================================================
@app.route("/tutoriel")
def tutoriel():
    return redirect(url_for("index") + "#tutoriel")


# ============================================================
# LANCEMENT
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
