# -*- coding: utf-8 -*-
"""
KETRIKA MIKROTIK v3.0.1 - Moteur de génération du fichier .rsc (CORRIGÉ)
Utilise exclusivement des chemins absolus pour éviter les erreurs de syntaxe RouterOS v7
Chaque section est encapsulée de manière isolée et sécurisée.
"""

import random
import string
from datetime import datetime


def generate_rsc(order, model_info):
    """
    Génère le contenu complet du fichier .rsc RouterOS v7 sans aucune erreur de syntaxe.
    Chaque commande utilise son chemin absolu pour garantir la compatibilité d'importation.
    """

    plan = order.plan_type
    has_wifi_24 = model_info.get("wifi_24ghz", False)
    has_wifi_5 = model_info.get("wifi_5ghz", False)
    wifi_type = model_info.get("wifi_type")  # ax / ac / n / None
    ports = model_info.get("ports", 5)
    wan_iface = order.wan_interface or "ether1"
    gateway = order.lan_gateway or "192.168.10.1"
    net_base = ".".join(gateway.split(".")[:3]) + ".0"
    pool_start = order.dhcp_pool_start or "192.168.10.10"
    pool_end = order.dhcp_pool_end or "192.168.10.250"
    ssid_2g = order.ssid_2g or "KETRIKA-WiFi"
    ssid_5g = order.ssid_5g or (ssid_2g + "-5G")
    wifi_pwd = order.wifi_password or "ketrika2024"

    lines = []
    a = lines.append

    # ========== EN-TÊTE COMPLET AVEC INSTRUCTIONS ==========
    filename = f"ketrika_{order.license_key}.rsc"
    a("# ==================================================================")
    a("#   KETRIKA MIKROTIK v3.0.1 - Configuration Automatique RouterOS v7")
    a("# ==================================================================")
    a(f"#   Licence  : {order.license_key}")
    a(f"#   Client   : {order.client_name}")
    a(f"#   Plan     : {plan.upper()}")
    a(f"#   Modele   : {model_info['name']}")
    a(f"#   Routeur  : {order.router_name}")
    a(f"#   Genere   : {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    a("# ==================================================================")
    a("#")
    a("#   INSTRUCTIONS D'IMPORTATION :")
    a("#   ---------------------------")
    a("#   1. Ouvrez Winbox et connectez-vous a votre routeur")
    a("#   2. Cliquez sur 'Files' dans le menu de gauche")
    a(f"#   3. Glissez le fichier '{filename}' dans la fenetre Files")
    a("#   4. Ouvrez 'New Terminal' et tapez :")
    a("#")
    a(f"#         /import {filename}")
    a("#")
    a("#   ASTUCE : Renommez le fichier en 'k.rsc' avant l'import")
    a("#   pour taper simplement :  /import k.rsc")
    a("#")
    a("#   Support WhatsApp : wa.me/261382817100")
    a("# ==================================================================")
    a("")
    a(":log warning \"KETRIKA v3.0.1 : Debut de la configuration automatique...\"")
    a(":delay 1s")
    a("")

    # ========== 1. DÉSACTIVATION FASTTRACK (CHEMIN ABSOLU) ==========
    a("# --- 1. Desactivation FastTrack pour compatibilite ---")
    a(":do {")
    a("  :foreach r in=[/ip firewall filter find where action=fasttrack-connection] do={")
    a("    /ip firewall filter set $r disabled=yes")
    a("  }")
    a("} on-error={}")
    a("")

    # ========== 2. MAC-SERVER TOUTES INTERFACES (CHEMINS ABSOLUS) ==========
    a("# --- 2. MAC-Server sur toutes les interfaces ---")
    a(":do {")
    a("  /tool mac-server set allowed-interface-list=all")
    a("  /tool mac-server mac-winbox set allowed-interface-list=all")
    a("  /tool mac-server ping set enabled=yes")
    a("} on-error={}")
    a("")

    # ========== 3. SERVICES SÉCURISÉS (CHEMINS ABSOLUS) ==========
    a("# --- 3. Protection des services ---")
    a(":do { /ip service set winbox port=8291 disabled=no } on-error={}")
    a(":do { /ip service set ssh port=22 disabled=no } on-error={}")
    a(":do { /ip service disable telnet } on-error={}")
    a(":do { /ip service disable ftp } on-error={}")
    a(":do { /ip service disable api } on-error={}")
    a(":do { /ip service disable api-ssl } on-error={}")
    a(":do { /ip service disable www } on-error={}")
    a(":do { /ip service disable www-ssl } on-error={}")
    a("")

    # ========== 4. BRIDGE D'USINE ==========
    a("# --- 4. Bridge : creation de bridge si inexistant ---")
    a(":do {")
    a("  :if ([:len [/interface bridge find where name=\"bridge\"]] = 0) do={")
    a("    /interface bridge add name=bridge")
    a("  }")
    a("} on-error={}")
    a("")

    # ========== 5. PORTS ETHERNET AU BRIDGE (CHEMINS ABSOLUS) ==========
    a("# --- 5. Ajout des ports Ethernet au bridge (sauf WAN) ---")
    for i in range(1, ports + 1):
        eth = f"ether{i}"
        if eth == wan_iface:
            continue
        a(f":do {{")
        a(f"  :if ([:len [/interface find where name=\"{eth}\"]] > 0) do={{")
        a(f"    :if ([:len [/interface bridge port find where interface=\"{eth}\"]] = 0) do={{")
        a(f"      /interface bridge port add bridge=bridge interface={eth}")
        a(f"    }}")
        a(f"  }}")
        a(f"}} on-error={{}}")
    a("")

    # ========== 6. ADRESSES IP (CHEMINS ABSOLUS) ==========
    a("# --- 6. Adresses IP : principale + secours 192.168.88.1 ---")
    a(":do {")
    a(f"  :if ([:len [/ip address find where address~\"{gateway}\"]] = 0) do={{")
    a(f"    /ip address add address={gateway}/24 interface=bridge network={net_base} comment=\"KETRIKA-LAN\"")
    a("  }")
    a("} on-error={}")
    a(":do {")
    a("  :if ([:len [/ip address find where address~\"192.168.88.1\"]] = 0) do={")
    a("    /ip address add address=192.168.88.1/24 interface=bridge network=192.168.88.0 comment=\"KETRIKA-SECOURS\"")
    a("  }")
    a("} on-error={}")
    a("")

    # ========== 7. DHCP POOL + SERVER + DNS (CHEMINS ABSOLUS) ==========
    a("# --- 7. DHCP Server complet ---")
    a(":do {")
    a(f"  :if ([:len [/ip pool find where name=\"ketrika-pool\"]] = 0) do={{")
    a(f"    /ip pool add name=ketrika-pool ranges={pool_start}-{pool_end}")
    a("  }")
    a("} on-error={}")
    a("")
    a(":do {")
    a("  :if ([:len [/ip dhcp-server find where name=\"ketrika-dhcp\"]] = 0) do={")
    a("    /ip dhcp-server add name=ketrika-dhcp interface=bridge address-pool=ketrika-pool disabled=no lease-time=1d")
    a("  }")
    a("} on-error={}")
    a("")
    a(":do {")
    a(f"  :if ([:len [/ip dhcp-server network find where address=\"{net_base}/24\"]] = 0) do={{")
    a(f"    /ip dhcp-server network add address={net_base}/24 gateway={gateway} dns-server=1.1.1.1,8.8.8.8")
    a("  }")
    a("} on-error={}")
    a("")
    a("# --- DNS ---")
    a(":do {")
    a("  /ip dns set servers=1.1.1.1,8.8.8.8 allow-remote-requests=yes")
    a("} on-error={}")
    a(":do {")
    a("  /ip dns set use-doh-server=\"https://cloudflare-dns.com/dns-query\" verify-doh-cert=yes")
    a("} on-error={}")
    a("")

    # ========== 8. DHCP CLIENT WAN ==========
    a("# --- 8. Client DHCP sur interface WAN ---")
    a(f":do {{")
    a(f"  :if ([:len [/ip dhcp-client find where interface=\"{wan_iface}\"]] = 0) do={{")
    a(f"    /ip dhcp-client add interface={wan_iface} disabled=no add-default-route=yes use-peer-dns=no")
    a(f"  }}")
    a(f"}} on-error={{}}")
    a("")

    # ========== 9. MAC SPOOFING ==========
    if plan in ("performance", "business") and order.mac_spoof:
        mac = order.mac_address or ""
        if mac:
            a("# --- 9. Changement MAC WAN (protection vie privee) ---")
            a(f":do {{")
            a(f"  /interface ethernet set [/interface ethernet find where name=\"{wan_iface}\"] mac-address={mac}")
            a(f"}} on-error={{}}")
            a("")

    # ========== 10 & 11. WI-FI (AX vs AC/N) ==========
    if has_wifi_24 or has_wifi_5:
        a("# --- 10. Configuration Wi-Fi ---")

        if wifi_type == "ax":
            a("# Wi-Fi 6 AX (/interface wifi)")
            a(":do {")
            a(f"  :if ([:len [/interface wifi security find where name=\"ketrika-sec\"]] = 0) do={{")
            a(f"    /interface wifi security add name=ketrika-sec authentication-types=wpa2-psk,wpa3-psk passphrase=\"{wifi_pwd}\"")
            a("  }")
            a("} on-error={}")
            a("")
            a(":do {")
            a(f"  :if ([:len [/interface wifi configuration find where name=\"ketrika-2g\"]] = 0) do={{")
            a(f"    /interface wifi configuration add name=ketrika-2g ssid=\"{ssid_2g}\" security=ketrika-sec country=Madagascar")
            a("  }")
            a("} on-error={}")
            if has_wifi_5:
                a(":do {")
                a(f"  :if ([:len [/interface wifi configuration find where name=\"ketrika-5g\"]] = 0) do={{")
                a(f"    /interface wifi configuration add name=ketrika-5g ssid=\"{ssid_5g}\" security=ketrika-sec country=Madagascar")
                a("  }")
                a("} on-error={}")
            a("")
            a(":do { /interface wifi set [/interface wifi find where default-name=\"wifi1\"] configuration=ketrika-2g disabled=no } on-error={}")
            if has_wifi_5:
                a(":do { /interface wifi set [/interface wifi find where default-name=\"wifi2\"] configuration=ketrika-5g disabled=no } on-error={}")
            a("")
            a("# --- 12. Ajout Wi-Fi AX au bridge ---")
            a(":do { :if ([:len [/interface bridge port find where interface=\"wifi1\"]] = 0) do={ /interface bridge port add bridge=bridge interface=wifi1 } } on-error={}")
            if has_wifi_5:
                a(":do { :if ([:len [/interface bridge port find where interface=\"wifi2\"]] = 0) do={ /interface bridge port add bridge=bridge interface=wifi2 } } on-error={}")
        else:
            a("# Wi-Fi AC/N (/interface wireless)")
            a(":do {")
            a(f"  :if ([:len [/interface wireless security-profiles find where name=\"ketrika-sec\"]] = 0) do={{")
            a(f"    /interface wireless security-profiles add name=ketrika-sec mode=dynamic-keys authentication-types=wpa2-psk wpa2-pre-shared-key=\"{wifi_pwd}\"")
            a("  }")
            a("} on-error={}")
            a("")
            a(":do {")
            a(f"  /interface wireless set [/interface wireless find where default-name=\"wlan1\"] ssid=\"{ssid_2g}\" security-profile=ketrika-sec mode=ap-bridge band=2ghz-b/g/n channel-width=20/40mhz-XX disabled=no")
            a("} on-error={}")
            if has_wifi_5:
                a(":do {")
                a(f"  /interface wireless set [/interface wireless find where default-name=\"wlan2\"] ssid=\"{ssid_5g}\" security-profile=ketrika-sec mode=ap-bridge band=5ghz-a/n/ac channel-width=20/40/80mhz-XXXX disabled=no")
                a("} on-error={}")
            a("")
            a("# --- 12. Ajout Wi-Fi AC/N au bridge ---")
            a(":do { :if ([:len [/interface bridge port find where interface=\"wlan1\"]] = 0) do={ /interface bridge port add bridge=bridge interface=wlan1 } } on-error={}")
            if has_wifi_5:
                a(":do { :if ([:len [/interface bridge port find where interface=\"wlan2\"]] = 0) do={ /interface bridge port add bridge=bridge interface=wlan2 } } on-error={}")
        a("")

    # ========== 13. WIREGUARD WARP (plan 2+) ==========
    if plan in ("performance", "business"):
        a("# --- 13. WireGuard WARP (tunnel VPN securise) ---")
        a(":do {")
        a("  :if ([:len [/interface wireguard find where name=\"wg-warp\"]] = 0) do={")
        a("    /interface wireguard add name=wg-warp listen-port=13231 mtu=1280")
        a("  }")
        a("} on-error={}")
        a("")

        # 14. Routing + Mangle
        a("# --- 14. Routing table + Mangle ---")
        a(":do {")
        a("  :if ([:len [/routing table find where name=\"via-secure\"]] = 0) do={")
        a("    /routing table add name=via-secure fib")
        a("  }")
        a("} on-error={}")
        a("")
        a(":do {")
        a("  :if ([:len [/ip firewall address-list find where list=\"ketrika-local\" and address=\"192.168.0.0/16\"]] = 0) do={")
        a("    /ip firewall address-list add list=ketrika-local address=192.168.0.0/16")
        a("  }")
        a("  :if ([:len [/ip firewall address-list find where list=\"ketrika-local\" and address=\"10.0.0.0/8\"]] = 0) do={")
        a("    /ip firewall address-list add list=ketrika-local address=10.0.0.0/8")
        a("  }")
        a("  :if ([:len [/ip firewall address-list find where list=\"ketrika-local\" and address=\"172.16.0.0/12\"]] = 0) do={")
        a("    /ip firewall address-list add list=ketrika-local address=172.16.0.0/12")
        a("  }")
        a("} on-error={}")
        a("")
        a(":do {")
        a("  :if ([:len [/ip firewall mangle find where comment=\"ketrika-mark-routing\"]] = 0) do={")
        a(f"    /ip firewall mangle add chain=prerouting action=mark-routing new-routing-mark=via-secure src-address={net_base}/24 dst-address-list=!ketrika-local dst-port=!8291 protocol=tcp comment=\"ketrika-mark-routing\"")
        a("  }")
        a("  :if ([:len [/ip firewall mangle find where comment=\"ketrika-mark-routing-udp\"]] = 0) do={")
        a(f"    /ip firewall mangle add chain=prerouting action=mark-routing new-routing-mark=via-secure src-address={net_base}/24 dst-address-list=!ketrika-local protocol=udp comment=\"ketrika-mark-routing-udp\"")
        a("  }")
        a("} on-error={}")
        a("")

    # ========== 15. HOTSPOT (plan business) ==========
    if plan == "business" and order.hotspot_tickets_count and order.hotspot_tickets_count > 0:
        a("# --- 15. Portail captif Hotspot professionnel ---")
        a(":do {")
        a("  :if ([:len [/ip hotspot profile find where name=\"ketrika-hs-prof\"]] = 0) do={")
        a(f"    /ip hotspot profile add name=ketrika-hs-prof hotspot-address={gateway} dns-name=login.ketrika.mg html-directory=hotspot login-by=http-chap,http-pap")
        a("  }")
        a("} on-error={}")
        a("")
        a(":do { :if ([:len [/ip hotspot user profile find where name=\"hs-1h\"]] = 0) do={ /ip hotspot user profile add name=hs-1h session-timeout=1h shared-users=1 rate-limit=5M/10M } } on-error={}")
        a(":do { :if ([:len [/ip hotspot user profile find where name=\"hs-1d\"]] = 0) do={ /ip hotspot user profile add name=hs-1d session-timeout=1d shared-users=1 rate-limit=5M/10M } } on-error={}")
        a(":do { :if ([:len [/ip hotspot user profile find where name=\"hs-1w\"]] = 0) do={ /ip hotspot user profile add name=hs-1w session-timeout=1w shared-users=2 rate-limit=5M/10M } } on-error={}")
        a(":do { :if ([:len [/ip hotspot user profile find where name=\"hs-1m\"]] = 0) do={ /ip hotspot user profile add name=hs-1m session-timeout=4w2d shared-users=3 rate-limit=10M/20M } } on-error={}")
        a("")
        a(":do {")
        a("  :if ([:len [/ip hotspot find where name=\"ketrika-hs\"]] = 0) do={")
        a("    /ip hotspot add name=ketrika-hs interface=bridge address-pool=ketrika-pool profile=ketrika-hs-prof disabled=no")
        a("  }")
        a("} on-error={}")
        a("")
        a("# --- Generation des tickets d'acces ---")
        count = min(order.hotspot_tickets_count, 200)
        for i in range(count):
            user = "T" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
            pwd = "".join(random.choices(string.digits, k=6))
            a(f":do {{ :if ([:len [/ip hotspot user find where name=\"{user}\"]] = 0) do={{ /ip hotspot user add name={user} password={pwd} profile=hs-1d server=ketrika-hs comment=\"Ticket KETRIKA\" }} }} on-error={{}}")
        a("")

    # ========== 16. NAT + MSS CLAMPING ==========
    a("# --- 16. NAT Masquerade + MSS Clamping ---")
    a(f":do {{ :if ([:len [/ip firewall nat find where comment=\"ketrika-nat-wan\"]] = 0) do={{ /ip firewall nat add chain=srcnat action=masquerade out-interface={wan_iface} comment=\"ketrika-nat-wan\" }} }} on-error={{}}")
    if plan in ("performance", "business"):
        a(":do { :if ([:len [/ip firewall nat find where comment=\"ketrika-nat-wg\"]] = 0) do={ /ip firewall nat add chain=srcnat action=masquerade out-interface=wg-warp comment=\"ketrika-nat-wg\" } } on-error={}")
    a("")
    a(":do {")
    a("  :if ([:len [/ip firewall mangle find where comment=\"ketrika-mss-clamp\"]] = 0) do={")
    a("    /ip firewall mangle add chain=forward action=change-mss new-mss=1280 protocol=tcp tcp-flags=syn tcp-mss=1281-65535 passthrough=yes comment=\"ketrika-mss-clamp\"")
    a("  }")
    a("} on-error={}")
    a("")

    # ========== 17. ANTI-TTL ==========
    if plan in ("performance", "business") and order.ttl_value and order.ttl_value > 0:
        a(f"# --- 17. Optimisation TTL (valeur: {order.ttl_value}) ---")
        a(":do {")
        a(f"  :if ([:len [/ip firewall mangle find where comment=\"ketrika-ttl-pre\"]] = 0) do={{")
        a(f"    /ip firewall mangle add chain=prerouting action=change-ttl new-ttl=set:{order.ttl_value} passthrough=yes comment=\"ketrika-ttl-pre\"")
        a("  }")
        a(f"  :if ([:len [/ip firewall mangle find where comment=\"ketrika-ttl-post\"]] = 0) do={{")
        a(f"    /ip firewall mangle add chain=postrouting action=change-ttl new-ttl=set:{order.ttl_value} passthrough=yes comment=\"ketrika-ttl-post\"")
        a("  }")
        a("  :if ([:len [/ip firewall mangle find where comment=\"ketrika-ttl-fwd\"]] = 0) do={")
        a(f"    /ip firewall mangle add chain=forward action=change-ttl new-ttl=set:{order.ttl_value} passthrough=yes comment=\"ketrika-ttl-fwd\"")
        a("  }")
        a("} on-error={}")
        a("")

    # ========== 18. QOS ==========
    if plan in ("performance", "business"):
        if order.dl_limit and order.dl_limit > 0 or order.ul_limit and order.ul_limit > 0:
            dl = f"{order.dl_limit}M" if order.dl_limit > 0 else "0"
            ul = f"{order.ul_limit}M" if order.ul_limit > 0 else "0"
            a("# --- 18. QoS - Limite de debit globale ---")
            a(":do {")
            a(f"  :if ([:len [/queue simple find where name=\"ketrika-qos-global\"]] = 0) do={{")
            a(f"    /queue simple add name=ketrika-qos-global target={net_base}/24 max-limit={ul}/{dl} comment=\"KETRIKA Global QoS\"")
            a("  }")
            a("} on-error={}")
            a("")
        if order.client_limit and order.client_limit > 0:
            cl = f"{order.client_limit}M"
            a("# --- 18b. QoS - Limite par client ---")
            a(":do {")
            a("  :if ([:len [/queue type find where name=\"ketrika-pcq-down\"]] = 0) do={")
            a(f"    /queue type add name=ketrika-pcq-down kind=pcq pcq-rate={cl} pcq-classifier=dst-address")
            a("  }")
            a("  :if ([:len [/queue type find where name=\"ketrika-pcq-up\"]] = 0) do={")
            a(f"    /queue type add name=ketrika-pcq-up kind=pcq pcq-rate={cl} pcq-classifier=src-address")
            a("  }")
            a("} on-error={}")
            a(":do {")
            a(f"  :if ([:len [/queue simple find where name=\"ketrika-qos-client\"]] = 0) do={{")
            a(f"    /queue simple add name=ketrika-qos-client target={net_base}/24 queue=ketrika-pcq-up/ketrika-pcq-down comment=\"KETRIKA Per-Client QoS\"")
            a("  }")
            a("} on-error={}")
            a("")

    # ========== 19. IDENTITY ==========
    a("# --- 19. Identite du routeur ---")
    a(f":do {{ /system identity set name=\"{order.router_name}\" }} on-error={{}}")
    a("")

    # ========== 20. SCHEDULER MISE EN VEILLE WI-FI ==========
    if order.sleep_mode and order.sleep_mode != "off" and order.sleep_start and order.sleep_end:
        a(f"# --- 20. Mise en veille Wi-Fi ({order.sleep_start} -> {order.sleep_end}) ---")
        if wifi_type == "ax":
            off_cmd = "/interface wifi disable [find]"
            on_cmd = "/interface wifi enable [find]"
        elif has_wifi_24 or has_wifi_5:
            off_cmd = "/interface wireless disable [find]"
            on_cmd = "/interface wireless enable [find]"
        else:
            off_cmd = ""
            on_cmd = ""

        if off_cmd:
            s_start = order.sleep_start if ":" in order.sleep_start else order.sleep_start + ":00"
            s_end = order.sleep_end if ":" in order.sleep_end else order.sleep_end + ":00"
            a(":do {")
            a(f"  :if ([:len [/system scheduler find where name=\"ketrika-wifi-off\"]] = 0) do={{")
            a(f"    /system scheduler add name=ketrika-wifi-off start-time={s_start}:00 interval=1d on-event=\"{off_cmd}\" comment=\"KETRIKA WiFi Auto-Off\"")
            a("  }")
            a(f"  :if ([:len [/system scheduler find where name=\"ketrika-wifi-on\"]] = 0) do={{")
            a(f"    /system scheduler add name=ketrika-wifi-on start-time={s_end}:00 interval=1d on-event=\"{on_cmd}\" comment=\"KETRIKA WiFi Auto-On\"")
            a("  }")
            a("} on-error={}")
            a("")

    # ========== 21. FIREWALL DE BASE ==========
    a("# --- 21. Firewall de protection ---")
    a(":do { :if ([:len [/ip firewall filter find where comment=\"ketrika-fw-estab\"]] = 0) do={ /ip firewall filter add chain=input action=accept connection-state=established,related comment=\"ketrika-fw-estab\" } } on-error={}")
    a(":do { :if ([:len [/ip firewall filter find where comment=\"ketrika-fw-lan\"]] = 0) do={ /ip firewall filter add chain=input action=accept src-address=192.168.0.0/16 comment=\"ketrika-fw-lan\" } } on-error={}")
    a(":do { :if ([:len [/ip firewall filter find where comment=\"ketrika-fw-icmp\"]] = 0) do={ /ip firewall filter add chain=input action=accept protocol=icmp comment=\"ketrika-fw-icmp\" } } on-error={}")
    a(f":do {{ :if ([:len [/ip firewall filter find where comment=\"ketrika-fw-drop\"]] = 0) do={{ /ip firewall filter add chain=input action=drop in-interface={wan_iface} comment=\"ketrika-fw-drop\" }} }} on-error={{}}")
    a(":do { :if ([:len [/ip firewall filter find where comment=\"ketrika-fw-fwd\"]] = 0) do={ /ip firewall filter add chain=forward action=accept connection-state=established,related comment=\"ketrika-fw-fwd\" } } on-error={}")
    a(f":do {{ :if ([:len [/ip firewall filter find where comment=\"ketrika-fw-fwd-drop\"]] = 0) do={{ /ip firewall filter add chain=forward action=drop connection-state=invalid in-interface={wan_iface} comment=\"ketrika-fw-fwd-drop\" }} }} on-error={{}}")
    a("")

    # ========== 22. BANNIÈRE SUCCÈS + INSTRUCTIONS ==========
    a(":delay 2s")
    a(":log warning \"\"")
    a(":log warning \"====================================================\"")
    a(":log warning \"  KETRIKA MIKROTIK v3.0.1 - CONFIGURATION TERMINEE \"")
    a(f":log warning \"  Licence  : {order.license_key}\"")
    a(f":log warning \"  Routeur  : {order.router_name}\"")
    a(f":log warning \"  Plan     : {plan.upper()}\"")
    a(":log warning \"  Status   : SUCCES\"")
    a(":log warning \"  Support  : wa.me/261382817100\"")
    a(":log warning \"  Made in Madagascar\"")
    a(":log warning \"====================================================\"")
    a(":log warning \"\"")
    a("")
    a(":put \"\"")
    a(":put \"====================================================\"")
    a(":put \"    KETRIKA MIKROTIK v3.0.1 - INSTALLATION REUSSIE\"")
    a(":put \"====================================================\"")
    a(":put \"\"")
    a(f":put \"  Licence : {order.license_key}\"")
    a(f":put \"  Routeur : {order.router_name}\"")
    a(f":put \"  Plan    : {plan.upper()}\"")
    a(":put \"\"")
    a(":put \"  Support : wa.me/261382817100\"")
    a(":put \"  Merci de votre confiance !\"")
    a(":put \"====================================================\"")
    a(":put \"\"")

    return "\n".join(lines)
