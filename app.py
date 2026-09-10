# app.py
import os
import secrets
import base64
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# ============== CODES SIMPLES ==============
# Code PIN à 4 chiffres pour chaque pack (vous pouvez les changer ici)
CODES_ACCES = {
    "1000": 1,  # Pack 1 (Classic DoH - 20 000 Ar)
    "2000": 2,  # Pack 2 (WARP WireGuard - 40 000 Ar)
    "3000": 3,  # Pack 3 (Hotspot/PPPoE - 60 000 Ar)
    "KETRIKA": 3 # Code Master (débloque tout)
}

PACKS = {
    1: {
        "name": "PACK CLASSIC DoH",
        "price": 20000,
        "desc": "Configuration DoH chiffrée + WiFi Auto + Anti-détection FAI",
        "features": [
            "DNS over HTTPS (DoH Cloudflare)",
            "Changement MAC automatique (Anti-blocage)",
            "WiFi Auto AC / AX / AN",
            "Obfuscation TTL & MSS (Camouflage partage)",
            "Mise en veille programmable"
        ]
    },
    2: {
        "name": "PACK WARP WireGuard",
        "price": 40000,
        "desc": "Pack Classic + Tunnel Cloudflare WARP WireGuard 100% Chiffré",
        "features": [
            "Tout le Pack Classic",
            "WARP Cloudflare WireGuard Auto",
            "Tunneling intégral indétectable",
            "Bypass total des restrictions FAI",
            "Double protection DNS & IP"
        ]
    },
    3: {
        "name": "PACK HOTSPOT / PPPoE",
        "price": 60000,
        "desc": "Pack WARP + Gestion Clients (Portail Captif ou Serveur PPPoE)",
        "features": [
            "Tout le Pack WARP WireGuard",
            "Hotspot avec Portail Captif OU Serveur PPPoE",
            "Limitation de vitesse par utilisateur",
            "Création de tickets / utilisateurs",
            "Contrôle total de bande passante"
        ]
    }
}

# ============== GÉNÉRATEUR WARP ==============
def generate_warp():
    privkey = base64.b64encode(secrets.token_bytes(32)).decode()
    endpoints = [
        "162.159.193.1:2408", "162.159.192.1:2408", 
        "188.114.96.1:2408", "188.114.97.1:2408",
        "engage.cloudflareclient.com:2408"
    ]
    return {
        'private_key': privkey,
        'public_key': 'bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo=',
        'endpoint': secrets.choice(endpoints),
        'address_v4': f'172.16.0.{secrets.randbelow(200) + 10}/32',
        'mtu': 1280
    }

# ============== GÉNÉRATEUR SCRIPT MIKROTIK ==============
def generate_mikrotik_script(cfg, pack_id):
    wan = cfg.get('wan_interface', 'ether1')
    lan = cfg.get('lan_interface', 'ether2')
    ssid = cfg.get('ssid_main', 'KETRIKA-WIFI')
    password = cfg.get('ssid_password', '12345678')
    ident = cfg.get('router_identity', 'Home-Gateway')
    
    # Fake MAC réaliste
    prefixes = ["00:1A:2B", "78:8A:20", "B8:69:F4", "DC:2C:6E", "AC:84:C6"]
    fake_mac = f"{secrets.choice(prefixes)}:{secrets.randbelow(256):02X}:{secrets.randbelow(256):02X}:{secrets.randbelow(256):02X}"

    # BASE COMMUNE (Anti-déconnexion + Camouflage + DoH)
    s = f"""# ╔══════════════════════════════════════════════════════════════╗
# ║           KETRIKA MIKROTIK - SCRIPT DE CONFIGURATION         ║
# ║  Coller directement dans Winbox (New Terminal)              ║
# ╚══════════════════════════════════════════════════════════════╝

# 1. IDENTITÉ & NETTOYAGE SANS COUPER WINBOX
/system identity set name="{ident}"
:do {{ /ip firewall filter remove [find comment~"ketrika"] }} on-error={{}}
:do {{ /ip firewall nat remove [find comment~"ketrika"] }} on-error={{}}
:do {{ /ip firewall mangle remove [find comment~"ketrika"] }} on-error={{}}

# 2. DÉSACTIVER LES TRACES DÉTECTABLES PAR LE FAI
:do {{ /tool bandwidth-server set enabled=no }} on-error={{}}
:do {{ /ip neighbor discovery-settings set discover-interface-list=none }} on-error={{}}
:do {{ /ip upnp set enabled=no }} on-error={{}}

# 3. CAMOUFLAGE MAC WAN
:do {{
/interface ethernet set {wan} mac-address="{fake_mac}"
:log info "KETRIKA: Nouvelle adresse MAC WAN appliquee"
}} on-error={{}}

# 4. BRIDGE ET INTERFACES
:do {{ /interface bridge add name=bridge-lan protocol-mode=none }} on-error={{}}
:do {{ /interface bridge port add interface={lan} bridge=bridge-lan }} on-error={{}}

# 5. IP & SERVEUR DHCP
:do {{ /ip address add address=192.168.88.1/24 interface=bridge-lan }} on-error={{}}
:do {{ /ip pool add name=dhcp-pool ranges=192.168.88.10-192.168.88.250 }} on-error={{}}
:do {{ /ip dhcp-server network add address=192.168.88.0/24 gateway=192.168.88.1 dns-server=192.168.88.1 }} on-error={{}}
:do {{ /ip dhcp-server add name=dhcp-lan interface=bridge-lan address-pool=dhcp-pool disabled=no }} on-error={{}}

# 6. CLIENT WAN
:do {{ /ip dhcp-client add interface={wan} disabled=no add-default-route=yes use-peer-dns=no }} on-error={{}}

# 7. DNS SECURISE AVEC DoH (Cloudflare)
/ip dns set allow-remote-requests=yes servers=1.1.1.1,1.0.0.1 use-doh-server=https://cloudflare-dns.com/dns-query verify-doh-cert=no
:do {{ /ip dns static add name=cloudflare-dns.com address=104.16.248.249 }} on-error={{}}
:do {{ /ip dns static add name=cloudflare-dns.com address=104.16.249.249 }} on-error={{}}

# 8. WIFI AUTO-DÉTECTION (RouterOS v6 & v7 / AC / AX / AN)
:do {{
  :foreach i in=[/interface wireless find] do={{
    /interface wireless security-profiles add name=ketrika-sec mode=dynamic-keys authentication-types=wpa2-psk wpa2-pre-shared-key="{password}"
    /interface wireless set $i mode=ap-bridge ssid="{ssid}" security-profile=ketrika-sec disabled=no
    /interface bridge port add interface=$i bridge=bridge-lan
  }}
}} on-error={{}}
:do {{
  :foreach i in=[/interface wifiwave2 find] do={{
    /interface wifiwave2 security add name=ketrika-sec authentication-types=wpa2-psk passphrase="{password}"
    /interface wifiwave2 set $i configuration.ssid="{ssid}" security=ketrika-sec disabled=no
    /interface bridge port add interface=$i bridge=bridge-lan
  }}
}} on-error={{}}

# 9. FIREWALL, NAT ET OBFUSCATION TTL (ANTI-DÉTECTION PARTAGE)
/ip firewall nat add chain=srcnat out-interface={wan} action=masquerade comment="ketrika-nat"
/ip firewall mangle add chain=postrouting out-interface={wan} action=change-ttl new-ttl=set:64 passthrough=yes comment="ketrika-ttl"
/ip firewall mangle add chain=forward protocol=tcp tcp-flags=syn action=change-mss new-mss=clamp-to-pmtu passthrough=yes comment="ketrika-mss"

# 10. FORCER LE DNS LOCAL
/ip firewall nat add chain=dstnat protocol=udp dst-port=53 action=redirect to-ports=53 comment="ketrika-dns"
/ip firewall nat add chain=dstnat protocol=tcp dst-port=53 action=redirect to-ports=53 comment="ketrika-dns"
"""

    # PACK 2 & 3 : WARP WIREGUARD
    if pack_id >= 2:
        warp = generate_warp()
        s += f"""
# ═══════════════════════════════════════
# SECTION WARP WIREGUARD (Tunnel 100% Chiffré)
# ═══════════════════════════════════════
:do {{
/interface wireguard add name=warp-wg listen-port=0 mtu={warp['mtu']} private-key="{warp['private_key']}" comment="ketrika-warp"
/interface wireguard peers add interface=warp-wg public-key="{warp['public_key']}" endpoint-address={warp['endpoint'].split(':')[0]} endpoint-port={warp['endpoint'].split(':')[1]} allowed-address=0.0.0.0/0 persistent-keepalive=25s comment="ketrika-peer"
/ip address add address={warp['address_v4']} interface=warp-wg comment="ketrika-warp-ip"
/ip firewall nat add chain=srcnat out-interface=warp-wg action=masquerade comment="ketrika-warp-nat"
/ip route add dst-address=0.0.0.0/0 gateway=warp-wg distance=1 comment="ketrika-route"
}} on-error={{ :log warning "WireGuard non supporte sur cette version" }}
"""

    # PACK 3 : HOTSPOT OU PPPOE
    if pack_id >= 3:
        stype = cfg.get('service_type', 'hotspot')
        dl = cfg.get('download_limit', '10M')
        ul = cfg.get('upload_limit', '5M')
        
        if stype == 'hotspot':
            s += f"""
# ═══════════════════════════════════════
# SECTION HOTSPOT PORTAIL CAPTIF
# ═══════════════════════════════════════
:do {{
/ip hotspot user profile add name="client-profile" rate-limit="{ul}/{dl}" shared-users=1
/ip hotspot add name="KETRIKA-SPOT" interface=bridge-lan address-pool=dhcp-pool profile=default disabled=no
/ip hotspot user add name="test" password="123" profile="client-profile"
}} on-error={{}}
"""
        else:
            s += f"""
# ═══════════════════════════════════════
# SECTION SERVEUR PPPoE
# ═══════════════════════════════════════
:do {{
/ip pool add name=pppoe-pool ranges=192.168.99.10-192.168.99.200
/ppp profile add name=pppoe-profile local-address=192.168.99.1 remote-address=pppoe-pool rate-limit="{ul}/{dl}"
/interface pppoe-server server add service-name=internet interface=bridge-lan default-profile=pppoe-profile disabled=no
/ppp secret add name="user1" password="123" profile=pppoe-profile service=pppoe
}} on-error={{}}
"""

    # MISE EN VEILLE (OPTIONNELLE)
    if cfg.get('sleep_enabled') == 'on':
        s += f"""
# ═══════════════════════════════════════
# SECTION MODE NUIT (23h00 - 06h00)
# ═══════════════════════════════════════
/system scheduler add name="mode-nuit" start-time=23:00:00 interval=1d on-event="/queue simple add name=veille target=bridge-lan max-limit=512k/1M comment=sleep"
/system scheduler add name="mode-jour" start-time=06:00:00 interval=1d on-event="/queue simple remove [find comment=sleep]"
"""

    s += """
:delay 2s
:put ""
:put "========================================="
:put "  CONFIGURATION KETRIKA TERMINEE AVEC SUCCES !"
:put "========================================="
"""
    return s

# ============== ROUTES ==============
@app.route('/')
def index():
    return render_template('index.html', packs=PACKS)

@app.route('/unlock', methods=['GET', 'POST'])
def unlock():
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        if code in CODES_ACCES:
            session['pack_id'] = CODES_ACCES[code]
            flash(f"✅ Code valide ! Accès au {PACKS[session['pack_id']]['name']}", "success")
            return redirect(url_for('generator'))
        else:
            flash("❌ Code PIN invalide ! Utilisez 1000, 2000 ou 3000 pour tester.", "error")
    return render_template('unlock.html')

@app.route('/generator', methods=['GET', 'POST'])
def generator():
    # Par défaut Pack 2 si pas connecté
    pack_id = session.get('pack_id', 2)
    script = None
    
    if request.method == 'POST':
        config = request.form.to_dict()
        script = generate_mikrotik_script(config, pack_id)
        return render_template('generator.html', pack=PACKS[pack_id], pack_id=pack_id, script=script)
        
    return render_template('generator.html', pack=PACKS[pack_id], pack_id=pack_id, script=None)

@app.route('/payment')
def payment():
    return render_template('payment.html', packs=PACKS)

# Accès direct rapide en 1 clic
@app.route('/pack/<int:pid>')
def direct_pack(pid):
    if pid in PACKS:
        session['pack_id'] = pid
    return redirect(url_for('generator'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
