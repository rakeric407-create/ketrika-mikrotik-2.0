# -*- coding: utf-8 -*-
"""
KETRIKA MIKROTIK v3.0.1 - Application Flask principale
Routes API, panel admin, gestion des commandes et téléchargements
"""

from flask import (
    Flask, render_template, request, jsonify,
    Response, redirect, url_for
)
from database import (
    db, Order, init_db,
    generate_license_key, generate_router_name, generate_random_mac,
    get_model_info, get_plan_price, MIKROTIK_MODELS, PLAN_PRICES
)
from warp_api import generate_rsc
from datetime import datetime
import json
import os

# ============================================================
# CONFIGURATION GLOBALE
# ============================================================
MVOLA_NUMBER = "038 28 171 00"
WHATSAPP_NUMBER = "261382817100"
WHATSAPP_LINK = "https://wa.me/261382817100"
ADMIN_PASSWORD = "ketrika2024"
APP_VERSION = "3.0.1"

# ============================================================
# INITIALISATION FLASK
# ============================================================
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ketrika.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "ketrika-v3-secret-prod-2024")

init_db(app)


# ============================================================
# PAGE D'ACCUEIL
# ============================================================
@app.route("/")
def index():
    """Affiche la page d'accueil complète"""
    return render_template(
        "index.html",
        mvola_number=MVOLA_NUMBER,
        whatsapp_number=WHATSAPP_NUMBER,
        whatsapp_link=WHATSAPP_LINK,
        models=MIKROTIK_MODELS,
        version=APP_VERSION,
    )


# ============================================================
# API : LISTE DES MODÈLES MIKROTIK
# ============================================================
@app.route("/api/models")
def api_models():
    """Retourne tous les modèles MikroTik au format JSON"""
    return jsonify(MIKROTIK_MODELS)


# ============================================================
# API : VÉRIFIER UNE LICENCE (ACTIVATION EN HAUT DE PAGE)
# ============================================================
@app.route("/api/check-license", methods=["POST"])
def api_check_license():
    """Vérifie le statut d'une licence et retourne les infos"""
    data = request.get_json(force=True, silent=True) or {}
    key = (data.get("license_key") or "").strip().upper()

    if not key:
        return jsonify({"success": False, "error": "Veuillez saisir une clé de licence."}), 400

    # Chercher la commande par licence
    order = Order.query.filter_by(license_key=key).first()

    if not order:
        return jsonify({
            "success": False,
            "error": "Licence introuvable. Vérifiez la clé saisie."
        }), 404

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

    # Si validée, ajouter le lien de téléchargement
    if order.payment_status == "validated":
        result["download_url"] = f"/api/download/{order.license_key}.rsc"
        result["validated_at"] = order.validated_at.strftime("%d/%m/%Y %H:%M") if order.validated_at else ""
    elif order.payment_status == "pending":
        result["mvola_number"] = MVOLA_NUMBER
        result["whatsapp_link"] = f"{WHATSAPP_LINK}?text=Bonjour%20KETRIKA%20!%20J%27ai%20paye%20pour%20la%20licence%20{order.license_key}"

    return jsonify(result)


# ============================================================
# API : CRÉER UNE COMMANDE
# ============================================================
@app.route("/api/order", methods=["POST"])
def api_order():
    """Crée une nouvelle commande à partir du formulaire"""
    try:
        data = request.get_json(force=True, silent=True) or {}

        # Validation du plan
        plan = data.get("plan_type", "essentiel")
        if plan not in ("essentiel", "performance", "business"):
            return jsonify({"success": False, "error": "Plan invalide."}), 400

        # Validation des champs obligatoires
        client_name = (data.get("client_name") or "").strip()
        whatsapp = (data.get("whatsapp_number") or "").strip()
        if not client_name:
            return jsonify({"success": False, "error": "Le nom est obligatoire."}), 400
        if not whatsapp:
            return jsonify({"success": False, "error": "Le numéro WhatsApp est obligatoire."}), 400
        if len(whatsapp) < 9:
            return jsonify({"success": False, "error": "Numéro WhatsApp invalide."}), 400

        # Validation modèle
        model_key = data.get("mikrotik_model", "hap_ac2")
        if model_key not in MIKROTIK_MODELS:
            model_key = "hap_ac2"

        # Générer la licence
        license_key = generate_license_key()
        router_name = (data.get("router_name") or "").strip() or generate_router_name(license_key)

        # MAC spoofing
        mac_spoof = bool(data.get("mac_spoof", False))
        mac_address = (data.get("mac_address") or "").strip()
        if mac_spoof and not mac_address:
            mac_address = generate_random_mac()

        # Gestion du sleep mode
        sleep_mode = data.get("sleep_mode", "off") or "off"
        sleep_start = (data.get("sleep_start") or "").strip()
        sleep_end = (data.get("sleep_end") or "").strip()

        # Conversion int sécurisée
        def safe_int(val, default=0):
            try:
                return int(val) if val else default
            except (ValueError, TypeError):
                return default

        # Créer l'objet Order
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
            wan_interface=data.get("wan_interface", "ether1") or "ether1",
            lan_gateway=data.get("lan_gateway", "192.168.10.1") or "192.168.10.1",
            lan_network=data.get("lan_network", "192.168.10.0/24") or "192.168.10.0/24",
            dhcp_pool_start=data.get("dhcp_pool_start", "192.168.10.10") or "192.168.10.10",
            dhcp_pool_end=data.get("dhcp_pool_end", "192.168.10.250") or "192.168.10.250",
            ttl_value=safe_int(data.get("ttl_value"), 0),
            mac_spoof=mac_spoof,
            mac_address=mac_address,
            dl_limit=safe_int(data.get("dl_limit"), 0),
            ul_limit=safe_int(data.get("ul_limit"), 0),
            client_limit=safe_int(data.get("client_limit"), 0),
            sleep_mode=sleep_mode,
            sleep_start=sleep_start,
            sleep_end=sleep_end,
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
                f"{WHATSAPP_LINK}?text="
                f"Bonjour%20KETRIKA%20!%20Voici%20ma%20preuve%20de%20paiement%20"
                f"pour%20la%20commande%20%23{order.id}%20"
                f"-%20Licence%20{order.license_key}%20"
                f"-%20Montant%20{order.payment_amount}%20Ar"
            ),
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": f"Erreur serveur : {str(e)}"}), 500


# ============================================================
# API : STATUT D'UNE COMMANDE
# ============================================================
@app.route("/api/status/<license_key>")
def api_status(license_key):
    """Vérifie le statut de paiement d'une licence"""
    order = Order.query.filter_by(license_key=license_key.upper()).first()
    if not order:
        return jsonify({"error": "Licence introuvable"}), 404
    return jsonify({
        "status": order.payment_status,
        "client": order.client_name,
        "plan": order.plan_type,
        "amount": order.payment_amount,
        "created_at": order.created_at.isoformat(),
    })


# ============================================================
# API : TÉLÉCHARGEMENT DU FICHIER .RSC
# ============================================================
@app.route("/api/download/<license_key>.rsc")
def api_download(license_key):
    """Génère et télécharge le fichier .rsc si le paiement est validé"""
    clean_key = license_key.strip().upper()
    order = Order.query.filter_by(license_key=clean_key).first()

    if not order:
        return Response(
            "# Erreur KETRIKA : Licence introuvable\n"
            "# Verifiez votre cle de licence.\n"
            f"# Contact : wa.me/{WHATSAPP_NUMBER}\n",
            mimetype="text/plain", status=404
        )

    if order.payment_status != "validated":
        return Response(
            "# Erreur KETRIKA : Paiement non valide\n"
            f"# Statut actuel : {order.payment_status}\n"
            f"# Envoyez votre preuve de paiement a : {MVOLA_NUMBER}\n"
            f"# Contact WhatsApp : wa.me/{WHATSAPP_NUMBER}\n",
            mimetype="text/plain", status=403
        )

    model_info = get_model_info(order.mikrotik_model)
    rsc_content = generate_rsc(order, model_info)

    filename = f"ketrika_{clean_key}.rsc"
    return Response(
        rsc_content,
        mimetype="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


# ============================================================
# PANEL ADMIN
# ============================================================
@app.route("/admin")
def admin():
    """Panel d'administration pour valider/rejeter les commandes"""
    pwd = request.args.get("pwd", "")
    if pwd != ADMIN_PASSWORD:
        return render_admin_login()

    pending = Order.query.filter_by(payment_status="pending").order_by(Order.created_at.desc()).all()
    validated = Order.query.filter_by(payment_status="validated").order_by(Order.validated_at.desc()).limit(100).all()
    expired = Order.query.filter_by(payment_status="expired").order_by(Order.created_at.desc()).limit(50).all()

    return render_admin_panel(pending, validated, expired)


def render_admin_login():
    """Affiche le formulaire de connexion admin"""
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KETRIKA Admin</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:#0a0f1a;color:#e2e8f0;font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px;}}
.box{{background:#111827;border:1px solid #1e293b;border-radius:16px;padding:40px;max-width:400px;width:100%;text-align:center;}}
h1{{color:#38bdf8;margin-bottom:8px;font-size:24px;}}
p{{color:#94a3b8;margin-bottom:24px;font-size:14px;}}
input{{width:100%;padding:14px;background:#0a0f1a;border:1px solid #1e293b;border-radius:8px;color:#e2e8f0;font-size:16px;margin-bottom:16px;}}
input:focus{{border-color:#38bdf8;outline:none;}}
button{{width:100%;padding:14px;background:linear-gradient(135deg,#38bdf8,#8b5cf6);color:#fff;border:none;border-radius:8px;font-size:16px;font-weight:700;cursor:pointer;}}
</style></head><body>
<div class="box">
<h1>🔒 KETRIKA Admin</h1>
<p>v{APP_VERSION} — Panneau d'administration</p>
<form method="get">
<input type="password" name="pwd" placeholder="Mot de passe administrateur" required autofocus>
<button type="submit">Accéder au panneau</button>
</form>
</div></body></html>"""


def render_admin_panel(pending, validated, expired):
    """Génère le HTML complet du panel admin"""
    html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KETRIKA Admin — v{APP_VERSION}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:#0a0f1a;color:#e2e8f0;font-family:system-ui,sans-serif;padding:16px;}}
.header{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #1e293b;}}
h1{{color:#38bdf8;font-size:22px;}}
.badge{{padding:6px 14px;border-radius:20px;font-size:12px;font-weight:700;}}
.badge-warn{{background:#f59e0b22;color:#f59e0b;border:1px solid #f59e0b;}}
.badge-ok{{background:#10b98122;color:#10b981;border:1px solid #10b981;}}
.badge-err{{background:#ef444422;color:#ef4444;border:1px solid #ef4444;}}
h2{{margin:24px 0 12px;font-size:18px;display:flex;align-items:center;gap:8px;}}
.card-grid{{display:grid;gap:12px;}}
.order-card{{background:#111827;border:1px solid #1e293b;border-radius:12px;padding:16px;}}
.order-top{{display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;margin-bottom:10px;}}
.order-name{{font-weight:700;font-size:16px;}}
.order-meta{{font-size:13px;color:#94a3b8;display:grid;gap:4px;}}
.order-meta a{{color:#10b981;}}
.order-key{{font-family:monospace;font-size:11px;color:#64748b;word-break:break-all;}}
.order-actions{{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;}}
button,.dl-btn{{padding:10px 16px;border:none;border-radius:8px;font-weight:700;cursor:pointer;font-size:14px;text-decoration:none;display:inline-block;}}
.btn-v{{background:#10b981;color:#000;}}
.btn-r{{background:#ef4444;color:#fff;}}
.dl-btn{{background:#38bdf8;color:#000;}}
.plan-e{{color:#38bdf8;}}
.plan-p{{color:#10b981;}}
.plan-b{{color:#8b5cf6;}}
@media(max-width:600px){{.order-top{{flex-direction:column;}}}}
</style></head><body>

<div class="header">
<h1>⚡ KETRIKA Admin v{APP_VERSION}</h1>
<div>
<span class="badge badge-warn">⏳ {len(pending)} en attente</span>
<span class="badge badge-ok">✅ {len(validated)} validées</span>
</div>
</div>
"""

    # Commandes en attente
    html += '<h2>⏳ Commandes en attente de paiement</h2><div class="card-grid">'
    if not pending:
        html += '<p style="color:#94a3b8;padding:20px;">Aucune commande en attente.</p>'
    for o in pending:
        plan_class = f"plan-{o.plan_type[0]}"
        html += f"""<div class="order-card">
<div class="order-top">
<div>
<div class="order-name">{o.client_name}</div>
<div class="order-meta">
<span>📱 <a href="https://wa.me/{o.whatsapp_number}" target="_blank">{o.whatsapp_number}</a></span>
<span class="{plan_class}">📦 {o.plan_type.upper()} — <b>{o.payment_amount:,} Ar</b></span>
<span>🔧 {o.mikrotik_model} → {o.router_name}</span>
<span>📅 {o.created_at.strftime('%d/%m/%Y %H:%M')}</span>
</div>
<div class="order-key">🔑 {o.license_key}</div>
</div>
<div style="font-size:24px;">#{o.id}</div>
</div>
<div class="order-actions">
<form method="post" action="/api/admin/validate/{o.id}?pwd={ADMIN_PASSWORD}" style="display:inline;">
<button class="btn-v" type="submit">✅ Valider le paiement</button>
</form>
<form method="post" action="/api/admin/reject/{o.id}?pwd={ADMIN_PASSWORD}" style="display:inline;">
<button class="btn-r" type="submit">❌ Rejeter</button>
</form>
</div>
</div>"""
    html += '</div>'

    # Commandes validées
    html += f'<h2>✅ Commandes validées ({len(validated)})</h2><div class="card-grid">'
    if not validated:
        html += '<p style="color:#94a3b8;padding:20px;">Aucune commande validée.</p>'
    for o in validated:
        plan_class = f"plan-{o.plan_type[0]}"
        dl_url = f"/api/download/{o.license_key}.rsc"
        html += f"""<div class="order-card" style="border-color:#10b98133;">
<div class="order-top">
<div>
<div class="order-name">{o.client_name} <span class="badge badge-ok" style="font-size:11px;">PAYÉ</span></div>
<div class="order-meta">
<span>📱 <a href="https://wa.me/{o.whatsapp_number}" target="_blank">{o.whatsapp_number}</a></span>
<span class="{plan_class}">📦 {o.plan_type.upper()} — {o.payment_amount:,} Ar</span>
<span>✅ Validé le {o.validated_at.strftime('%d/%m/%Y %H:%M') if o.validated_at else '-'}</span>
</div>
<div class="order-key">🔑 {o.license_key}</div>
</div>
<div><a class="dl-btn" href="{dl_url}" target="_blank">📥 Télécharger .rsc</a></div>
</div>
</div>"""
    html += '</div>'

    # Commandes rejetées
    if expired:
        html += f'<h2 style="color:#ef4444;">❌ Rejetées ({len(expired)})</h2><div class="card-grid">'
        for o in expired:
            html += f"""<div class="order-card" style="border-color:#ef444433;opacity:.6;">
<div class="order-name">{o.client_name} — #{o.id} — {o.plan_type.upper()}</div>
<div class="order-key">{o.license_key}</div>
</div>"""
        html += '</div>'

    html += '</body></html>'
    return html


# ============================================================
# API ADMIN : VALIDER UNE COMMANDE
# ============================================================
@app.route("/api/admin/validate/<int:order_id>", methods=["POST"])
def api_admin_validate(order_id):
    """Valide le paiement d'une commande"""
    if request.args.get("pwd", "") != ADMIN_PASSWORD:
        return "Non autorisé", 403
    order = Order.query.get(order_id)
    if not order:
        return "Commande introuvable", 404
    order.payment_status = "validated"
    order.validated_at = datetime.utcnow()
    db.session.commit()
    return redirect(f"/admin?pwd={ADMIN_PASSWORD}")


# ============================================================
# API ADMIN : REJETER UNE COMMANDE
# ============================================================
@app.route("/api/admin/reject/<int:order_id>", methods=["POST"])
def api_admin_reject(order_id):
    """Rejette une commande non payée"""
    if request.args.get("pwd", "") != ADMIN_PASSWORD:
        return "Non autorisé", 403
    order = Order.query.get(order_id)
    if not order:
        return "Commande introuvable", 404
    order.payment_status = "expired"
    db.session.commit()
    return redirect(f"/admin?pwd={ADMIN_PASSWORD}")


# ============================================================
# REDIRECTION TUTORIEL
# ============================================================
@app.route("/tutoriel")
def tutoriel():
    """Redirige vers la section tutoriel de la page d'accueil"""
    return redirect(url_for("index") + "#tutoriel")


# ============================================================
# GESTION ERREURS
# ============================================================
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Page introuvable"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Erreur interne du serveur"}), 500


# ============================================================
# LANCEMENT
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
