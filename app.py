# -*- coding: utf-8 -*-
"""KETRIKA MIKROTIK 301 - Application Flask"""

from flask import Flask, render_template, request, jsonify, Response, redirect, send_file
from database import (
    db, Order, init_db, generate_license_key, generate_router_name,
    generate_random_mac, get_model_info, get_plan_price, MIKROTIK_MODELS
)
from warp_api import generate_rsc, generate_tutorial_txt, register_warp_device
from datetime import datetime
import json, os, io, zipfile

MVOLA_NUMBER = "038 28 171 00"
WHATSAPP_NUMBER = "261382817100"
WHATSAPP_LINK = "https://wa.me/261382817100"
ADMIN_PASSWORD = "ketrika2024"
APP_VERSION = "301"

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ketrika.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "ketrika-301-secret")
init_db(app)


@app.route("/")
def index():
    return render_template("index.html",
        mvola_number=MVOLA_NUMBER, whatsapp_number=WHATSAPP_NUMBER,
        whatsapp_link=WHATSAPP_LINK, models=MIKROTIK_MODELS, version=APP_VERSION)


@app.route("/api/models")
def api_models():
    return jsonify(MIKROTIK_MODELS)


@app.route("/api/check-license", methods=["POST"])
def api_check_license():
    data = request.get_json(force=True, silent=True) or {}
    key = (data.get("license_key") or "").strip().upper()
    if not key:
        return jsonify({"success": False, "error": "Saisissez une cle."}), 400
    order = Order.query.filter_by(license_key=key).first()
    if not order:
        return jsonify({"success": False, "error": "Licence introuvable."}), 404
    r = {
        "success": True, "license_key": order.license_key,
        "client_name": order.client_name, "plan_type": order.plan_type,
        "payment_status": order.payment_status, "router_name": order.router_name,
        "mikrotik_model": order.mikrotik_model, "amount": order.payment_amount,
        "created_at": order.created_at.strftime("%d/%m/%Y %H:%M"),
    }
    if order.payment_status == "validated":
        r["download_url"] = f"/api/download/{order.license_key}.zip"
        r["download_rsc_url"] = f"/api/download/{order.license_key}.rsc"
        r["validated_at"] = order.validated_at.strftime("%d/%m/%Y %H:%M") if order.validated_at else ""
    elif order.payment_status == "pending":
        r["mvola_number"] = MVOLA_NUMBER
        r["whatsapp_link"] = f"{WHATSAPP_LINK}?text=Paiement%20{order.license_key}"
    return jsonify(r)


@app.route("/api/order", methods=["POST"])
def api_order():
    try:
        data = request.get_json(force=True, silent=True) or {}
        plan = data.get("plan_type", "essentiel")
        if plan not in ("essentiel", "performance", "business"):
            return jsonify({"success": False, "error": "Plan invalide."}), 400
        cn = (data.get("client_name") or "").strip()
        wa = (data.get("whatsapp_number") or "").strip()
        if not cn:
            return jsonify({"success": False, "error": "Nom obligatoire."}), 400
        if not wa or len(wa) < 9:
            return jsonify({"success": False, "error": "WhatsApp invalide."}), 400

        mk = data.get("mikrotik_model", "hap_ac2")
        if mk not in MIKROTIK_MODELS: mk = "hap_ac2"

        lic = generate_license_key()
        rn = (data.get("router_name") or "").strip() or generate_router_name(lic)
        ms = bool(data.get("mac_spoof", False))
        ma = (data.get("mac_address") or "").strip()
        if ms and not ma: ma = generate_random_mac()

        def si(v, d=0):
            try: return int(v) if v else d
            except: return d

        # Inscription WARP pour plans performance/business
        warp_priv = warp_pub = warp_ip4 = warp_ip6 = warp_cid = ""
        if plan in ("performance", "business"):
            warp_data = register_warp_device()
            if warp_data:
                warp_priv = warp_data.get("private_key", "")
                warp_pub = warp_data.get("public_key", "")
                warp_ip4 = warp_data.get("ipv4", "")
                warp_ip6 = warp_data.get("ipv6", "")
                warp_cid = warp_data.get("client_id", "")

        order = Order(
            license_key=lic, client_name=cn, whatsapp_number=wa, plan_type=plan,
            mikrotik_model=mk, router_name=rn,
            ssid_2g=(data.get("ssid_2g") or "").strip(),
            ssid_5g=(data.get("ssid_5g") or "").strip(),
            wifi_password=(data.get("wifi_password") or "").strip(),
            wan_interface=data.get("wan_interface") or "ether1",
            lan_gateway=data.get("lan_gateway") or "192.168.10.1",
            lan_network=data.get("lan_network") or "192.168.10.0/24",
            dhcp_pool_start=data.get("dhcp_pool_start") or "192.168.10.10",
            dhcp_pool_end=data.get("dhcp_pool_end") or "192.168.10.250",
            ttl_value=si(data.get("ttl_value")),
            mac_spoof=ms, mac_address=ma,
            dl_limit=si(data.get("dl_limit")), ul_limit=si(data.get("ul_limit")),
            client_limit=si(data.get("client_limit")),
            sleep_mode=data.get("sleep_mode") or "off",
            sleep_start=(data.get("sleep_start") or "").strip(),
            sleep_end=(data.get("sleep_end") or "").strip(),
            hotspot_tickets_count=si(data.get("hotspot_tickets_count")),
            hotspot_profiles=json.dumps(data.get("hotspot_profiles", [])),
            payment_status="pending", payment_amount=get_plan_price(plan),
            terms_accepted=bool(data.get("terms_accepted")),
            warp_private_key=warp_priv, warp_public_key=warp_pub,
            warp_ipv4=warp_ip4, warp_ipv6=warp_ip6, warp_client_id=warp_cid,
        )
        db.session.add(order)
        db.session.commit()

        return jsonify({
            "success": True, "order_id": order.id, "license_key": lic,
            "amount": order.payment_amount, "plan_type": plan, "router_name": rn,
            "mvola_number": MVOLA_NUMBER,
            "whatsapp_link": f"{WHATSAPP_LINK}?text=Paiement%20commande%20%23{order.id}%20{lic}%20{order.payment_amount}Ar",
            "warp_registered": bool(warp_priv),
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/download/<license_key>.rsc")
def api_download_rsc(license_key):
    o = Order.query.filter_by(license_key=license_key.strip().upper()).first()
    if not o: return "Introuvable", 404
    if o.payment_status != "validated": return "Non valide", 403
    rsc = generate_rsc(o, get_model_info(o.mikrotik_model))
    return Response(rsc, mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="ketrika_{o.license_key}.rsc"'})


@app.route("/api/download/<license_key>.zip")
def api_download_zip(license_key):
    o = Order.query.filter_by(license_key=license_key.strip().upper()).first()
    if not o: return "Introuvable", 404
    if o.payment_status != "validated": return "Non valide", 403
    mi = get_model_info(o.mikrotik_model)
    rsc = generate_rsc(o, mi)
    fn = f"ketrika_{o.license_key}.rsc"
    tut = generate_tutorial_txt(o, fn)
    cmd = f"/import file-name={fn}\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(fn, rsc)
        z.writestr("LISEZ-MOI-INSTALLATION.txt", tut)
        z.writestr("COMMANDE-A-COPIER.txt", cmd)
    buf.seek(0)
    return send_file(buf, mimetype='application/zip', as_attachment=True,
        download_name=f"KETRIKA_{o.license_key}.zip")


@app.route("/admin")
def admin():
    pwd = request.args.get("pwd", "")
    if pwd != ADMIN_PASSWORD:
        return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Admin</title><style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#0f172a;color:#e2e8f0;font-family:system-ui;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px;}}
.b{{background:#1e293b;border-radius:16px;padding:40px;max-width:400px;width:100%;text-align:center;}}h1{{color:#38bdf8;margin-bottom:24px;}}
input{{width:100%;padding:14px;background:#0f172a;border:1px solid #334155;border-radius:8px;color:#e2e8f0;font-size:16px;margin-bottom:16px;}}
button{{width:100%;padding:14px;background:#38bdf8;color:#000;border:none;border-radius:8px;font-weight:700;cursor:pointer;font-size:16px;}}</style></head>
<body><div class="b"><h1>KETRIKA Admin</h1><form method="get"><input type="password" name="pwd" placeholder="Mot de passe" required autofocus><button>Entrer</button></form></div></body></html>"""

    pending = Order.query.filter_by(payment_status="pending").order_by(Order.created_at.desc()).all()
    validated = Order.query.filter_by(payment_status="validated").order_by(Order.validated_at.desc()).limit(100).all()

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KETRIKA Admin</title><style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:16px;}}
h1{{color:#38bdf8;margin-bottom:20px;}}h2{{margin:24px 0 12px;font-size:18px;}}
.c{{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:16px;margin-bottom:12px;}}
.n{{font-weight:700;font-size:16px;margin-bottom:6px;}}.m{{font-size:13px;color:#94a3b8;line-height:1.6;}}.m a{{color:#10b981;}}
.k{{font-family:monospace;font-size:11px;color:#64748b;word-break:break-all;margin-top:6px;}}
.a{{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;}}
button,.d{{padding:10px 16px;border:none;border-radius:8px;font-weight:700;cursor:pointer;font-size:14px;text-decoration:none;display:inline-block;}}
.v{{background:#10b981;color:#000;}}.r{{background:#ef4444;color:#fff;}}.d{{background:#38bdf8;color:#000;}}.z{{background:#8b5cf6;color:#fff;}}
.w{{background:#f59e0b22;color:#f59e0b;padding:4px 10px;border-radius:12px;font-size:11px;font-weight:700;}}
</style></head><body>
<h1>KETRIKA MIKROTIK {APP_VERSION} - Admin</h1>
<div style="margin-bottom:20px;"><span class="w">⏳ {len(pending)} en attente</span></div>
<h2>En attente</h2>"""

    for o in pending:
        html += f"""<div class="c"><div class="n">{o.client_name} — #{o.id}</div>
<div class="m">📱 <a href="https://wa.me/{o.whatsapp_number}" target="_blank">{o.whatsapp_number}</a><br>
📦 {o.plan_type.upper()} — <b>{o.payment_amount:,} Ar</b><br>
🔧 {o.mikrotik_model} | WARP: {'✅' if o.warp_private_key else '❌'}<br>
📅 {o.created_at.strftime('%d/%m %H:%M')}</div>
<div class="k">{o.license_key}</div>
<div class="a">
<form method="post" action="/api/admin/validate/{o.id}?pwd={ADMIN_PASSWORD}"><button class="v">✅ Valider</button></form>
<form method="post" action="/api/admin/reject/{o.id}?pwd={ADMIN_PASSWORD}"><button class="r">❌</button></form></div></div>"""

    html += f'<h2>Validées ({len(validated)})</h2>'
    for o in validated:
        html += f"""<div class="c"><div class="n">{o.client_name} #{o.id}</div>
<div class="m">{o.plan_type.upper()} | <a href="https://wa.me/{o.whatsapp_number}">{o.whatsapp_number}</a></div>
<div class="k">{o.license_key}</div>
<div class="a"><a class="z" href="/api/download/{o.license_key}.zip">📦 ZIP</a>
<a class="d" href="/api/download/{o.license_key}.rsc">📥 RSC</a></div></div>"""

    html += '</body></html>'
    return html


@app.route("/api/admin/validate/<int:oid>", methods=["POST"])
def validate(oid):
    if request.args.get("pwd") != ADMIN_PASSWORD: return "Non", 403
    o = Order.query.get(oid)
    if not o: return "?", 404
    o.payment_status = "validated"
    o.validated_at = datetime.utcnow()
    db.session.commit()
    return redirect(f"/admin?pwd={ADMIN_PASSWORD}")


@app.route("/api/admin/reject/<int:oid>", methods=["POST"])
def reject(oid):
    if request.args.get("pwd") != ADMIN_PASSWORD: return "Non", 403
    o = Order.query.get(oid)
    if not o: return "?", 404
    o.payment_status = "expired"
    db.session.commit()
    return redirect(f"/admin?pwd={ADMIN_PASSWORD}")


@app.errorhandler(404)
def e404(e): return jsonify({"error": "Introuvable"}), 404

@app.errorhandler(500)
def e500(e): return jsonify({"error": "Erreur serveur"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
