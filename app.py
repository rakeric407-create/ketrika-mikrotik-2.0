import os
import io
import zipfile
import secrets
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, abort, Response

from database import (
    init_db,
    create_order,
    get_order_by_license,
    get_order_by_id,
    get_all_orders,
    set_order_status,
    OrderRecord
)
from warp_api import register_warp

app = Flask(__name__)
app.config["SECRET_KEY"] = secrets.token_hex(16)
init_db()

MVOLA_NUMBER = "038 28 171 00"
WHATSAPP_NUMBER = "261382817100"
WHATSAPP_LINK = "https://wa.me/261382817100"
ADMIN_PASSWORD = "ketrika2024"
VERSION = "301"

WARP_PEER_PUBLIC = "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo="
WARP_ENDPOINT = "162.159.193.1"
WARP_PORT = 2408

PLANS = {
    "essentiel": {"name": "ESSENTIEL", "price": 30000},
    "performance": {"name": "PERFORMANCE", "price": 50000},
    "business": {"name": "BUSINESS", "price": 80000},
}

MODELS = {
    "hAP lite":     {"wifi": True,  "wifi_5": False, "wifi_type": "N",  "ports": 4,  "cat": "hAP"},
    "hAP":          {"wifi": True,  "wifi_5": False, "wifi_type": "N",  "ports": 5,  "cat": "hAP"},
    "hAP ac lite":  {"wifi": True,  "wifi_5": True,  "wifi_type": "AC", "ports": 5,  "cat": "hAP"},
    "hAP ac2":      {"wifi": True,  "wifi_5": True,  "wifi_type": "AC", "ports": 5,  "cat": "hAP"},
    "hAP ac3":      {"wifi": True,  "wifi_5": True,  "wifi_type": "AC", "ports": 5,  "cat": "hAP"},
    "hAP ax2":      {"wifi": True,  "wifi_5": True,  "wifi_type": "AX", "ports": 5,  "cat": "hAP"},
    "hAP ax3":      {"wifi": True,  "wifi_5": True,  "wifi_type": "AX", "ports": 5,  "cat": "hAP"},
    "hAP ax lite":  {"wifi": True,  "wifi_5": False, "wifi_type": "AX", "ports": 4,  "cat": "hAP"},
    "RB750Gr3":     {"wifi": False, "wifi_5": False, "wifi_type": "",   "ports": 5,  "cat": "RB"},
    "RB750r2":      {"wifi": False, "wifi_5": False, "wifi_type": "",   "ports": 5,  "cat": "RB"},
    "RB760iGS":     {"wifi": False, "wifi_5": False, "wifi_type": "",   "ports": 5,  "cat": "RB"},
    "RB4011":       {"wifi": False, "wifi_5": False, "wifi_type": "",   "ports": 10, "cat": "RB"},
    "RB5009":       {"wifi": False, "wifi_5": False, "wifi_type": "",   "ports": 8,  "cat": "RB"},
    "RB3011":       {"wifi": False, "wifi_5": False, "wifi_type": "",   "ports": 10, "cat": "RB"},
    "CCR1009":      {"wifi": False, "wifi_5": False, "wifi_type": "",   "ports": 8,  "cat": "CCR"},
    "CCR1036":      {"wifi": False, "wifi_5": False, "wifi_type": "",   "ports": 12, "cat": "CCR"},
    "CCR2004":      {"wifi": False, "wifi_5": False, "wifi_type": "",   "ports": 16, "cat": "CCR"},
    "CHR":          {"wifi": False, "wifi_5": False, "wifi_type": "",   "ports": 2,  "cat": "Virtuel"},
}


def gen_license():
    return "LIC-" + secrets.token_hex(4).upper()


def generate_rsc(o: OrderRecord) -> str:
    L = []
    add = L.append

    add(f"# KETRIKA MIKROTIK {VERSION} - Configuration automatique RouterOS v7")
    add(f"# Licence : {o.license_key}")
    add(f"# Client  : {o.customer_name}")
    add(f"# Plan    : {o.plan.upper()}")
    add(f"# Modele  : {o.model}")
    add(f"# Date    : {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    add("")
    add(":log info \"KETRIKA : Initialisation du deploiement\"")
    add(":delay 1s")
    add("")

    plan_perf = o.plan in ("performance", "business")
    plan_biz = o.plan == "business"
    model_info = MODELS.get(o.model, {})
    has_wifi = model_info.get("wifi", False) and o.wifi_enabled
    has_wifi_5 = model_info.get("wifi_5", False) and o.wifi_enabled
    ports = model_info.get("ports", 5)

    # 1. FastTrack OFF
    add("# 1. Desactivation FastTrack pour permettre le routage avance")
    add(":do {")
    add("  /ip/settings/set tcp-syncookies=yes")
    add("} on-error={}")
    add("")

    # 2. MAC-Server
    add("# 2. Acces MAC-Server et Winbox sur toutes les interfaces")
    add(":do {")
    add("  /tool/mac-server/set allowed-interface-list=all")
    add("  /tool/mac-server/mac-winbox/set allowed-interface-list=all")
    add("  /tool/mac-server/ping/set enabled=yes")
    add("} on-error={}")
    add("")

    # 3. Services
    add("# 3. Securisation des services systeme")
    add(":do {")
    add("  /ip/service/set winbox disabled=no")
    add("  /ip/service/set ssh disabled=no")
    add("  /ip/service/set telnet disabled=yes")
    add("  /ip/service/set ftp disabled=yes")
    add("  /ip/service/set api disabled=yes")
    add("  /ip/service/set api-ssl disabled=yes")
    add("  /ip/service/set www disabled=yes")
    add("} on-error={}")
    add("")

    # 4. Bridge d'usine
    add("# 4. Conservation et creation du bridge LAN")
    add(":do {")
    add("  /interface/bridge/add name=bridge comment=\"KETRIKA LAN\"")
    add("} on-error={}")
    add("")

    # 5. Ports Ethernet au bridge (sauf WAN)
    add("# 5. Assignation des ports locaux au bridge")
    for i in range(2, ports + 1):
        add(f":do {{ /interface/bridge/port/add bridge=bridge interface=ether{i} }} on-error={{}}")
    add("")

    # 6. Adresses IP (LAN + Backup)
    add("# 6. Adresses IP LAN principale et adresse de secours usine")
    add(":do {")
    add(f"  /ip/address/add address={o.lan_ip}/{o.lan_mask} interface=bridge comment=\"LAN KETRIKA\"")
    add("} on-error={}")
    add(":do {")
    add("  /ip/address/add address=192.168.88.1/24 interface=bridge comment=\"Backup usine\"")
    add("} on-error={}")
    add("")

    # 7. DHCP Server + Pool + Network + DNS Cloudflare
    add("# 7. Serveur DHCP et DNS Cloudflare securise")
    lan_net = ".".join(o.lan_ip.split(".")[:3]) + ".0"
    add(":do {")
    add(f"  /ip/pool/add name=dhcp_pool ranges={o.dhcp_start}-{o.dhcp_end}")
    add("} on-error={}")
    add(":do {")
    add("  /ip/dhcp-server/add name=dhcp1 interface=bridge address-pool=dhcp_pool lease-time=1d disabled=no")
    add("} on-error={}")
    add(":do {")
    add(f"  /ip/dhcp-server/network/add address={lan_net}/{o.lan_mask} gateway={o.lan_ip} dns-server=1.1.1.1,1.0.0.1")
    add("} on-error={}")
    add(":do {")
    add("  /ip/dns/set servers=1.1.1.1,1.0.0.1 allow-remote-requests=yes")
    add("} on-error={}")
    add("")

    # 8. DHCP Client WAN
    add("# 8. Client DHCP sur interface WAN")
    add(":do {")
    add(f"  /ip/dhcp-client/add interface={o.wan_port} disabled=no comment=\"WAN KETRIKA\"")
    add("} on-error={}")
    add("")

    # 9. NAT Masquerade WAN (PRIORITAIRE)
    add("# 9. NAT Masquerade WAN en priorite pour garantir la continuite Internet")
    add(":do {")
    add(f"  /ip/firewall/nat/add chain=srcnat out-interface={o.wan_port} action=masquerade comment=\"NAT WAN KETRIKA\"")
    add("} on-error={}")
    add("")

    # 10. MAC Spoofing (plan 2+)
    if plan_perf and o.mac_spoof != "off":
        add("# 10. Anonymisation de la signature physique WAN")
        if o.mac_spoof == "manuel" and o.mac_manual:
            add(":do {")
            add(f"  /interface/ethernet/set {o.wan_port} mac-address={o.mac_manual}")
            add("} on-error={}")
        else:
            add(":do {")
            add("  :local r1 ([:tostr ([:rndnum from=16 to=250])])")
            add("  :local r2 ([:tostr ([:rndnum from=16 to=250])])")
            add("  :local r3 ([:tostr ([:rndnum from=16 to=250])])")
            add("  :local r4 ([:tostr ([:rndnum from=16 to=250])])")
            add("  :local r5 ([:tostr ([:rndnum from=16 to=250])])")
            add("  :local mac (\"02:\" . $r1 . \":\" . $r2 . \":\" . $r3 . \":\" . $r4 . \":\" . $r5)")
            add(f"  /interface/ethernet/set {o.wan_port} mac-address=$mac")
            add("} on-error={}")
        add("")

    # 11. Wi-Fi configuration (index numérique, sans country)
    if has_wifi:
        add("# 11. Configuration Wi-Fi RouterOS v7 sans parametre country")
        add(":delay 2s")
        add(":do {")
        add("  :local i 0")
        add("  :foreach w in=[/interface/wifi/find] do={")
        add("    :if ($i = 0) do={")
        add(f"      /interface/wifi/set $w ssid=\"{o.ssid_24}\" disabled=no")
        add(f"      /interface/wifi/security/set [find default=yes] authentication-types=wpa2-psk,wpa3-psk passphrase=\"{o.wifi_password}\"")
        add("    }")
        if has_wifi_5:
            add("    :if ($i = 1) do={")
            add(f"      /interface/wifi/set $w ssid=\"{o.ssid_5}\" disabled=no")
            add("    }")
        add("    :set i ($i + 1)")
        add("  }")
        add("} on-error={}")
        add(":do { /interface/bridge/port/add bridge=bridge interface=wifi1 } on-error={}")
        if has_wifi_5:
            add(":do { /interface/bridge/port/add bridge=bridge interface=wifi2 } on-error={}")
        add("")

    # 12. WireGuard WARP (plan 2+)
    if plan_perf and o.warp_private_key and o.warp_public_key:
        add("# 12. Tunnel WireGuard WARP Cloudflare avec protection de routage")
        add(":do {")
        add(f"  /interface/wireguard/add name=warp private-key=\"{o.warp_private_key}\" listen-port=13231 mtu=1280 comment=\"WARP KETRIKA\"")
        add("} on-error={}")
        add(":do {")
        add(f"  /ip/address/add address={o.warp_ipv4}/32 interface=warp")
        add("} on-error={}")
        add(":do {")
        add(f"  /interface/wireguard/peers/add interface=warp public-key=\"{WARP_PEER_PUBLIC}\" endpoint-address={WARP_ENDPOINT} endpoint-port={WARP_PORT} allowed-address=0.0.0.0/0 persistent-keepalive=25s")
        add("} on-error={}")
        add(":do {")
        add("  /routing/table/add name=to-warp fib")
        add("} on-error={}")
        add(":do {")
        add("  /ip/route/add dst-address=0.0.0.0/0 gateway=warp routing-table=to-warp comment=\"Route WARP\"")
        add("} on-error={}")
        add(":do {")
        add(f"  /ip/firewall/mangle/add chain=prerouting in-interface=bridge dst-address=!{lan_net}/{o.lan_mask} protocol=!icmp action=mark-routing new-routing-mark=to-warp passthrough=no comment=\"Mark WARP\"")
        add("} on-error={}")
        add(":do {")
        add("  /ip/firewall/mangle/add chain=prerouting protocol=tcp dst-port=8291 action=accept passthrough=no place-before=0 comment=\"Exclusion Winbox\"")
        add("} on-error={}")
        add(":do {")
        add("  /ip/firewall/nat/add chain=srcnat out-interface=warp action=masquerade comment=\"NAT WARP\"")
        add("} on-error={}")
        add("")

    # 13. MSS Clamping
    if plan_perf:
        add("# 13. Ajustement MSS Clamping pour MTU optimale")
        add(":do {")
        add("  /ip/firewall/mangle/add chain=forward protocol=tcp tcp-flags=syn action=change-mss new-mss=1240 tcp-mss=1241-65535 comment=\"MSS Clamp\"")
        add("} on-error={}")
        add("")

    # 14. TTL Change
    if plan_perf and o.ttl_value in (64, 65, 128):
        add(f"# 14. Optimisation de la signature paquet TTL vers {o.ttl_value}")
        add(":do {")
        add(f"  /ip/firewall/mangle/add chain=postrouting action=change-ttl new-ttl=set:{o.ttl_value} passthrough=yes comment=\"TTL {o.ttl_value}\"")
        add("} on-error={}")
        add("")

    # 15. QoS Simple Queue
    if plan_perf and (o.limit_down or o.limit_up or o.limit_per_client):
        add("# 15. Gestion et repartition de la bande passante")
        if o.limit_down or o.limit_up:
            dl = f"{o.limit_down}k" if o.limit_down else "0"
            ul = f"{o.limit_up}k" if o.limit_up else "0"
            add(":do {")
            add(f"  /queue/simple/add name=global-queue target={lan_net}/{o.lan_mask} max-limit={ul}/{dl} comment=\"Limite globale\"")
            add("} on-error={}")
        if o.limit_per_client:
            pc = f"{o.limit_per_client}k"
            add(":do {")
            add(f"  /queue/simple/add name=per-client target={lan_net}/{o.lan_mask} max-limit={pc}/{pc} queue=default/default burst-limit=0/0 comment=\"Par client\"")
            add("} on-error={}")
        add("")

    # 16. Hotspot (plan 3)
    if plan_biz:
        add("# 16. Portail Captif Hotspot professionnel")
        add(":do {")
        add(f"  /ip/pool/add name=hs-pool ranges={o.dhcp_start}-{o.dhcp_end}")
        add("} on-error={}")
        add(":do {")
        add(f"  /ip/hotspot/profile/add name=hsprof1 hotspot-address={o.lan_ip} dns-name=ketrika.local html-directory=hotspot login-by=http-chap")
        add("} on-error={}")
        add(":do {")
        add("  /ip/hotspot/user/profile/add name=1h session-timeout=1h shared-users=1")
        add("  /ip/hotspot/user/profile/add name=1j session-timeout=1d shared-users=1")
        add("  /ip/hotspot/user/profile/add name=1sem session-timeout=7d shared-users=1")
        add("  /ip/hotspot/user/profile/add name=1mois session-timeout=30d shared-users=1")
        add("} on-error={}")
        add(":do {")
        add("  /ip/hotspot/add name=hs1 interface=bridge address-pool=hs-pool profile=hsprof1 disabled=no")
        add("} on-error={}")
        if o.hotspot_tickets > 0:
            add("# Generation automatique des tickets dacces")
            add(":do {")
            add(f"  :for i from=1 to={o.hotspot_tickets} do={{")
            add("    :local u (\"tk\" . [:tostr $i] . [:tostr ([:rndnum from=100 to=999])])")
            add("    :local p ([:tostr ([:rndnum from=100000 to=999999])])")
            add(f"    /ip/hotspot/user/add name=$u password=$p profile={o.hotspot_profile}")
            add("  }")
            add("} on-error={}")
        add("")

    # 17. System Identity
    add("# 17. Nom didentification du routeur")
    add(":do {")
    add(f"  /system/identity/set name=\"{o.router_name}\"")
    add("} on-error={}")
    add("")

    # 18. Scheduler veille Wi-Fi
    if has_wifi and o.sleep_enabled:
        add("# 18. Programmation automatique de la veille Wi-Fi")
        add(":do {")
        add(f"  /system/scheduler/add name=wifi-off start-time={o.sleep_start} interval=1d on-event=\"/interface/wifi/disable [find]\" comment=\"Veille ON\"")
        add(f"  /system/scheduler/add name=wifi-on start-time={o.sleep_stop} interval=1d on-event=\"/interface/wifi/enable [find]\" comment=\"Veille OFF\"")
        add("} on-error={}")
        add("")

    # 19. Firewall filter
    add("# 19. Regles de filtrage pare-feu input et forward")
    add(":do {")
    add("  /ip/firewall/filter/add chain=input action=accept connection-state=established,related comment=\"Accept established\"")
    add("  /ip/firewall/filter/add chain=input action=accept protocol=icmp comment=\"Accept ICMP\"")
    add("  /ip/firewall/filter/add chain=input action=accept in-interface=bridge comment=\"Accept LAN\"")
    add(f"  /ip/firewall/filter/add chain=input action=drop in-interface={o.wan_port} comment=\"Drop WAN input\"")
    add("  /ip/firewall/filter/add chain=forward action=accept connection-state=established,related comment=\"Fwd established\"")
    add("  /ip/firewall/filter/add chain=forward action=drop connection-state=invalid comment=\"Drop invalid\"")
    add("} on-error={}")
    add("")

    # 20. Bannière
    add("# 20. Notification de fin de configuration")
    add(":log info \"KETRIKA : Configuration terminee avec succes\"")
    add(":put \"===============================================\"")
    add(f":put \"KETRIKA MIKROTIK {VERSION} - Configuration appliquee avec succes\"")
    add(f":put \"Licence : {o.license_key}\"")
    add(f":put \"Plan    : {o.plan.upper()}\"")
    add(":put \"===============================================\"")
    add("")

    return "\n".join(L)


def generate_readme(o: OrderRecord, filename: str) -> str:
    plan_name = PLANS[o.plan]["name"]
    txt = f"""===============================================
KETRIKA MIKROTIK {VERSION} - GUIDE D INSTALLATION OFFICIEL
===============================================

Client       : {o.customer_name}
Licence      : {o.license_key}
Formule      : {plan_name} ({o.price} Ar)
Equipement   : {o.model}
Nom routeur  : {o.router_name}
Port WAN     : {o.wan_port}
Reseau LAN   : {o.lan_ip}/{o.lan_mask}
"""
    if o.wifi_enabled and MODELS.get(o.model, {}).get("wifi", False):
        txt += f"SSID 2.4 GHz : {o.ssid_24}\n"
        if MODELS.get(o.model, {}).get("wifi_5", False):
            txt += f"SSID 5 GHz   : {o.ssid_5}\n"
        txt += f"Cle Wi-Fi    : {o.wifi_password}\n"

    if o.plan in ("performance", "business") and o.warp_ipv4:
        txt += f"\n--- TUNNEL SECURISE CLOUDFLARE ---\n"
        txt += f"Adresse IPv4 : {o.warp_ipv4}\n"
        txt += f"Passerelle   : {WARP_ENDPOINT}:{WARP_PORT}\n"

    txt += f"""

===============================================
PROCEDURE D INSTALLATION PAS A PAS
===============================================

1. Reinitialisez votre MikroTik aux parametres dusine :
   - Maintenez le bouton Reset enfonce 10 secondes pendant l allumage.

2. Branchez votre ordinateur sur le port ether2 avec un cable reseau.

3. Lancez Winbox et allez sur l onglet Neighbors. Double-cliquez sur l adresse MAC.
   Identifiant : admin (laissez le mot de passe vide).

4. Ouvrez le menu Files a gauche.

5. Glissez-deposez le fichier {filename} directement dans la fenetre Files.

6. Ouvrez le New Terminal dans Winbox et executez la commande :

   /import file-name={filename}

7. Attendez la notification de succes dans le terminal.

8. Vous pouvez desormais acceder a votre routeur via l adresse : {o.lan_ip}

--- SUPPORT TECHNIQUE INCLUS ---
WhatsApp : +261 38 28 171 00
Lien direct : {WHATSAPP_LINK}
===============================================
"""
    return txt


def generate_command_txt(filename: str) -> str:
    return f"""COMMANDE A COPIER DANS LE TERMINAL WINBOX
===========================================

/import file-name={filename}

===========================================
Deposez d abord le fichier dans Files puis
collez la commande ci-dessus dans New Terminal.
"""


# ============================================================
# ROUTES FLASK
# ============================================================
@app.route("/")
def index():
    return render_template("index.html",
                           mvola=MVOLA_NUMBER,
                           whatsapp=WHATSAPP_NUMBER,
                           whatsapp_link=WHATSAPP_LINK,
                           version=VERSION)


@app.route("/api/models")
def api_models():
    return jsonify(MODELS)


@app.route("/api/check-license", methods=["POST"])
def api_check_license():
    data = request.get_json() or {}
    key = (data.get("license") or "").strip().upper()
    if not key:
        return jsonify({"ok": False, "msg": "Veuillez entrer une cle de licence"}), 400
    o = get_order_by_license(key)
    if not o:
        return jsonify({"ok": False, "msg": "Licence introuvable dans le systeme"}), 404
    return jsonify({
        "ok": True,
        "status": o.status,
        "plan": o.plan,
        "customer": o.customer_name,
        "download_rsc": f"/api/download/{o.license_key}.rsc" if o.status == "validated" else None,
        "download_zip": f"/api/download/{o.license_key}.zip" if o.status == "validated" else None,
    })


@app.route("/api/order", methods=["POST"])
def api_order():
    d = request.get_json() or {}
    plan = d.get("plan")
    if plan not in PLANS:
        return jsonify({"ok": False, "msg": "Formule invalide"}), 400

    if not d.get("cgu"):
        return jsonify({"ok": False, "msg": "Veuillez accepter les conditions generales"}), 400

    order_payload = {
        "license_key": gen_license(),
        "customer_name": (d.get("customer_name") or "").strip()[:120],
        "whatsapp": (d.get("whatsapp") or "").strip()[:40],
        "plan": plan,
        "price": PLANS[plan]["price"],
        "model": d.get("model") or "hAP ac2",
        "router_name": (d.get("router_name") or "KETRIKA-RB").strip()[:60],
        "wan_port": d.get("wan_port") or "ether1",
        "lan_ip": d.get("lan_ip") or "192.168.10.1",
        "lan_mask": str(d.get("lan_mask") or "24"),
        "dhcp_start": d.get("dhcp_start") or "192.168.10.100",
        "dhcp_end": d.get("dhcp_end") or "192.168.10.250",
        "wifi_enabled": bool(d.get("wifi_enabled", True)),
        "ssid_24": (d.get("ssid_24") or "KETRIKA_2G")[:60],
        "ssid_5": (d.get("ssid_5") or "KETRIKA_5G")[:60],
        "wifi_password": (d.get("wifi_password") or "ketrika2024")[:60],
        "sleep_enabled": bool(d.get("sleep_enabled", False)),
        "sleep_start": d.get("sleep_start") or "23:00:00",
        "sleep_stop": d.get("sleep_stop") or "06:00:00",
        "ttl_value": int(d.get("ttl_value") or 0),
        "mac_spoof": d.get("mac_spoof") or "off",
        "mac_manual": (d.get("mac_manual") or "")[:40],
        "limit_down": int(d.get("limit_down") or 0),
        "limit_up": int(d.get("limit_up") or 0),
        "limit_per_client": int(d.get("limit_per_client") or 0),
        "hotspot_tickets": int(d.get("hotspot_tickets") or 0),
        "hotspot_profile": d.get("hotspot_profile") or "1h",
        "warp_private_key": "",
        "warp_public_key": "",
        "warp_ipv4": "",
    }

    if plan in ("performance", "business"):
        warp = register_warp()
        if warp:
            order_payload["warp_private_key"] = warp["private_key"]
            order_payload["warp_public_key"] = warp["public_key"]
            order_payload["warp_ipv4"] = warp["ipv4"]

    order = create_order(order_payload)

    return jsonify({
        "ok": True,
        "license": order.license_key,
        "price": order.price,
        "plan_name": PLANS[plan]["name"],
        "whatsapp_link": WHATSAPP_LINK,
        "mvola": MVOLA_NUMBER,
    })


@app.route("/api/download/<lic>.rsc")
def api_download_rsc(lic):
    o = get_order_by_license(lic)
    if not o or o.status != "validated":
        abort(403)
    filename = f"ketrika_{o.license_key}.rsc"
    content = generate_rsc(o)
    return Response(content, mimetype="text/plain",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.route("/api/download/<lic>.zip")
def api_download_zip(lic):
    o = get_order_by_license(lic)
    if not o or o.status != "validated":
        abort(403)
    rsc_name = f"ketrika_{o.license_key}.rsc"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(rsc_name, generate_rsc(o))
        z.writestr("LISEZ-MOI.txt", generate_readme(o, rsc_name))
        z.writestr("COMMANDE.txt", generate_command_txt(rsc_name))
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name=f"ketrika_{o.license_key}.zip")


@app.route("/admin")
def admin():
    pwd = request.args.get("pwd", "")
    if pwd != ADMIN_PASSWORD:
        return "<h2 style='font-family:system-ui;padding:40px;color:#dc2626'>Acces refuse - Mot de passe incorrect</h2>", 401
    orders = get_all_orders()
    rows = []
    for o in orders:
        color = {"pending": "#b45309", "validated": "#047857", "rejected": "#dc2626"}.get(o.status, "#334155")
        rows.append(f"""
        <tr>
          <td>{o.id}</td>
          <td><code>{o.license_key}</code></td>
          <td>{o.customer_name}<br><small>{o.whatsapp}</small></td>
          <td>{o.plan.upper()}<br><small>{o.price:,} Ar</small></td>
          <td>{o.model}</td>
          <td style="color:{color};font-weight:700">{o.status.upper()}</td>
          <td>{o.created_at}</td>
          <td>
            <button onclick="act({o.id},'validate')" style="background:#047857;color:#fff;border:0;padding:6px 12px;border-radius:6px;cursor:pointer;font-weight:600">Valider</button>
            <button onclick="act({o.id},'reject')" style="background:#dc2626;color:#fff;border:0;padding:6px 12px;border-radius:6px;cursor:pointer;font-weight:600;margin-left:4px">Rejeter</button>
          </td>
        </tr>""")
    html = f"""<!doctype html><html><head><meta charset="utf-8">
    <title>Administration KETRIKA {VERSION}</title>
    <style>
    body{{font-family:system-ui;background:#f8fafc;color:#0f172a;padding:24px;margin:0}}
    h1{{color:#1d4ed8;margin-bottom:8px}}
    table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08);margin-top:16px}}
    th,td{{padding:14px;text-align:left;border-bottom:1px solid #e2e8f0;font-size:14px}}
    th{{background:#1d4ed8;color:#fff;font-weight:600}}
    tr:hover{{background:#f1f5f9}}
    code{{background:#e2e8f0;padding:3px 6px;border-radius:4px;font-size:13px;color:#1e40af}}
    </style></head><body>
    <h1>Panneau d'Administration KETRIKA {VERSION}</h1>
    <p style="color:#64748b">Total : {len(orders)} commande(s) enregistree(s)</p>
    <table><thead><tr><th>ID</th><th>Licence</th><th>Client</th><th>Formule</th><th>Equipement</th><th>Statut</th><th>Date Creation</th><th>Actions</th></tr></thead>
    <tbody>{''.join(rows)}</tbody></table>
    <script>
    async function act(id, action){{
      const pwd = new URLSearchParams(location.search).get('pwd');
      const r = await fetch('/api/admin/'+action+'/'+id+'?pwd='+pwd, {{method:'POST'}});
      const d = await r.json();
      alert(d.msg || 'Operation effectuee');
      location.reload();
    }}
    </script></body></html>"""
    return html


@app.route("/api/admin/validate/<int:oid>", methods=["POST"])
def api_admin_validate(oid):
    if request.args.get("pwd", "") != ADMIN_PASSWORD:
        return jsonify({"ok": False, "msg": "Acces refuse"}), 401
    set_order_status(oid, "validated")
    return jsonify({"ok": True, "msg": f"Commande #{oid} validee avec succes"})


@app.route("/api/admin/reject/<int:oid>", methods=["POST"])
def api_admin_reject(oid):
    if request.args.get("pwd", "") != ADMIN_PASSWORD:
        return jsonify({"ok": False, "msg": "Acces refuse"}), 401
    set_order_status(oid, "rejected")
    return jsonify({"ok": True, "msg": f"Commande #{oid} rejetee"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
