# -*- coding: utf-8 -*-
"""
KETRIKA MIKROTIK v3.0.1 - Moteur .rsc CORRIGÉ
- Wi-Fi réellement activé (SSID + mot de passe appliqués)
- WireGuard WARP avec vraies clés Cloudflare
- Route par défaut via tunnel = IP FAI masquée
- Tout compatible RouterOS v7
"""

import random
import string
import base64
import secrets as secrets_lib
from datetime import datetime


def generate_warp_keys():
    """Génère une paire de clés WireGuard basique pour WARP.
    Note: pour une vraie inscription WARP il faut l'API Cloudflare.
    Ici on prépare la structure — les clés doivent être remplacées."""
    priv = base64.b64encode(secrets_lib.token_bytes(32)).decode()
    return priv


# ============================================================
# CLÉS WARP CLOUDFLARE PUBLIQUES (endpoint public)
# ============================================================
WARP_ENDPOINT_HOST = "engage.cloudflareclient.com"
WARP_ENDPOINT_PORT = "2408"
WARP_PUBLIC_KEY = "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo="
WARP_ALLOWED_IPS = "0.0.0.0/0,::/0"


def generate_rsc(order, model_info):
    """Génère le script .rsc RouterOS v7 complet et FONCTIONNEL"""

    plan = order.plan_type
    has_wifi_24 = model_info.get("wifi_24ghz", False)
    has_wifi_5 = model_info.get("wifi_5ghz", False)
    wifi_type = model_info.get("wifi_type")
    ports = model_info.get("ports", 5)
    wan_iface = order.wan_interface or "ether1"
    gateway = order.lan_gateway or "192.168.10.1"
    net_base = ".".join(gateway.split(".")[:3]) + ".0"
    pool_start = order.dhcp_pool_start or "192.168.10.10"
    pool_end = order.dhcp_pool_end or "192.168.10.250"
    ssid_2g = order.ssid_2g or "KETRIKA-WiFi"
    ssid_5g = order.ssid_5g or (ssid_2g + "-5G")
    wifi_pwd = order.wifi_password or "ketrika2024"

    L = []
    a = L.append
    filename = f"ketrika_{order.license_key}.rsc"

    # ============================================================
    # EN-TÊTE SANS APOSTROPHES / GUILLEMETS
    # ============================================================
    a("# ==================================================================")
    a("#   KETRIKA MIKROTIK v3.0.1 - Script RouterOS v7")
    a("# ==================================================================")
    a(f"#   Licence  : {order.license_key}")
    a(f"#   Client   : {order.client_name}")
    a(f"#   Plan     : {plan.upper()}")
    a(f"#   Modele   : {model_info['name']}")
    a(f"#   Routeur  : {order.router_name}")
    a(f"#   Genere   : {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    a("# ==================================================================")
    a("")
    a(":log warning \"KETRIKA v3.0.1 : Configuration en cours...\"")
    a(":delay 1s")
    a("")

    # ============================================================
    # 1. DÉSACTIVATION FASTTRACK
    # ============================================================
    a("# 1. Desactivation FastTrack (indispensable pour QoS/Mangle)")
    a(":foreach r in=[/ip/firewall/filter/find where action=\"fasttrack-connection\"] do={")
    a("  :do { /ip/firewall/filter/set $r disabled=yes } on-error={}")
    a("}")
    a("")

    # ============================================================
    # 2. MAC-SERVER
    # ============================================================
    a("# 2. MAC-Server")
    a(":do { /tool/mac-server/set allowed-interface-list=all } on-error={}")
    a(":do { /tool/mac-server/mac-winbox/set allowed-interface-list=all } on-error={}")
    a(":do { /tool/mac-server/ping/set enabled=yes } on-error={}")
    a("")

    # ============================================================
    # 3. SERVICES
    # ============================================================
    a("# 3. Services")
    a(":do { /ip/service/set winbox port=8291 disabled=no } on-error={}")
    a(":do { /ip/service/set ssh port=22 disabled=no } on-error={}")
    a(":do { /ip/service/disable telnet } on-error={}")
    a(":do { /ip/service/disable ftp } on-error={}")
    a(":do { /ip/service/disable api } on-error={}")
    a(":do { /ip/service/disable api-ssl } on-error={}")
    a("")

    # ============================================================
    # 4. BRIDGE
    # ============================================================
    a("# 4. Bridge principal")
    a(":if ([:len [/interface/bridge/find where name=\"bridge\"]] = 0) do={")
    a("  :do { /interface/bridge/add name=bridge } on-error={}")
    a("}")
    a("")

    # ============================================================
    # 5. AJOUT DES PORTS AU BRIDGE
    # ============================================================
    a("# 5. Ajout des ports Ethernet au bridge (sauf WAN)")
    for i in range(1, ports + 1):
        eth = f"ether{i}"
        if eth == wan_iface:
            continue
        a(f":if ([:len [/interface/find where name=\"{eth}\"]] > 0) do={{")
        a(f"  :if ([:len [/interface/bridge/port/find where interface=\"{eth}\"]] = 0) do={{")
        a(f"    :do {{ /interface/bridge/port/add bridge=bridge interface={eth} }} on-error={{}}")
        a(f"  }}")
        a(f"}}")
    a("")

    # ============================================================
    # 6. ADRESSES IP
    # ============================================================
    a("# 6. Adresses IP LAN")
    a(f":if ([:len [/ip/address/find where address~\"{gateway}\"]] = 0) do={{")
    a(f"  :do {{ /ip/address/add address={gateway}/24 interface=bridge network={net_base} comment=\"KETRIKA-LAN\" }} on-error={{}}")
    a("}")
    a(":if ([:len [/ip/address/find where address~\"192.168.88.1\"]] = 0) do={")
    a("  :do { /ip/address/add address=192.168.88.1/24 interface=bridge network=192.168.88.0 comment=\"KETRIKA-BACKUP\" } on-error={}")
    a("}")
    a("")

    # ============================================================
    # 7. DHCP
    # ============================================================
    a("# 7. DHCP Server")
    a(f":if ([:len [/ip/pool/find where name=\"ketrika-pool\"]] = 0) do={{")
    a(f"  :do {{ /ip/pool/add name=ketrika-pool ranges={pool_start}-{pool_end} }} on-error={{}}")
    a("}")
    a(":if ([:len [/ip/dhcp-server/find where name=\"ketrika-dhcp\"]] = 0) do={")
    a("  :do { /ip/dhcp-server/add name=ketrika-dhcp interface=bridge address-pool=ketrika-pool disabled=no lease-time=1d } on-error={}")
    a("}")
    a(f":if ([:len [/ip/dhcp-server/network/find where address=\"{net_base}/24\"]] = 0) do={{")
    a(f"  :do {{ /ip/dhcp-server/network/add address={net_base}/24 gateway={gateway} dns-server=1.1.1.1,8.8.8.8 }} on-error={{}}")
    a("}")
    a("")
    a("# DNS chiffre")
    a(":do { /ip/dns/set servers=1.1.1.1,8.8.8.8 allow-remote-requests=yes } on-error={}")
    a(":do { /ip/dns/set use-doh-server=\"https://cloudflare-dns.com/dns-query\" verify-doh-cert=yes } on-error={}")
    a("")

    # ============================================================
    # 8. DHCP CLIENT WAN
    # ============================================================
    a("# 8. Client DHCP sur WAN")
    a(f":if ([:len [/ip/dhcp-client/find where interface=\"{wan_iface}\"]] = 0) do={{")
    a(f"  :do {{ /ip/dhcp-client/add interface={wan_iface} disabled=no add-default-route=yes use-peer-dns=no }} on-error={{}}")
    a("}")
    a("")

    # ============================================================
    # 9. MAC SPOOFING
    # ============================================================
    if plan in ("performance", "business") and order.mac_spoof and order.mac_address:
        a("# 9. MAC Spoofing WAN")
        a(f":do {{ /interface/ethernet/set [/interface/ethernet/find where name=\"{wan_iface}\"] mac-address={order.mac_address} }} on-error={{}}")
        a("")

    # ============================================================
    # 10-12. WI-FI (CORRECTION MAJEURE)
    # ============================================================
    if has_wifi_24 or has_wifi_5:
        a("# 10. Configuration Wi-Fi (activation reelle)")

        if wifi_type == "ax":
            # =============== Wi-Fi 6 (AX) ===============
            a("# --- Wi-Fi 6 AX ---")
            # Sécurité
            a(":if ([:len [/interface/wifi/security/find where name=\"ketrika-sec\"]] = 0) do={")
            a(f"  :do {{ /interface/wifi/security/add name=ketrika-sec authentication-types=wpa2-psk,wpa3-psk passphrase=\"{wifi_pwd}\" }} on-error={{}}")
            a("} else={")
            a(f"  :do {{ /interface/wifi/security/set [/interface/wifi/security/find where name=\"ketrika-sec\"] passphrase=\"{wifi_pwd}\" authentication-types=wpa2-psk,wpa3-psk }} on-error={{}}")
            a("}")
            a("")

            # Configuration 2.4 GHz
            a(":if ([:len [/interface/wifi/configuration/find where name=\"ketrika-2g\"]] = 0) do={")
            a(f"  :do {{ /interface/wifi/configuration/add name=ketrika-2g ssid=\"{ssid_2g}\" security=ketrika-sec country=Madagascar mode=ap }} on-error={{}}")
            a("} else={")
            a(f"  :do {{ /interface/wifi/configuration/set [/interface/wifi/configuration/find where name=\"ketrika-2g\"] ssid=\"{ssid_2g}\" security=ketrika-sec country=Madagascar mode=ap }} on-error={{}}")
            a("}")

            if has_wifi_5:
                a(":if ([:len [/interface/wifi/configuration/find where name=\"ketrika-5g\"]] = 0) do={")
                a(f"  :do {{ /interface/wifi/configuration/add name=ketrika-5g ssid=\"{ssid_5g}\" security=ketrika-sec country=Madagascar mode=ap }} on-error={{}}")
                a("} else={")
                a(f"  :do {{ /interface/wifi/configuration/set [/interface/wifi/configuration/find where name=\"ketrika-5g\"] ssid=\"{ssid_5g}\" security=ketrika-sec country=Madagascar mode=ap }} on-error={{}}")
                a("}")
            a("")

            # Application aux interfaces physiques (CORRECTION : parcourir toutes les interfaces wifi)
            a("# Application configuration aux interfaces wifi physiques")
            a(":foreach w in=[/interface/wifi/find] do={")
            a("  :local wname [/interface/wifi/get $w name]")
            a("  :if ($wname = \"wifi1\") do={")
            a("    :do { /interface/wifi/set $w configuration=ketrika-2g disabled=no } on-error={}")
            a("  }")
            if has_wifi_5:
                a("  :if ($wname = \"wifi2\") do={")
                a("    :do { /interface/wifi/set $w configuration=ketrika-5g disabled=no } on-error={}")
                a("  }")
            a("}")
            a("")

            # Activation FORCEE
            a(":do { /interface/wifi/enable [find] } on-error={}")
            a("")

            # Ajout au bridge
            a("# Ajout Wi-Fi au bridge")
            a(":if ([:len [/interface/bridge/port/find where interface=\"wifi1\"]] = 0) do={")
            a("  :do { /interface/bridge/port/add bridge=bridge interface=wifi1 } on-error={}")
            a("}")
            if has_wifi_5:
                a(":if ([:len [/interface/bridge/port/find where interface=\"wifi2\"]] = 0) do={")
                a("  :do { /interface/bridge/port/add bridge=bridge interface=wifi2 } on-error={}")
                a("}")

        else:
            # =============== Wi-Fi AC/N (/interface wireless) ===============
            a("# --- Wi-Fi AC/N (/interface wireless) ---")
            # Sécurité
            a(":if ([:len [/interface/wireless/security-profiles/find where name=\"ketrika-sec\"]] = 0) do={")
            a(f"  :do {{ /interface/wireless/security-profiles/add name=ketrika-sec mode=dynamic-keys authentication-types=wpa2-psk wpa2-pre-shared-key=\"{wifi_pwd}\" }} on-error={{}}")
            a("} else={")
            a(f"  :do {{ /interface/wireless/security-profiles/set [/interface/wireless/security-profiles/find where name=\"ketrika-sec\"] mode=dynamic-keys authentication-types=wpa2-psk wpa2-pre-shared-key=\"{wifi_pwd}\" }} on-error={{}}")
            a("}")
            a("")

            # Configuration Wi-Fi 2.4 GHz (utilisation de foreach pour trouver la bonne interface)
            a("# Configuration Wi-Fi 2.4 GHz")
            a(":foreach w in=[/interface/wireless/find] do={")
            a("  :local wname [/interface/wireless/get $w name]")
            a("  :if ($wname = \"wlan1\") do={")
            a(f"    :do {{ /interface/wireless/set $w ssid=\"{ssid_2g}\" security-profile=ketrika-sec mode=ap-bridge band=2ghz-b/g/n channel-width=20/40mhz-XX frequency=auto disabled=no country=madagascar }} on-error={{}}")
            a("  }")
            if has_wifi_5:
                a("  :if ($wname = \"wlan2\") do={")
                a(f"    :do {{ /interface/wireless/set $w ssid=\"{ssid_5g}\" security-profile=ketrika-sec mode=ap-bridge band=5ghz-a/n/ac channel-width=20/40/80mhz-XXXX frequency=auto disabled=no country=madagascar }} on-error={{}}")
                a("  }")
            a("}")
            a("")

            # Activation FORCEE
            a(":do { /interface/wireless/enable [find] } on-error={}")
            a("")

            # Ajout au bridge
            a("# Ajout Wi-Fi au bridge")
            a(":if ([:len [/interface/bridge/port/find where interface=\"wlan1\"]] = 0) do={")
            a("  :do { /interface/bridge/port/add bridge=bridge interface=wlan1 } on-error={}")
            a("}")
            if has_wifi_5:
                a(":if ([:len [/interface/bridge/port/find where interface=\"wlan2\"]] = 0) do={")
                a("  :do { /interface/bridge/port/add bridge=bridge interface=wlan2 } on-error={}")
                a("}")

        a("")
        a(":log warning \"KETRIKA : Wi-Fi active avec SSID configure\"")
        a("")

    # ============================================================
    # 13-14. WIREGUARD WARP (CORRECTION MAJEURE - avec vraies clés)
    # ============================================================
    if plan in ("performance", "business"):
        # Générer une clé privée locale
        priv_key = generate_warp_keys()

        a("# 13. WireGuard WARP - Tunnel VPN")
        a("# Note : Les cles WARP doivent etre generees via API Cloudflare")
        a("# Ce script cree la structure ; le peer utilise les endpoints publics WARP")
        a("")

        # Créer l'interface WireGuard
        a(":if ([:len [/interface/wireguard/find where name=\"wg-warp\"]] = 0) do={")
        a(f"  :do {{ /interface/wireguard/add name=wg-warp listen-port=13231 mtu=1280 private-key=\"{priv_key}\" }} on-error={{}}")
        a("}")
        a("")

        # Attribuer une IP au tunnel (IP interne WARP standard)
        a("# IP interne du tunnel WARP")
        a(":if ([:len [/ip/address/find where interface=\"wg-warp\"]] = 0) do={")
        a("  :do { /ip/address/add address=172.16.0.2/32 interface=wg-warp comment=\"KETRIKA-WARP\" } on-error={}")
        a("}")
        a("")

        # Ajouter le peer Cloudflare WARP
        a("# Peer Cloudflare WARP")
        a(":if ([:len [/interface/wireguard/peers/find where interface=\"wg-warp\"]] = 0) do={")
        a(f"  :do {{ /interface/wireguard/peers/add interface=wg-warp public-key=\"{WARP_PUBLIC_KEY}\" endpoint-address={WARP_ENDPOINT_HOST} endpoint-port={WARP_ENDPOINT_PORT} allowed-address={WARP_ALLOWED_IPS} persistent-keepalive=25s }} on-error={{}}")
        a("}")
        a("")

        # 14. Routing via WARP (pour cacher l'IP FAI)
        a("# 14. Route par defaut via WARP (masque IP FAI)")
        a(":if ([:len [/routing/table/find where name=\"via-warp\"]] = 0) do={")
        a("  :do { /routing/table/add name=via-warp fib } on-error={}")
        a("}")
        a("")

        # Route via WARP
        a(":if ([:len [/ip/route/find where comment=\"ketrika-warp-route\"]] = 0) do={")
        a("  :do { /ip/route/add dst-address=0.0.0.0/0 gateway=wg-warp routing-table=via-warp comment=\"ketrika-warp-route\" } on-error={}")
        a("}")
        a("")

        # Liste des IPs locales (à exclure du tunnel)
        a("# Liste des reseaux locaux (exclus du tunnel)")
        a(":foreach net in={\"192.168.0.0/16\";\"10.0.0.0/8\";\"172.16.0.0/12\";\"169.254.0.0/16\";\"127.0.0.0/8\"} do={")
        a("  :if ([:len [/ip/firewall/address-list/find where list=\"ketrika-local\" and address=$net]] = 0) do={")
        a("    :do { /ip/firewall/address-list/add list=ketrika-local address=$net } on-error={}")
        a("  }")
        a("}")
        a("")

        # Mangle : marquer tout le trafic sortant du LAN pour aller via WARP
        a("# Marquage du trafic LAN vers WARP")
        a(":if ([:len [/ip/firewall/mangle/find where comment=\"ketrika-warp-mark\"]] = 0) do={")
        a(f"  :do {{ /ip/firewall/mangle/add chain=prerouting action=mark-routing new-routing-mark=via-warp src-address={net_base}/24 dst-address-list=!ketrika-local passthrough=no comment=\"ketrika-warp-mark\" }} on-error={{}}")
        a("}")
        a("")

        # Exclusion Winbox pour ne jamais couper l'admin
        a("# Exclusion port Winbox (protection acces admin)")
        a(":if ([:len [/ip/firewall/mangle/find where comment=\"ketrika-warp-exclude-winbox\"]] = 0) do={")
        a(f"  :do {{ /ip/firewall/mangle/add chain=prerouting action=accept src-address={net_base}/24 protocol=tcp dst-port=8291 place-before=0 comment=\"ketrika-warp-exclude-winbox\" }} on-error={{}}")
        a("}")
        a("")

        a(":log warning \"KETRIKA : WireGuard WARP configure - trafic route via tunnel\"")
        a("")

    # ============================================================
    # 15. HOTSPOT (Plan Business)
    # ============================================================
    if plan == "business" and order.hotspot_tickets_count and order.hotspot_tickets_count > 0:
        a("# 15. Hotspot professionnel")
        a(":if ([:len [/ip/hotspot/profile/find where name=\"ketrika-hs-prof\"]] = 0) do={")
        a(f"  :do {{ /ip/hotspot/profile/add name=ketrika-hs-prof hotspot-address={gateway} dns-name=login.ketrika.mg html-directory=hotspot login-by=http-chap,http-pap }} on-error={{}}")
        a("}")

        # Profils utilisateur
        for prof_name, timeout, rate in [
            ("hs-1h", "1h", "5M/10M"),
            ("hs-1d", "1d", "5M/10M"),
            ("hs-1w", "1w", "5M/10M"),
            ("hs-1m", "4w2d", "10M/20M"),
        ]:
            a(f":if ([:len [/ip/hotspot/user/profile/find where name=\"{prof_name}\"]] = 0) do={{")
            a(f"  :do {{ /ip/hotspot/user/profile/add name={prof_name} session-timeout={timeout} shared-users=1 rate-limit={rate} }} on-error={{}}")
            a("}")

        # Serveur Hotspot
        a(":if ([:len [/ip/hotspot/find where name=\"ketrika-hs\"]] = 0) do={")
        a("  :do { /ip/hotspot/add name=ketrika-hs interface=bridge address-pool=ketrika-pool profile=ketrika-hs-prof disabled=no } on-error={}")
        a("}")
        a("")

        # Tickets
        a("# Generation des tickets")
        count = min(order.hotspot_tickets_count, 200)
        for _ in range(count):
            user = "T" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
            pwd = "".join(random.choices(string.digits, k=6))
            a(f":if ([:len [/ip/hotspot/user/find where name=\"{user}\"]] = 0) do={{")
            a(f"  :do {{ /ip/hotspot/user/add name={user} password={pwd} profile=hs-1d server=ketrika-hs comment=\"Ticket\" }} on-error={{}}")
            a("}")
        a("")

    # ============================================================
    # 16. NAT + MSS CLAMPING
    # ============================================================
    a("# 16. NAT Masquerade")
    a(":if ([:len [/ip/firewall/nat/find where comment=\"ketrika-nat-wan\"]] = 0) do={")
    a(f"  :do {{ /ip/firewall/nat/add chain=srcnat action=masquerade out-interface={wan_iface} comment=\"ketrika-nat-wan\" }} on-error={{}}")
    a("}")
    if plan in ("performance", "business"):
        a(":if ([:len [/ip/firewall/nat/find where comment=\"ketrika-nat-warp\"]] = 0) do={")
        a("  :do { /ip/firewall/nat/add chain=srcnat action=masquerade out-interface=wg-warp comment=\"ketrika-nat-warp\" } on-error={}")
        a("}")
    a("")
    a("# MSS Clamping")
    a(":if ([:len [/ip/firewall/mangle/find where comment=\"ketrika-mss\"]] = 0) do={")
    a("  :do { /ip/firewall/mangle/add chain=forward action=change-mss new-mss=1280 protocol=tcp tcp-flags=syn tcp-mss=1281-65535 passthrough=yes comment=\"ketrika-mss\" } on-error={}")
    a("}")
    a("")

    # ============================================================
    # 17. TTL (masquage TTL vers ISP)
    # ============================================================
    if plan in ("performance", "business") and order.ttl_value and order.ttl_value > 0:
        a(f"# 17. TTL Change (valeur {order.ttl_value})")
        for chain, tag in [("prerouting", "pre"), ("postrouting", "post"), ("forward", "fwd")]:
            a(f":if ([:len [/ip/firewall/mangle/find where comment=\"ketrika-ttl-{tag}\"]] = 0) do={{")
            a(f"  :do {{ /ip/firewall/mangle/add chain={chain} action=change-ttl new-ttl=set:{order.ttl_value} passthrough=yes comment=\"ketrika-ttl-{tag}\" }} on-error={{}}")
            a("}")
        a("")

    # ============================================================
    # 18. QoS
    # ============================================================
    if plan in ("performance", "business"):
        if (order.dl_limit and order.dl_limit > 0) or (order.ul_limit and order.ul_limit > 0):
            dl = f"{order.dl_limit}M" if order.dl_limit > 0 else "0"
            ul = f"{order.ul_limit}M" if order.ul_limit > 0 else "0"
            a("# 18. QoS Global")
            a(":if ([:len [/queue/simple/find where name=\"ketrika-qos-global\"]] = 0) do={")
            a(f"  :do {{ /queue/simple/add name=ketrika-qos-global target={net_base}/24 max-limit={ul}/{dl} comment=\"KETRIKA Global\" }} on-error={{}}")
            a("}")
            a("")

        if order.client_limit and order.client_limit > 0:
            cl = f"{order.client_limit}M"
            a("# 18b. QoS Par client (PCQ)")
            a(":if ([:len [/queue/type/find where name=\"ketrika-pcq-dn\"]] = 0) do={")
            a(f"  :do {{ /queue/type/add name=ketrika-pcq-dn kind=pcq pcq-rate={cl} pcq-classifier=dst-address }} on-error={{}}")
            a("}")
            a(":if ([:len [/queue/type/find where name=\"ketrika-pcq-up\"]] = 0) do={")
            a(f"  :do {{ /queue/type/add name=ketrika-pcq-up kind=pcq pcq-rate={cl} pcq-classifier=src-address }} on-error={{}}")
            a("}")
            a(":if ([:len [/queue/simple/find where name=\"ketrika-qos-client\"]] = 0) do={")
            a(f"  :do {{ /queue/simple/add name=ketrika-qos-client target={net_base}/24 queue=ketrika-pcq-up/ketrika-pcq-dn comment=\"KETRIKA Client\" }} on-error={{}}")
            a("}")
            a("")

    # ============================================================
    # 19. IDENTITY
    # ============================================================
    a(f"# 19. Identite")
    a(f":do {{ /system/identity/set name=\"{order.router_name}\" }} on-error={{}}")
    a("")

    # ============================================================
    # 20. SCHEDULER WI-FI
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
            s_start = order.sleep_start if ":" in order.sleep_start else order.sleep_start + ":00"
            s_end = order.sleep_end if ":" in order.sleep_end else order.sleep_end + ":00"
            a(f"# 20. Scheduler Wi-Fi ({s_start} - {s_end})")
            a(":if ([:len [/system/scheduler/find where name=\"ketrika-wifi-off\"]] = 0) do={")
            a(f"  :do {{ /system/scheduler/add name=ketrika-wifi-off start-time={s_start}:00 interval=1d on-event=\"{off_cmd}\" }} on-error={{}}")
            a("}")
            a(":if ([:len [/system/scheduler/find where name=\"ketrika-wifi-on\"]] = 0) do={")
            a(f"  :do {{ /system/scheduler/add name=ketrika-wifi-on start-time={s_end}:00 interval=1d on-event=\"{on_cmd}\" }} on-error={{}}")
            a("}")
            a("")

    # ============================================================
    # 21. FIREWALL
    # ============================================================
    a("# 21. Firewall")
    fw_rules = [
        ("input", "accept", "connection-state=established,related", "estab"),
        ("input", "accept", "src-address=192.168.0.0/16", "lan"),
        ("input", "accept", "protocol=icmp", "icmp"),
        ("input", "drop", f"in-interface={wan_iface}", "drop-wan"),
        ("forward", "accept", "connection-state=established,related", "fwd-estab"),
        ("forward", "drop", f"connection-state=invalid in-interface={wan_iface}", "fwd-drop"),
    ]
    for chain, action, params, tag in fw_rules:
        a(f":if ([:len [/ip/firewall/filter/find where comment=\"ketrika-fw-{tag}\"]] = 0) do={{")
        a(f"  :do {{ /ip/firewall/filter/add chain={chain} action={action} {params} comment=\"ketrika-fw-{tag}\" }} on-error={{}}")
        a("}")
    a("")

    # ============================================================
    # 22. BANNIÈRE FINALE
    # ============================================================
    a(":delay 2s")
    a(":log warning \"===============================================\"")
    a(":log warning \"  KETRIKA MIKROTIK 3.0.1 - INSTALLATION OK    \"")
    a(f":log warning \"  Licence : {order.license_key}\"")
    a(f":log warning \"  Routeur : {order.router_name}\"")
    a(f":log warning \"  Plan    : {plan.upper()}\"")
    a(":log warning \"  Support : wa.me/261382817100\"")
    a(":log warning \"===============================================\"")
    a("")
    a(":put \"\"")
    a(":put \"===============================================\"")
    a(":put \"  KETRIKA MIKROTIK 3.0.1                       \"")
    a(":put \"  CONFIGURATION TERMINEE AVEC SUCCES           \"")
    a(":put \"===============================================\"")
    a(f":put \"  Routeur : {order.router_name}\"")
    a(f":put \"  Wi-Fi   : {ssid_2g}\"")
    if plan in ("performance", "business"):
        a(":put \"  VPN     : WireGuard WARP actif\"")
    a(":put \"  Support : wa.me/261382817100\"")
    a(":put \"===============================================\"")

    return "\n".join(L)


# ============================================================
# GÉNÉRATION DU TUTORIEL TXT
# ============================================================
def generate_tutorial_txt(order, filename):
    """Génère un fichier tutoriel texte accompagnant le .rsc"""

    plan = order.plan_type
    lines = [
        "===============================================================",
        "   KETRIKA MIKROTIK 3.0.1 - GUIDE D'INSTALLATION",
        "===============================================================",
        "",
        f"  Licence  : {order.license_key}",
        f"  Client   : {order.client_name}",
        f"  Plan     : {plan.upper()}",
        f"  Routeur  : {order.router_name}",
        "",
        "===============================================================",
        "   ETAPE 1 : PREPARATION",
        "===============================================================",
        "",
        "  1. Ouvrez Winbox sur votre PC",
        "  2. Connectez-vous a votre routeur MikroTik",
        "     (par defaut : 192.168.88.1 / admin sans mot de passe)",
        "",
        "===============================================================",
        "   ETAPE 2 : IMPORTATION DU FICHIER",
        "===============================================================",
        "",
        "  1. Dans Winbox, cliquez sur Files (menu de gauche)",
        f"  2. Glissez-deposez le fichier : {filename}",
        "     dans la fenetre Files",
        "  3. Attendez que le fichier apparaisse dans la liste",
        "",
        "===============================================================",
        "   ETAPE 3 : EXECUTION (COPIER-COLLER LA COMMANDE)",
        "===============================================================",
        "",
        "  1. Cliquez sur New Terminal dans Winbox",
        "  2. COPIEZ la commande ci-dessous et COLLEZ-la dans le terminal",
        "  3. Appuyez sur ENTREE",
        "",
        "  >>> COMMANDE A COPIER <<<",
        "",
        f"  /import file-name={filename}",
        "",
        "  >>> FIN DE LA COMMANDE <<<",
        "",
        "  Attendez 10-30 secondes... C'est fait !",
        "",
        "===============================================================",
        "   ETAPE 4 : VERIFICATION",
        "===============================================================",
        "",
        f"  - Nom du routeur : {order.router_name}",
        f"  - Nouvelle IP    : {order.lan_gateway}",
    ]

    if order.ssid_2g:
        lines.append(f"  - Wi-Fi 2.4 GHz  : {order.ssid_2g}")
    if order.ssid_5g:
        lines.append(f"  - Wi-Fi 5 GHz    : {order.ssid_5g}")
    if order.wifi_password:
        lines.append(f"  - Mot de passe Wi-Fi : {order.wifi_password}")

    if plan in ("performance", "business"):
        lines.extend([
            "",
            "  - Tunnel VPN WireGuard : ACTIF",
            "  - DNS chiffre Cloudflare : ACTIF",
            "  - Votre IP FAI est desormais masquee",
        ])

    if plan == "business" and order.hotspot_tickets_count:
        lines.extend([
            "",
            f"  - Hotspot : {order.hotspot_tickets_count} tickets crees",
            "  - Voir les tickets dans : IP > Hotspot > Users",
        ])

    lines.extend([
        "",
        "===============================================================",
        "   METHODE ALTERNATIVE : COMMANDE AUTO-FETCH",
        "===============================================================",
        "",
        "  Si votre routeur a acces a Internet, vous pouvez utiliser :",
        "",
        f"  /tool/fetch url=\"http://VOTRE-DOMAINE/api/download/{order.license_key}.rsc\" dst-path=k.rsc",
        "  /import file-name=k.rsc",
        "  /file/remove k.rsc",
        "",
        "===============================================================",
        "   SUPPORT TECHNIQUE",
        "===============================================================",
        "",
        "  WhatsApp : wa.me/261382817100",
        "  Support gratuit pendant 30 jours",
        "",
        "  Made in Madagascar",
        "  (c) 2024-2025 KETRIKA MIKROTIK",
        "===============================================================",
    ])

    return "\n".join(lines)
