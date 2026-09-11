# -*- coding: utf-8 -*-
"""
KETRIKA MIKROTIK - Moteur de génération du fichier .rsc
Génère un script RouterOS v7 complet et sécurisé
"""

import json
from datetime import datetime


# ============================================================
# GÉNÉRATION DU FICHIER .RSC ROUTEROS v7
# ============================================================
def generate_rsc(order, model_info):
    """
    Génère le script complet .rsc à importer via /import dans Winbox
    order : instance Order
    model_info : dict retourné par get_model_info()
    """

    plan = order.plan_type
    has_wifi_24 = model_info.get("wifi_24ghz", False)
    has_wifi_5 = model_info.get("wifi_5ghz", False)
    wifi_type = model_info.get("wifi_type")  # ax / ac / n / None
    ports = model_info.get("ports", 5)

    lines = []
    add = lines.append

    # ------------------------------------------------------------
    # EN-TÊTE
    # ------------------------------------------------------------
    add("# ============================================================")
    add(f"# KETRIKA MIKROTIK - Configuration automatique")
    add(f"# Licence : {order.license_key}")
    add(f"# Client  : {order.client_name}")
    add(f"# Plan    : {plan.upper()}")
    add(f"# Modèle  : {model_info['name']}")
    add(f"# Généré  : {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    add("# ============================================================")
    add("")
    add(":log warning \"KETRIKA: Debut de la configuration\"")
    add(":delay 1s")
    add("")

    # ------------------------------------------------------------
    # 1. DÉSACTIVATION FASTTRACK
    # ------------------------------------------------------------
    add("# --- Desactivation FastTrack ---")
    add("/ip firewall filter")
    add(":foreach r in=[find where action=fasttrack-connection] do={ set $r disabled=yes }")
    add("")

    # ------------------------------------------------------------
    # 2. MAC-SERVER SUR TOUTES LES INTERFACES
    # ------------------------------------------------------------
    add("# --- Activation MAC-Server sur toutes les interfaces ---")
    add("/tool mac-server")
    add("set allowed-interface-list=all")
    add("/tool mac-server mac-winbox")
    add("set allowed-interface-list=all")
    add("/tool mac-server ping")
    add("set enabled=yes")
    add("")

    # ------------------------------------------------------------
    # 3. PROTECTION WINBOX & SSH
    # ------------------------------------------------------------
    add("# --- Protection acces Winbox / SSH ---")
    add("/ip service")
    add(":do { set winbox port=8291 } on-error={}")
    add(":do { set ssh port=22 } on-error={}")
    add(":do { disable telnet } on-error={}")
    add(":do { disable ftp } on-error={}")
    add(":do { disable api } on-error={}")
    add(":do { disable api-ssl } on-error={}")
    add("")

    # ------------------------------------------------------------
    # 4. BRIDGE D'USINE
    # ------------------------------------------------------------
    add("# --- Bridge par defaut : on utilise 'bridge' sans le modifier ---")
    add("/interface bridge")
    add(":if ([:len [find where name=\"bridge\"]] = 0) do={ add name=bridge }")
    add("")

    # ------------------------------------------------------------
    # 5. AJOUT DES PORTS AU BRIDGE (verification avec find)
    # ------------------------------------------------------------
    add("# --- Ajout des ports Ethernet au bridge (verification) ---")
    add("/interface bridge port")
    wan_iface = order.wan_interface or "ether1"
    for i in range(2, ports + 1):
        eth = f"ether{i}"
        add(f":if ([:len [/interface ethernet find where name=\"{eth}\"]] > 0) do={{")
        add(f"  :if ([:len [find where interface=\"{eth}\"]] = 0) do={{ add bridge=bridge interface={eth} }}")
        add("}")
    add("")

    # ------------------------------------------------------------
    # 6. DOUBLE IP : gateway personnalisée + secours 192.168.88.1
    # ------------------------------------------------------------
    add("# --- Adresses IP (gateway personnalisee + secours 192.168.88.1) ---")
    add("/ip address")
    add(f":if ([:len [find where address~\"{order.lan_gateway}\"]] = 0) do={{ add address={order.lan_gateway}/24 interface=bridge network={order.lan_network.split('/')[0]} }}")
    add(":if ([:len [find where address~\"192.168.88.1\"]] = 0) do={ add address=192.168.88.1/24 interface=bridge network=192.168.88.0 }")
    add("")

    # ------------------------------------------------------------
    # 7. DHCP SERVER + POOL + DNS
    # ------------------------------------------------------------
    add("# --- Pool DHCP ---")
    add("/ip pool")
    add(f":if ([:len [find where name=\"ketrika-pool\"]] = 0) do={{ add name=ketrika-pool ranges={order.dhcp_pool_start}-{order.dhcp_pool_end} }}")
    add("")
    add("# --- DHCP Server ---")
    add("/ip dhcp-server")
    add(":if ([:len [find where name=\"ketrika-dhcp\"]] = 0) do={ add name=ketrika-dhcp interface=bridge address-pool=ketrika-pool disabled=no lease-time=1d }")
    add("/ip dhcp-server network")
    net_base = ".".join(order.lan_gateway.split(".")[:3]) + ".0"
    add(f":if ([:len [find where address=\"{net_base}/24\"]] = 0) do={{ add address={net_base}/24 gateway={order.lan_gateway} dns-server=1.1.1.1,8.8.8.8 }}")
    add("")
    add("# --- DNS chiffre ---")
    add("/ip dns")
    add("set servers=1.1.1.1,8.8.8.8 allow-remote-requests=yes")
    add(":do { set use-doh-server=\"https://cloudflare-dns.com/dns-query\" verify-doh-cert=yes } on-error={}")
    add("")

    # ------------------------------------------------------------
    # 8. DHCP CLIENT WAN
    # ------------------------------------------------------------
    add("# --- Client DHCP sur WAN ---")
    add("/ip dhcp-client")
    add(f":if ([:len [find where interface=\"{wan_iface}\"]] = 0) do={{ add interface={wan_iface} disabled=no add-default-route=yes use-peer-dns=no }}")
    add("")

    # ------------------------------------------------------------
    # 9. MAC SPOOFING CONDITIONNEL (plan 2+)
    # ------------------------------------------------------------
    if plan in ("performance", "business") and order.mac_spoof and order.mac_address:
        add("# --- MAC Spoofing WAN ---")
        add("/interface ethernet")
        add(f":do {{ set [find where name=\"{wan_iface}\"] mac-address={order.mac_address} }} on-error={{}}")
        add("")

    # ------------------------------------------------------------
    # 10 & 11. Wi-Fi AX (/interface wifi) et AC/N (/interface wireless)
    # ------------------------------------------------------------
    if has_wifi_24 or has_wifi_5:
        add("# --- Configuration Wi-Fi ---")
        ssid_2g = order.ssid_2g or f"KETRIKA-{order.license_key[-4:]}"
        ssid_5g = order.ssid_5g or ssid_2g + "-5G"
        wpwd = order.wifi_password or "ketrika2024"

        if wifi_type == "ax":
            # RouterOS v7 - /interface wifi
            add("# --- Wi-Fi AX (RouterOS v7 /interface wifi) ---")
            add(":do {")
            add(f"  /interface wifi security add name=ketrika-sec authentication-types=wpa2-psk,wpa3-psk passphrase=\"{wpwd}\"")
            add("} on-error={}")
            add(":do {")
            add(f"  /interface wifi configuration add name=ketrika-cfg-2g ssid=\"{ssid_2g}\" security=ketrika-sec country=Madagascar")
            add("} on-error={}")
            if has_wifi_5:
                add(":do {")
                add(f"  /interface wifi configuration add name=ketrika-cfg-5g ssid=\"{ssid_5g}\" security=ketrika-sec country=Madagascar")
                add("} on-error={}")
            add(":do {")
            add("  /interface wifi set [find where default-name=\"wifi1\"] configuration=ketrika-cfg-2g disabled=no")
            add("} on-error={}")
            if has_wifi_5:
                add(":do {")
                add("  /interface wifi set [find where default-name=\"wifi2\"] configuration=ketrika-cfg-5g disabled=no")
                add("} on-error={}")
        else:
            # Wi-Fi AC / N -> /interface wireless
            add("# --- Wi-Fi AC/N (/interface wireless) ---")
            add(":do {")
            add(f"  /interface wireless security-profiles add name=ketrika-sec mode=dynamic-keys authentication-types=wpa2-psk wpa2-pre-shared-key=\"{wpwd}\"")
            add("} on-error={}")
            add(":do {")
            add(f"  /interface wireless set [find where default-name=\"wlan1\"] ssid=\"{ssid_2g}\" security-profile=ketrika-sec mode=ap-bridge band=2ghz-b/g/n channel-width=20/40mhz-XX disabled=no")
            add("} on-error={}")
            if has_wifi_5:
                add(":do {")
                add(f"  /interface wireless set [find where default-name=\"wlan2\"] ssid=\"{ssid_5g}\" security-profile=ketrika-sec mode=ap-bridge band=5ghz-a/n/ac channel-width=20/40/80mhz-XXXX disabled=no")
                add("} on-error={}")

        # 12. Ajout des interfaces Wi-Fi au bridge
        add("")
        add("# --- Ajout des interfaces Wi-Fi au bridge ---")
        add("/interface bridge port")
        if wifi_type == "ax":
            add(":do {")
            add(":if ([:len [find where interface=\"wifi1\"]] = 0) do={ add bridge=bridge interface=wifi1 }")
            add("} on-error={}")
            if has_wifi_5:
                add(":do {")
                add(":if ([:len [find where interface=\"wifi2\"]] = 0) do={ add bridge=bridge interface=wifi2 }")
                add("} on-error={}")
        else:
            add(":do {")
            add(":if ([:len [find where interface=\"wlan1\"]] = 0) do={ add bridge=bridge interface=wlan1 }")
            add("} on-error={}")
            if has_wifi_5:
                add(":do {")
                add(":if ([:len [find where interface=\"wlan2\"]] = 0) do={ add bridge=bridge interface=wlan2 }")
                add("} on-error={}")
        add("")

    # ------------------------------------------------------------
    # 13. WIREGUARD WARP (plan 2+)
    # ------------------------------------------------------------
    if plan in ("performance", "business"):
        add("# --- WireGuard WARP (tunnel VPN nouvelle generation) ---")
        add("/interface wireguard")
        add(":if ([:len [find where name=\"wg-warp\"]] = 0) do={ add name=wg-warp listen-port=13231 mtu=1280 }")
        add("")
        add("# NOTE : Les cles WARP doivent etre configurees manuellement ou via API")
        add("# /interface wireguard peers add interface=wg-warp public-key=\"...\" endpoint-address=... endpoint-port=... allowed-address=0.0.0.0/0")
        add("")
        add("# --- Routing table dediee ---")
        add("/routing table")
        add(":if ([:len [find where name=\"via-secure\"]] = 0) do={ add name=via-secure fib }")
        add("")
        add("# --- Mangle : marquage routing (exclusion 8291 + LAN) ---")
        add("/ip firewall mangle")
        add(":if ([:len [find where comment=\"ketrika-mark\"]] = 0) do={")
        add("  add chain=prerouting action=mark-routing new-routing-mark=via-secure passthrough=no \\")
        add("    src-address=192.168.10.0/24 dst-address-list=!local-nets protocol=!icmp \\")
        add("    comment=\"ketrika-mark\"")
        add("}")
        add("/ip firewall address-list")
        add(":if ([:len [find where list=\"local-nets\"]] = 0) do={")
        add("  add list=local-nets address=192.168.0.0/16")
        add("  add list=local-nets address=10.0.0.0/8")
        add("  add list=local-nets address=172.16.0.0/12")
        add("}")
        add("")

    # ------------------------------------------------------------
    # 15. HOTSPOT (plan 3)
    # ------------------------------------------------------------
    if plan == "business" and order.hotspot_tickets_count > 0:
        add("# --- Portail captif Hotspot ---")
        add("/ip hotspot profile")
        add(":if ([:len [find where name=\"ketrika-hs-profile\"]] = 0) do={")
        add("  add name=ketrika-hs-profile hotspot-address=" + order.lan_gateway + " dns-name=login.ketrika.mg html-directory=hotspot login-by=http-chap,http-pap")
        add("}")
        add("/ip hotspot user profile")
        add(":if ([:len [find where name=\"hs-1hour\"]] = 0) do={ add name=hs-1hour session-timeout=1h shared-users=1 }")
        add(":if ([:len [find where name=\"hs-1day\"]] = 0) do={ add name=hs-1day session-timeout=1d shared-users=1 }")
        add(":if ([:len [find where name=\"hs-1week\"]] = 0) do={ add name=hs-1week session-timeout=1w shared-users=1 }")
        add(":if ([:len [find where name=\"hs-1month\"]] = 0) do={ add name=hs-1month session-timeout=4w shared-users=1 }")
        add("/ip hotspot")
        add(":if ([:len [find where name=\"ketrika-hs\"]] = 0) do={ add name=ketrika-hs interface=bridge address-pool=ketrika-pool profile=ketrika-hs-profile disabled=no }")
        add("")
        add("# --- Generation des tickets ---")
        add("/ip hotspot user")
        import random
        import string
        for i in range(min(order.hotspot_tickets_count, 100)):
            user = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            pwd = ''.join(random.choices(string.digits, k=6))
            add(f":if ([:len [find where name=\"{user}\"]] = 0) do={{ add name={user} password={pwd} profile=hs-1day }}")
        add("")

    # ------------------------------------------------------------
    # 16. NAT MASQUERADE + MSS CLAMPING
    # ------------------------------------------------------------
    add("# --- NAT Masquerade sur WAN ---")
    add("/ip firewall nat")
    add(f":if ([:len [find where comment=\"ketrika-nat-wan\"]] = 0) do={{ add chain=srcnat action=masquerade out-interface={wan_iface} comment=\"ketrika-nat-wan\" }}")
    if plan in ("performance", "business"):
        add(":if ([:len [find where comment=\"ketrika-nat-wg\"]] = 0) do={ add chain=srcnat action=masquerade out-interface=wg-warp comment=\"ketrika-nat-wg\" }")
    add("")
    add("# --- MSS Clamping (evite fragmentation) ---")
    add("/ip firewall mangle")
    add(":if ([:len [find where comment=\"ketrika-mss\"]] = 0) do={")
    add("  add chain=forward action=change-mss new-mss=1280 tcp-flags=syn protocol=tcp tcp-mss=1281-65535 comment=\"ketrika-mss\"")
    add("}")
    add("")

    # ------------------------------------------------------------
    # 17. ANTI-TTL (masquage TTL)
    # ------------------------------------------------------------
    if plan in ("performance", "business") and order.ttl_value > 0:
        add("# --- Optimisation TTL ---")
        add("/ip firewall mangle")
        add(f":if ([:len [find where comment=\"ketrika-ttl-pre\"]] = 0) do={{ add chain=prerouting action=change-ttl new-ttl=set:{order.ttl_value} passthrough=yes comment=\"ketrika-ttl-pre\" }}")
        add(f":if ([:len [find where comment=\"ketrika-ttl-post\"]] = 0) do={{ add chain=postrouting action=change-ttl new-ttl=set:{order.ttl_value} passthrough=yes comment=\"ketrika-ttl-post\" }}")
        add("")

    # ------------------------------------------------------------
    # 18. QOS - SIMPLE QUEUE
    # ------------------------------------------------------------
    if plan in ("performance", "business") and (order.dl_limit > 0 or order.ul_limit > 0):
        dl = f"{order.dl_limit}M" if order.dl_limit > 0 else "0"
        ul = f"{order.ul_limit}M" if order.ul_limit > 0 else "0"
        add("# --- QoS Simple Queue Global ---")
        add("/queue simple")
        add(f":if ([:len [find where name=\"ketrika-global\"]] = 0) do={{ add name=ketrika-global target=192.168.10.0/24 max-limit={ul}/{dl} }}")
        add("")
    if plan in ("performance", "business") and order.client_limit > 0:
        cl = f"{order.client_limit}M"
        add("# --- Limitation par client ---")
        add("/queue simple")
        add(f":if ([:len [find where name=\"ketrika-per-client\"]] = 0) do={{ add name=ketrika-per-client target=192.168.10.0/24 max-limit={cl}/{cl} queue=pcq-upload-default/pcq-download-default }}")
        add("")

    # ------------------------------------------------------------
    # 19. IDENTITY (nom du routeur)
    # ------------------------------------------------------------
    add("# --- Identite du routeur ---")
    add("/system identity")
    add(f"set name=\"{order.router_name}\"")
    add("")

    # ------------------------------------------------------------
    # 20. SCHEDULER MISE EN VEILLE WI-FI
    # ------------------------------------------------------------
    if order.sleep_mode and order.sleep_mode != "off" and order.sleep_start and order.sleep_end:
        add("# --- Scheduler mise en veille Wi-Fi ---")
        # Off script
        if wifi_type == "ax":
            off_cmd = "/interface wifi disable [find]"
            on_cmd = "/interface wifi enable [find]"
        else:
            off_cmd = "/interface wireless disable [find]"
            on_cmd = "/interface wireless enable [find]"

        add("/system scheduler")
        add(f":if ([:len [find where name=\"ketrika-wifi-off\"]] = 0) do={{ add name=ketrika-wifi-off start-time={order.sleep_start}:00 interval=1d on-event=\"{off_cmd}\" }}")
        add(f":if ([:len [find where name=\"ketrika-wifi-on\"]] = 0) do={{ add name=ketrika-wifi-on start-time={order.sleep_end}:00 interval=1d on-event=\"{on_cmd}\" }}")
        add("")

    # ------------------------------------------------------------
    # 21. FIREWALL FINAL
    # ------------------------------------------------------------
    add("# --- Firewall (regles de base) ---")
    add("/ip firewall filter")
    add(":if ([:len [find where comment=\"ketrika-established\"]] = 0) do={ add chain=input action=accept connection-state=established,related comment=\"ketrika-established\" }")
    add(":if ([:len [find where comment=\"ketrika-lan-input\"]] = 0) do={ add chain=input action=accept src-address=192.168.0.0/16 comment=\"ketrika-lan-input\" }")
    add(":if ([:len [find where comment=\"ketrika-icmp\"]] = 0) do={ add chain=input action=accept protocol=icmp comment=\"ketrika-icmp\" }")
    add(f":if ([:len [find where comment=\"ketrika-drop-wan\"]] = 0) do={{ add chain=input action=drop in-interface={wan_iface} comment=\"ketrika-drop-wan\" }}")
    add("")

    # ------------------------------------------------------------
    # 22. BANNIÈRE DE SUCCÈS
    # ------------------------------------------------------------
    add(":log warning \"===================================================\"")
    add(":log warning \"  KETRIKA MIKROTIK - Configuration terminee !     \"")
    add(f":log warning \"  Licence : {order.license_key}\"")
    add(f":log warning \"  Routeur : {order.router_name}\"")
    add(":log warning \"  Merci de votre confiance - Made in Madagascar   \"")
    add(":log warning \"===================================================\"")
    add(":put \"\"")
    add(":put \"    _  _______ _____ ____  ___ _  __    _   \"")
    add(":put \"   | |/ / ____|_   _|  _ \\|_ _| |/ /   / \\  \"")
    add(":put \"   | ' /|  _|   | | | |_) || || ' /   / _ \\ \"")
    add(":put \"   | . \\| |___  | | |  _ < | || . \\  / ___ \\\"")
    add(":put \"   |_|\\_\\_____| |_| |_| \\_\\___|_|\\_\\/_/   \\_\\\"")
    add(":put \"\"")
    add(":put \"   Configuration KETRIKA importee avec succes !\"")
    add(":put \"\"")

    return "\n".join(lines)
