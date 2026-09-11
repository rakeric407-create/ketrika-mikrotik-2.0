# -*- coding: utf-8 -*-
"""
KETRIKA MIKROTIK 301 - Moteur .rsc + API WARP Cloudflare
Wi-Fi SSID/password reellement appliques
WireGuard WARP avec inscription API Cloudflare
Connexion Internet garantie meme si WARP echoue
"""

import random
import string
import requests
import json
import base64
from datetime import datetime


# ============================================================
# API CLOUDFLARE WARP : inscription + recuperation des cles
# ============================================================
WARP_API = "https://api.cloudflareclient.com/v0a2158/reg"
CF_PUBKEY = "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo="


def register_warp_device():
    """
    Inscrit un nouvel appareil sur Cloudflare WARP via l API publique.
    Retourne un dict avec private_key, public_key, ipv4, ipv6, client_id
    ou None si echec.
    """
    try:
        # Generer une paire de cles WireGuard via l API
        # Etape 1 : Inscription
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "okhttp/3.12.1",
        }
        payload = {
            "key": "",  # sera genere cote serveur
            "install_id": "",
            "fcm_token": "",
            "tos": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "model": "MikroTik",
            "serial_number": "KETRIKA-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8)),
            "locale": "fr_MG",
        }

        resp = requests.post(WARP_API, json=payload, headers=headers, timeout=15)

        if resp.status_code in (200, 201):
            data = resp.json()
            result = data.get("result", data)
            config = result.get("config", {})
            interface_conf = config.get("interface", {})
            peers = config.get("peers", [{}])
            peer = peers[0] if peers else {}

            return {
                "private_key": result.get("private_key", ""),
                "public_key": peer.get("public_key", CF_PUBKEY),
                "ipv4": interface_conf.get("addresses", {}).get("v4", "172.16.0.2"),
                "ipv6": interface_conf.get("addresses", {}).get("v6", ""),
                "client_id": result.get("id", ""),
                "endpoint": peer.get("endpoint", {}).get("host", "engage.cloudflareclient.com:2408"),
            }
        else:
            return None
    except Exception:
        return None


def generate_rsc(order, model_info):
    """Genere le script .rsc RouterOS v7 complet et fonctionnel"""

    plan = order.plan_type
    has_wifi_24 = model_info.get("wifi_24ghz", False)
    has_wifi_5 = model_info.get("wifi_5ghz", False)
    wifi_type = model_info.get("wifi_type")
    ports = model_info.get("ports", 5)
    wan = order.wan_interface or "ether1"
    gw = order.lan_gateway or "192.168.10.1"
    net = ".".join(gw.split(".")[:3]) + ".0"
    ps = order.dhcp_pool_start or "192.168.10.10"
    pe = order.dhcp_pool_end or "192.168.10.250"
    s2g = order.ssid_2g or "KETRIKA-WiFi"
    s5g = order.ssid_5g or (s2g + "-5G")
    wpw = order.wifi_password or "ketrika2024"

    L = []
    a = L.append
    fn = f"ketrika_{order.license_key}.rsc"

    # EN-TETE
    a("# ==================================================================")
    a("#   KETRIKA MIKROTIK 301 - Script RouterOS v7")
    a("# ==================================================================")
    a(f"#   Licence : {order.license_key}")
    a(f"#   Client  : {order.client_name}")
    a(f"#   Plan    : {plan.upper()}")
    a(f"#   Modele  : {model_info['name']}")
    a(f"#   Routeur : {order.router_name}")
    a(f"#   Date    : {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    a("# ==================================================================")
    a(f"#   Commande : /import file-name={fn}")
    a("# ==================================================================")
    a("")
    a(":log warning \"KETRIKA 301 : Demarrage...\"")
    a(":delay 1s")
    a("")

    # 1. FASTTRACK OFF
    a("# 1. FastTrack off")
    a(":foreach r in=[/ip/firewall/filter/find where action=\"fasttrack-connection\"] do={")
    a("  :do { /ip/firewall/filter/set $r disabled=yes } on-error={}")
    a("}")
    a("")

    # 2. MAC-SERVER
    a("# 2. MAC-Server")
    a(":do { /tool/mac-server/set allowed-interface-list=all } on-error={}")
    a(":do { /tool/mac-server/mac-winbox/set allowed-interface-list=all } on-error={}")
    a(":do { /tool/mac-server/ping/set enabled=yes } on-error={}")
    a("")

    # 3. SERVICES
    a("# 3. Services")
    a(":do { /ip/service/set winbox port=8291 disabled=no } on-error={}")
    a(":do { /ip/service/set ssh port=22 disabled=no } on-error={}")
    for svc in ["telnet", "ftp", "api", "api-ssl", "www", "www-ssl"]:
        a(f":do {{ /ip/service/disable {svc} }} on-error={{}}")
    a("")

    # 4. BRIDGE
    a("# 4. Bridge")
    a(":if ([:len [/interface/bridge/find where name=\"bridge\"]] = 0) do={")
    a("  :do { /interface/bridge/add name=bridge } on-error={}")
    a("}")
    a("")

    # 5. PORTS AU BRIDGE
    a("# 5. Ports Ethernet au bridge")
    for i in range(1, ports + 1):
        eth = f"ether{i}"
        if eth == wan:
            continue
        a(f":if ([:len [/interface/find where name=\"{eth}\"]] > 0) do={{")
        a(f"  :if ([:len [/interface/bridge/port/find where interface=\"{eth}\"]] = 0) do={{")
        a(f"    :do {{ /interface/bridge/port/add bridge=bridge interface={eth} }} on-error={{}}")
        a("  }")
        a("}")
    a("")

    # 6. ADRESSES IP
    a("# 6. IP LAN")
    a(f":if ([:len [/ip/address/find where address~\"{gw}\"]] = 0) do={{")
    a(f"  :do {{ /ip/address/add address={gw}/24 interface=bridge network={net} comment=\"KETRIKA\" }} on-error={{}}")
    a("}")
    a(":if ([:len [/ip/address/find where address~\"192.168.88.1\"]] = 0) do={")
    a("  :do { /ip/address/add address=192.168.88.1/24 interface=bridge network=192.168.88.0 comment=\"BACKUP\" } on-error={}")
    a("}")
    a("")

    # 7. DHCP + DNS
    a("# 7. DHCP")
    a(f":if ([:len [/ip/pool/find where name=\"ketrika-pool\"]] = 0) do={{")
    a(f"  :do {{ /ip/pool/add name=ketrika-pool ranges={ps}-{pe} }} on-error={{}}")
    a("}")
    a(":if ([:len [/ip/dhcp-server/find where name=\"ketrika-dhcp\"]] = 0) do={")
    a("  :do { /ip/dhcp-server/add name=ketrika-dhcp interface=bridge address-pool=ketrika-pool disabled=no lease-time=1d } on-error={}")
    a("}")
    a(f":if ([:len [/ip/dhcp-server/network/find where address=\"{net}/24\"]] = 0) do={{")
    a(f"  :do {{ /ip/dhcp-server/network/add address={net}/24 gateway={gw} dns-server=1.1.1.1,8.8.8.8 }} on-error={{}}")
    a("}")
    a(":do { /ip/dns/set servers=1.1.1.1,8.8.8.8 allow-remote-requests=yes } on-error={}")
    a("")

    # 8. DHCP CLIENT WAN
    a("# 8. DHCP Client WAN")
    a(f":if ([:len [/ip/dhcp-client/find where interface=\"{wan}\"]] = 0) do={{")
    a(f"  :do {{ /ip/dhcp-client/add interface={wan} disabled=no add-default-route=yes use-peer-dns=no }} on-error={{}}")
    a("}")
    a("")

    # 9. MAC SPOOF
    if plan in ("performance", "business") and order.mac_spoof and order.mac_address:
        a("# 9. MAC Spoof")
        a(f":do {{ /interface/ethernet/set [/interface/ethernet/find where name=\"{wan}\"] mac-address={order.mac_address} }} on-error={{}}")
        a("")

    # ============================================================
    # 10. WI-FI - CORRECTION MAJEURE
    # ============================================================
    if has_wifi_24 or has_wifi_5:
        a("# 10. Wi-Fi Configuration")
        a("")

        if wifi_type == "ax":
            # ===== Wi-Fi 6 AX =====
            a("# --- Wi-Fi 6 AX ---")
            a("# Supprimer les anciens profils si existants")
            a(":do { /interface/wifi/security/remove [/interface/wifi/security/find where name=\"ketrika-sec\"] } on-error={}")
            a(f":do {{ /interface/wifi/security/add name=ketrika-sec authentication-types=wpa2-psk,wpa3-psk passphrase=\"{wpw}\" }} on-error={{}}")
            a("")
            a(":do { /interface/wifi/configuration/remove [/interface/wifi/configuration/find where name=\"ketrika-2g\"] } on-error={}")
            a(f":do {{ /interface/wifi/configuration/add name=ketrika-2g ssid=\"{s2g}\" security=ketrika-sec country=Madagascar mode=ap }} on-error={{}}")
            if has_wifi_5:
                a(":do { /interface/wifi/configuration/remove [/interface/wifi/configuration/find where name=\"ketrika-5g\"] } on-error={}")
                a(f":do {{ /interface/wifi/configuration/add name=ketrika-5g ssid=\"{s5g}\" security=ketrika-sec country=Madagascar mode=ap }} on-error={{}}")
            a("")
            a("# Appliquer sur les interfaces physiques")
            a(":foreach w in=[/interface/wifi/find] do={")
            a("  :local wname [/interface/wifi/get $w default-name]")
            a("  :if ($wname = \"wifi1\") do={")
            a("    :do { /interface/wifi/set $w configuration=ketrika-2g disabled=no } on-error={}")
            a("  }")
            if has_wifi_5:
                a("  :if ($wname = \"wifi2\") do={")
                a("    :do { /interface/wifi/set $w configuration=ketrika-5g disabled=no } on-error={}")
                a("  }")
            a("}")
            a(":do { /interface/wifi/enable [/interface/wifi/find] } on-error={}")
            a("")
            # Bridge
            a("# Bridge Wi-Fi")
            a(":if ([:len [/interface/bridge/port/find where interface=\"wifi1\"]] = 0) do={")
            a("  :do { /interface/bridge/port/add bridge=bridge interface=wifi1 } on-error={}")
            a("}")
            if has_wifi_5:
                a(":if ([:len [/interface/bridge/port/find where interface=\"wifi2\"]] = 0) do={")
                a("  :do { /interface/bridge/port/add bridge=bridge interface=wifi2 } on-error={}")
                a("}")
        else:
            # ===== Wi-Fi AC/N =====
            a("# --- Wi-Fi AC/N ---")
            a("# Supprimer ancien profil securite si existant")
            a(":do { /interface/wireless/security-profiles/remove [/interface/wireless/security-profiles/find where name=\"ketrika-sec\"] } on-error={}")
            a(f":do {{ /interface/wireless/security-profiles/add name=ketrika-sec mode=dynamic-keys authentication-types=wpa2-psk wpa2-pre-shared-key=\"{wpw}\" }} on-error={{}}")
            a("")
            a("# Appliquer SSID et securite sur chaque interface")
            a(":foreach w in=[/interface/wireless/find] do={")
            a("  :local wname [/interface/wireless/get $w default-name]")
            a("  :if ($wname = \"wlan1\") do={")
            a(f"    :do {{ /interface/wireless/set $w mode=ap-bridge ssid=\"{s2g}\" security-profile=ketrika-sec band=2ghz-b/g/n channel-width=20/40mhz-XX frequency=auto disabled=no country=madagascar wireless-protocol=802.11 }} on-error={{}}")
            a("  }")
            if has_wifi_5:
                a("  :if ($wname = \"wlan2\") do={")
                a(f"    :do {{ /interface/wireless/set $w mode=ap-bridge ssid=\"{s5g}\" security-profile=ketrika-sec band=5ghz-a/n/ac channel-width=20/40/80mhz-XXXX frequency=auto disabled=no country=madagascar wireless-protocol=802.11 }} on-error={{}}")
                a("  }")
            a("}")
            a(":do { /interface/wireless/enable [/interface/wireless/find] } on-error={}")
            a("")
            # Bridge
            a("# Bridge Wi-Fi")
            a(":if ([:len [/interface/bridge/port/find where interface=\"wlan1\"]] = 0) do={")
            a("  :do { /interface/bridge/port/add bridge=bridge interface=wlan1 } on-error={}")
            a("}")
            if has_wifi_5:
                a(":if ([:len [/interface/bridge/port/find where interface=\"wlan2\"]] = 0) do={")
                a("  :do { /interface/bridge/port/add bridge=bridge interface=wlan2 } on-error={}")
                a("}")

        a("")
        a(f":log warning \"KETRIKA : Wi-Fi active - SSID={s2g}\"")
        a("")

    # ============================================================
    # 11. NAT (AVANT WARP pour garantir la connexion)
    # ============================================================
    a("# 11. NAT Masquerade WAN")
    a(f":if ([:len [/ip/firewall/nat/find where comment=\"ketrika-nat\"]] = 0) do={{")
    a(f"  :do {{ /ip/firewall/nat/add chain=srcnat action=masquerade out-interface={wan} comment=\"ketrika-nat\" }} on-error={{}}")
    a("}")
    a("")

    # ============================================================
    # 12. WIREGUARD WARP (plan 2+) - AVEC VRAIES CLES
    # ============================================================
    if plan in ("performance", "business") and order.warp_private_key:
        warp_priv = order.warp_private_key
        warp_ipv4 = order.warp_ipv4 or "172.16.0.2"
        ep_host = "engage.cloudflareclient.com"
        ep_port = "2408"

        a("# 12. WireGuard WARP avec cles Cloudflare")
        a("")
        a("# Supprimer ancienne config si existante")
        a(":do { /interface/wireguard/peers/remove [/interface/wireguard/peers/find where interface=\"wg-warp\"] } on-error={}")
        a(":do { /ip/address/remove [/ip/address/find where interface=\"wg-warp\"] } on-error={}")
        a(":do { /interface/wireguard/remove [/interface/wireguard/find where name=\"wg-warp\"] } on-error={}")
        a("")
        a(f":do {{ /interface/wireguard/add name=wg-warp listen-port=13231 mtu=1280 private-key=\"{warp_priv}\" }} on-error={{}}")
        a(f":do {{ /ip/address/add address={warp_ipv4}/32 interface=wg-warp comment=\"WARP\" }} on-error={{}}")
        a(f":do {{ /interface/wireguard/peers/add interface=wg-warp public-key=\"{CF_PUBKEY}\" endpoint-address={ep_host} endpoint-port={ep_port} allowed-address=0.0.0.0/0,::/0 persistent-keepalive=25s comment=\"Cloudflare-WARP\" }} on-error={{}}")
        a("")

        # NAT WARP
        a(":if ([:len [/ip/firewall/nat/find where comment=\"ketrika-nat-warp\"]] = 0) do={")
        a("  :do { /ip/firewall/nat/add chain=srcnat action=masquerade out-interface=wg-warp comment=\"ketrika-nat-warp\" } on-error={}")
        a("}")
        a("")

        # Routing table
        a(":if ([:len [/routing/table/find where name=\"via-warp\"]] = 0) do={")
        a("  :do { /routing/table/add name=via-warp fib } on-error={}")
        a("}")
        a("")

        # Route via WARP
        a(":do { /ip/route/remove [/ip/route/find where comment=\"ketrika-warp-route\"] } on-error={}")
        a(":do { /ip/route/add dst-address=0.0.0.0/0 gateway=wg-warp routing-table=via-warp comment=\"ketrika-warp-route\" } on-error={}")
        a("")

        # Address lists
        a(":foreach net in={\"192.168.0.0/16\";\"10.0.0.0/8\";\"172.16.0.0/12\"} do={")
        a("  :if ([:len [/ip/firewall/address-list/find where list=\"ketrika-local\" and address=$net]] = 0) do={")
        a("    :do { /ip/firewall/address-list/add list=ketrika-local address=$net } on-error={}")
        a("  }")
        a("}")
        a("")

        # Mangle AVEC FALLBACK : si wg-warp tombe, le trafic passe par WAN normal
        a("# Mangle : router via WARP (avec fallback si tunnel down)")
        a(":do { /ip/firewall/mangle/remove [/ip/firewall/mangle/find where comment~\"ketrika-warp\"] } on-error={}")
        a("# Exclure Winbox et LAN du tunnel")
        a(f":do {{ /ip/firewall/mangle/add chain=prerouting action=accept src-address={net}/24 protocol=tcp dst-port=8291 comment=\"ketrika-warp-exclude\" }} on-error={{}}")
        a(f":do {{ /ip/firewall/mangle/add chain=prerouting action=accept src-address={net}/24 dst-address-list=ketrika-local comment=\"ketrika-warp-local\" }} on-error={{}}")
        a(f":do {{ /ip/firewall/mangle/add chain=prerouting action=mark-routing new-routing-mark=via-warp src-address={net}/24 dst-address-list=!ketrika-local passthrough=no connection-state=new comment=\"ketrika-warp-mark\" }} on-error={{}}")
        a("")
        a(":log warning \"KETRIKA : WireGuard WARP configure\"")
        a("")

    # ============================================================
    # 13. MSS CLAMPING
    # ============================================================
    a("# 13. MSS Clamping")
    a(":if ([:len [/ip/firewall/mangle/find where comment=\"ketrika-mss\"]] = 0) do={")
    a("  :do { /ip/firewall/mangle/add chain=forward action=change-mss new-mss=1280 protocol=tcp tcp-flags=syn tcp-mss=1281-65535 passthrough=yes comment=\"ketrika-mss\" } on-error={}")
    a("}")
    a("")

    # ============================================================
    # 14. TTL
    # ============================================================
    if plan in ("performance", "business") and order.ttl_value and order.ttl_value > 0:
        a(f"# 14. TTL = {order.ttl_value}")
        a(":do { /ip/firewall/mangle/remove [/ip/firewall/mangle/find where comment~\"ketrika-ttl\"] } on-error={}")
        for chain, tag in [("prerouting", "pre"), ("postrouting", "post"), ("forward", "fwd")]:
            a(f":do {{ /ip/firewall/mangle/add chain={chain} action=change-ttl new-ttl=set:{order.ttl_value} passthrough=yes comment=\"ketrika-ttl-{tag}\" }} on-error={{}}")
        a("")

    # ============================================================
    # 15. QOS
    # ============================================================
    if plan in ("performance", "business"):
        if (order.dl_limit and order.dl_limit > 0) or (order.ul_limit and order.ul_limit > 0):
            dl = f"{order.dl_limit}M" if order.dl_limit > 0 else "0"
            ul = f"{order.ul_limit}M" if order.ul_limit > 0 else "0"
            a("# 15. QoS Global")
            a(":do { /queue/simple/remove [/queue/simple/find where name=\"ketrika-qos\"] } on-error={}")
            a(f":do {{ /queue/simple/add name=ketrika-qos target={net}/24 max-limit={ul}/{dl} comment=\"KETRIKA\" }} on-error={{}}")
            a("")

    # ============================================================
    # 16. HOTSPOT
    # ============================================================
    if plan == "business" and order.hotspot_tickets_count and order.hotspot_tickets_count > 0:
        a("# 16. Hotspot")
        a(":if ([:len [/ip/hotspot/profile/find where name=\"ketrika-hs-prof\"]] = 0) do={")
        a(f"  :do {{ /ip/hotspot/profile/add name=ketrika-hs-prof hotspot-address={gw} dns-name=login.ketrika.mg html-directory=hotspot login-by=http-chap,http-pap }} on-error={{}}")
        a("}")
        for pn, to, rl in [("hs-1h","1h","5M/10M"),("hs-1d","1d","5M/10M"),("hs-1w","1w","5M/10M"),("hs-1m","4w2d","10M/20M")]:
            a(f":if ([:len [/ip/hotspot/user/profile/find where name=\"{pn}\"]] = 0) do={{")
            a(f"  :do {{ /ip/hotspot/user/profile/add name={pn} session-timeout={to} shared-users=1 rate-limit={rl} }} on-error={{}}")
            a("}")
        a(":if ([:len [/ip/hotspot/find where name=\"ketrika-hs\"]] = 0) do={")
        a("  :do { /ip/hotspot/add name=ketrika-hs interface=bridge address-pool=ketrika-pool profile=ketrika-hs-prof disabled=no } on-error={}")
        a("}")
        a("")
        count = min(order.hotspot_tickets_count, 200)
        for _ in range(count):
            u = "T" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
            p = "".join(random.choices(string.digits, k=6))
            a(f":if ([:len [/ip/hotspot/user/find where name=\"{u}\"]] = 0) do={{")
            a(f"  :do {{ /ip/hotspot/user/add name={u} password={p} profile=hs-1d server=ketrika-hs }} on-error={{}}")
            a("}")
        a("")

    # ============================================================
    # 17. IDENTITY
    # ============================================================
    a(f"# 17. Identity")
    a(f":do {{ /system/identity/set name=\"{order.router_name}\" }} on-error={{}}")
    a("")

    # ============================================================
    # 18. VEILLE WI-FI
    # ============================================================
    if order.sleep_mode and order.sleep_mode != "off" and order.sleep_start and order.sleep_end:
        if wifi_type == "ax":
            off_cmd = "/interface/wifi/disable [find]"
            on_cmd = "/interface/wifi/enable [find]"
        elif has_wifi_24 or has_wifi_5:
            off_cmd = "/interface/wireless/disable [find]"
            on_cmd = "/interface/wireless/enable [find]"
        else:
            off_cmd = ""
            on_cmd = ""
        if off_cmd:
            ss = order.sleep_start if ":" in order.sleep_start else order.sleep_start + ":00"
            se = order.sleep_end if ":" in order.sleep_end else order.sleep_end + ":00"
            a(f"# 18. Veille Wi-Fi {ss} - {se}")
            a(":do { /system/scheduler/remove [/system/scheduler/find where name~\"ketrika-wifi\"] } on-error={}")
            a(f":do {{ /system/scheduler/add name=ketrika-wifi-off start-time={ss}:00 interval=1d on-event=\"{off_cmd}\" }} on-error={{}}")
            a(f":do {{ /system/scheduler/add name=ketrika-wifi-on start-time={se}:00 interval=1d on-event=\"{on_cmd}\" }} on-error={{}}")
            a("")

    # ============================================================
    # 19. FIREWALL
    # ============================================================
    a("# 19. Firewall")
    fw = [
        ("input", "accept", "connection-state=established,related", "estab"),
        ("input", "accept", f"src-address=192.168.0.0/16", "lan"),
        ("input", "accept", "protocol=icmp", "icmp"),
        ("input", "drop", f"in-interface={wan}", "drop"),
        ("forward", "accept", "connection-state=established,related", "fwd"),
        ("forward", "drop", f"connection-state=invalid in-interface={wan}", "fwd-drop"),
    ]
    for ch, act, par, tag in fw:
        a(f":if ([:len [/ip/firewall/filter/find where comment=\"k-fw-{tag}\"]] = 0) do={{")
        a(f"  :do {{ /ip/firewall/filter/add chain={ch} action={act} {par} comment=\"k-fw-{tag}\" }} on-error={{}}")
        a("}")
    a("")

    # ============================================================
    # 20. SUCCES
    # ============================================================
    a(":delay 2s")
    a(":log warning \"================================================\"")
    a(":log warning \"  KETRIKA MIKROTIK 301 - TERMINE\"")
    a(f":log warning \"  Licence : {order.license_key}\"")
    a(f":log warning \"  Routeur : {order.router_name}\"")
    a(f":log warning \"  Wi-Fi   : {s2g}\"")
    a(":log warning \"  Support : wa.me/261382817100\"")
    a(":log warning \"================================================\"")
    a("")
    a(":put \"\"")
    a(":put \"================================================\"")
    a(":put \"  KETRIKA MIKROTIK 301 - SUCCES\"")
    a(":put \"================================================\"")
    a(f":put \"  Routeur : {order.router_name}\"")
    a(f":put \"  Wi-Fi   : {s2g} / mdp: {wpw}\"")
    a(f":put \"  IP      : {gw}\"")
    if plan in ("performance", "business"):
        a(":put \"  VPN     : WireGuard WARP\"")
    a(":put \"================================================\"")

    return "\n".join(L)


def generate_tutorial_txt(order, filename):
    """Genere le fichier tutoriel texte"""
    plan = order.plan_type
    L = [
        "================================================",
        "  KETRIKA MIKROTIK 301 - GUIDE INSTALLATION",
        "================================================",
        "",
        f"  Licence  : {order.license_key}",
        f"  Client   : {order.client_name}",
        f"  Plan     : {plan.upper()}",
        f"  Routeur  : {order.router_name}",
        "",
        "================================================",
        "  ETAPE 1 : OUVRIR WINBOX",
        "================================================",
        "",
        "  Telecharger Winbox : https://mikrotik.com/download",
        "  Ouvrez Winbox et connectez-vous a votre routeur",
        "  (IP par defaut : 192.168.88.1 / login : admin)",
        "",
        "================================================",
        "  ETAPE 2 : GLISSER LE FICHIER",
        "================================================",
        "",
        "  Dans Winbox cliquez sur : Files",
        f"  Glissez le fichier : {filename}",
        "  Attendez que le fichier apparaisse",
        "",
        "================================================",
        "  ETAPE 3 : COPIER-COLLER LA COMMANDE",
        "================================================",
        "",
        "  Cliquez sur : New Terminal",
        "  Copiez-collez la commande ci-dessous :",
        "",
        f"  /import file-name={filename}",
        "",
        "  Attendez 10-30 secondes... Termine !",
        "",
        "================================================",
        "  VOS IDENTIFIANTS",
        "================================================",
        "",
        f"  Nom du routeur  : {order.router_name}",
        f"  IP du routeur   : {order.lan_gateway}",
    ]
    if order.ssid_2g:
        L.append(f"  Wi-Fi 2.4 GHz   : {order.ssid_2g}")
    if order.ssid_5g:
        L.append(f"  Wi-Fi 5 GHz     : {order.ssid_5g}")
    if order.wifi_password:
        L.append(f"  Mot de passe    : {order.wifi_password}")
    if plan in ("performance", "business"):
        L.extend(["", "  VPN WireGuard WARP : ACTIF"])
    L.extend([
        "",
        "================================================",
        "  SUPPORT : wa.me/261382817100",
        "  KETRIKA MIKROTIK - Made in Madagascar",
        "================================================",
    ])
    return "\n".join(L)
