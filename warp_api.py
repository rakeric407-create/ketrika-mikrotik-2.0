# -*- coding: utf-8 -*-
"""
KETRIKA MIKROTIK 301 - Generateur .rsc
Correction : country=etsi pour wifi AX (Madagascar non supporte)
"""

import random
import string
import base64
import os
from datetime import datetime


def _gen_wg_privkey():
    """Genere une cle privee WireGuard curve25519"""
    raw = bytearray(os.urandom(32))
    raw[0] &= 248
    raw[31] = (raw[31] & 127) | 64
    return base64.b64encode(bytes(raw)).decode()


CF_PUBKEY = "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo="
CF_ENDPOINT = "162.159.193.1"
CF_PORT = "2408"


def generate_rsc(order, model_info):
    plan = order.plan_type
    has24 = model_info.get("wifi_24ghz", False)
    has5 = model_info.get("wifi_5ghz", False)
    wtype = model_info.get("wifi_type")
    ports = model_info.get("ports", 5)
    wan = order.wan_interface or "ether1"
    gw = order.lan_gateway or "192.168.10.1"
    net = ".".join(gw.split(".")[:3]) + ".0"
    ps = order.dhcp_pool_start or "192.168.10.10"
    pe = order.dhcp_pool_end or "192.168.10.250"
    s2 = order.ssid_2g or "KETRIKA-WiFi"
    s5 = order.ssid_5g or (s2 + "-5G")
    wp = order.wifi_password or "ketrika2024"

    L = []
    a = L.append
    fn = f"ketrika_{order.license_key}.rsc"

    a("# KETRIKA MIKROTIK 301")
    a(f"# Licence : {order.license_key}")
    a(f"# Client  : {order.client_name}")
    a(f"# Plan    : {plan.upper()}")
    a(f"# Modele  : {model_info['name']}")
    a(f"# Routeur : {order.router_name}")
    a(f"# Date    : {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    a("")
    a(":log warning \"KETRIKA 301 : Demarrage...\"")
    a(":delay 1s")
    a("")

    # === FASTTRACK OFF ===
    a("# FastTrack OFF")
    a(":foreach i in=[/ip/firewall/filter/find where action=\"fasttrack-connection\"] do={")
    a("  :do { /ip/firewall/filter/set $i disabled=yes } on-error={}")
    a("}")
    a("")

    # === MAC SERVER ===
    a("# MAC Server")
    a(":do { /tool/mac-server/set allowed-interface-list=all } on-error={}")
    a(":do { /tool/mac-server/mac-winbox/set allowed-interface-list=all } on-error={}")
    a(":do { /tool/mac-server/ping/set enabled=yes } on-error={}")
    a("")

    # === SERVICES ===
    a("# Services")
    a(":do { /ip/service/set winbox port=8291 disabled=no } on-error={}")
    a(":do { /ip/service/set ssh port=22 disabled=no } on-error={}")
    for s in ["telnet", "ftp", "api", "api-ssl", "www", "www-ssl"]:
        a(f":do {{ /ip/service/disable {s} }} on-error={{}}")
    a("")

    # === BRIDGE ===
    a("# Bridge")
    a(":if ([:len [/interface/bridge/find where name=\"bridge\"]] = 0) do={")
    a("  /interface/bridge/add name=bridge")
    a("}")
    a("")

    # === PORTS AU BRIDGE ===
    a("# Ports Ethernet au bridge")
    for i in range(1, ports + 1):
        e = f"ether{i}"
        if e == wan:
            continue
        a(f":do {{")
        a(f"  :if ([:len [/interface/find where name=\"{e}\"]] > 0) do={{")
        a(f"    :if ([:len [/interface/bridge/port/find where interface=\"{e}\"]] = 0) do={{")
        a(f"      /interface/bridge/port/add bridge=bridge interface={e}")
        a(f"    }}")
        a(f"  }}")
        a(f"}} on-error={{}}")
    a("")

    # === IP ===
    a("# IP LAN")
    a(f":if ([:len [/ip/address/find where comment=\"KETRIKA\"]] = 0) do={{")
    a(f"  /ip/address/add address={gw}/24 interface=bridge network={net} comment=\"KETRIKA\"")
    a("}")
    a(":if ([:len [/ip/address/find where comment=\"BACKUP\"]] = 0) do={")
    a("  /ip/address/add address=192.168.88.1/24 interface=bridge network=192.168.88.0 comment=\"BACKUP\"")
    a("}")
    a("")

    # === DHCP ===
    a("# DHCP")
    a(f":if ([:len [/ip/pool/find where name=\"pool1\"]] = 0) do={{")
    a(f"  /ip/pool/add name=pool1 ranges={ps}-{pe}")
    a("}")
    a(":if ([:len [/ip/dhcp-server/find where name=\"dhcp1\"]] = 0) do={")
    a("  /ip/dhcp-server/add name=dhcp1 interface=bridge address-pool=pool1 disabled=no lease-time=1d")
    a("}")
    a(f":if ([:len [/ip/dhcp-server/network/find where gateway=\"{gw}\"]] = 0) do={{")
    a(f"  /ip/dhcp-server/network/add address={net}/24 gateway={gw} dns-server=1.1.1.1,8.8.8.8")
    a("}")
    a("/ip/dns/set servers=1.1.1.1,8.8.8.8 allow-remote-requests=yes")
    a("")

    # === DHCP CLIENT WAN ===
    a("# DHCP Client WAN")
    a(f":if ([:len [/ip/dhcp-client/find where interface=\"{wan}\"]] = 0) do={{")
    a(f"  /ip/dhcp-client/add interface={wan} disabled=no add-default-route=yes use-peer-dns=no")
    a("}")
    a("")

    # === NAT PRIORITAIRE ===
    a("# NAT Masquerade WAN")
    a(f":if ([:len [/ip/firewall/nat/find where comment=\"K-NAT\"]] = 0) do={{")
    a(f"  /ip/firewall/nat/add chain=srcnat action=masquerade out-interface={wan} comment=\"K-NAT\"")
    a("}")
    a("")

    # === MAC SPOOF ===
    if plan in ("performance", "business") and order.mac_spoof and order.mac_address:
        a("# MAC Spoof")
        a(f":do {{ /interface/ethernet/set [/interface/ethernet/find where name=\"{wan}\"] mac-address={order.mac_address} }} on-error={{}}")
        a("")

    # ============================================================
    # WI-FI - CORRECTION country=etsi (Madagascar non supporte pour AX)
    # ============================================================
    if has24 or has5:
        a("# =========================================")
        a("# WI-FI CONFIGURATION")
        a("# =========================================")
        a("")

        if wtype == "ax":
            a("# Wi-Fi 6 AX (/interface/wifi) - country=etsi")
            a("")
            a("# Nettoyage anciens profils")
            a(":do { /interface/wifi/security/remove [/interface/wifi/security/find where name=\"ksec\"] } on-error={}")
            a(":do { /interface/wifi/configuration/remove [/interface/wifi/configuration/find where name=\"kcfg2\"] } on-error={}")
            a(":do { /interface/wifi/configuration/remove [/interface/wifi/configuration/find where name=\"kcfg5\"] } on-error={}")
            a("")
            a(f"/interface/wifi/security/add name=ksec authentication-types=wpa2-psk,wpa3-psk passphrase=\"{wp}\"")
            # CORRECTION : country=etsi au lieu de Madagascar
            a(f"/interface/wifi/configuration/add name=kcfg2 ssid=\"{s2}\" security=ksec country=etsi mode=ap")
            if has5:
                a(f"/interface/wifi/configuration/add name=kcfg5 ssid=\"{s5}\" security=ksec country=etsi mode=ap")
            a("")
            a("# Application avec compteur")
            a(":local idx 0")
            a(":foreach w in=[/interface/wifi/find] do={")
            a("  :if ($idx = 0) do={")
            a("    :do { /interface/wifi/set $w configuration=kcfg2 disabled=no } on-error={}")
            a("  }")
            if has5:
                a("  :if ($idx = 1) do={")
                a("    :do { /interface/wifi/set $w configuration=kcfg5 disabled=no } on-error={}")
                a("  }")
            a("  :set idx ($idx + 1)")
            a("}")
            a("")
            a(":do { /interface/wifi/enable [/interface/wifi/find] } on-error={}")
            a("")
            a("# Bridge Wi-Fi")
            a(":foreach w in=[/interface/wifi/find] do={")
            a("  :local wn [/interface/wifi/get $w name]")
            a("  :if ([:len [/interface/bridge/port/find where interface=$wn]] = 0) do={")
            a("    :do { /interface/bridge/port/add bridge=bridge interface=$wn } on-error={}")
            a("  }")
            a("}")
        else:
            a("# Wi-Fi AC/N (/interface/wireless)")
            a("")
            a("# Nettoyage ancien profil securite")
            a(":do { /interface/wireless/security-profiles/remove [/interface/wireless/security-profiles/find where name=\"ksec\"] } on-error={}")
            a("")
            a(f"/interface/wireless/security-profiles/add name=ksec mode=dynamic-keys authentication-types=wpa2-psk wpa2-pre-shared-key=\"{wp}\"")
            a("")
            a("# Application avec compteur (country omis = no_country_set par defaut)")
            a(":local idx 0")
            a(":foreach w in=[/interface/wireless/find] do={")
            a("  :if ($idx = 0) do={")
            a(f"    :do {{ /interface/wireless/set $w mode=ap-bridge ssid=\"{s2}\" security-profile=ksec band=2ghz-b/g/n channel-width=20/40mhz-XX frequency=auto disabled=no }} on-error={{}}")
            a("  }")
            if has5:
                a("  :if ($idx = 1) do={")
                a(f"    :do {{ /interface/wireless/set $w mode=ap-bridge ssid=\"{s5}\" security-profile=ksec band=5ghz-a/n/ac channel-width=20/40/80mhz-XXXX frequency=auto disabled=no }} on-error={{}}")
                a("  }")
            a("  :set idx ($idx + 1)")
            a("}")
            a("")
            a(":do { /interface/wireless/enable [/interface/wireless/find] } on-error={}")
            a("")
            a("# Bridge Wi-Fi")
            a(":foreach w in=[/interface/wireless/find] do={")
            a("  :local wn [/interface/wireless/get $w name]")
            a("  :if ([:len [/interface/bridge/port/find where interface=$wn]] = 0) do={")
            a("    :do { /interface/bridge/port/add bridge=bridge interface=$wn } on-error={}")
            a("  }")
            a("}")

        a("")
        a(f":log warning \"KETRIKA : Wi-Fi active SSID={s2}\"")
        a("")

    # === WIREGUARD WARP (plan 2+) ===
    if plan in ("performance", "business"):
        privkey = _gen_wg_privkey()

        a("# =========================================")
        a("# WIREGUARD WARP")
        a("# =========================================")
        a("")
        a("# Nettoyage complet")
        a(":do { /ip/firewall/mangle/remove [/ip/firewall/mangle/find where comment~\"KW-\"] } on-error={}")
        a(":do { /ip/route/remove [/ip/route/find where comment=\"KW-ROUTE\"] } on-error={}")
        a(":do { /ip/firewall/nat/remove [/ip/firewall/nat/find where comment=\"KW-NAT\"] } on-error={}")
        a(":do { /ip/address/remove [/ip/address/find where comment=\"KW-IP\"] } on-error={}")
        a(":do { /interface/wireguard/peers/remove [/interface/wireguard/peers/find where comment=\"KW-PEER\"] } on-error={}")
        a(":do { /interface/wireguard/remove [/interface/wireguard/find where name=\"wg-warp\"] } on-error={}")
        a("")
        a(f"/interface/wireguard/add name=wg-warp listen-port=13231 mtu=1280 private-key=\"{privkey}\"")
        a("")
        a("/ip/address/add address=172.16.0.2/32 interface=wg-warp network=172.16.0.2 comment=\"KW-IP\"")
        a("")
        a(f"/interface/wireguard/peers/add interface=wg-warp public-key=\"{CF_PUBKEY}\" endpoint-address={CF_ENDPOINT} endpoint-port={CF_PORT} allowed-address=0.0.0.0/0,::/0 persistent-keepalive=25s comment=\"KW-PEER\"")
        a("")
        a("/ip/firewall/nat/add chain=srcnat action=masquerade out-interface=wg-warp comment=\"KW-NAT\"")
        a("")
        a(":if ([:len [/routing/table/find where name=\"to-warp\"]] = 0) do={")
        a("  /routing/table/add name=to-warp fib")
        a("}")
        a("")
        a("/ip/route/add dst-address=0.0.0.0/0 gateway=wg-warp routing-table=to-warp comment=\"KW-ROUTE\"")
        a("")
        a(":foreach addr in={\"192.168.0.0/16\";\"10.0.0.0/8\";\"172.16.0.0/12\"} do={")
        a("  :if ([:len [/ip/firewall/address-list/find where list=\"local-net\" and address=$addr]] = 0) do={")
        a("    /ip/firewall/address-list/add list=local-net address=$addr")
        a("  }")
        a("}")
        a("")
        a(f"/ip/firewall/mangle/add chain=prerouting action=accept protocol=tcp dst-port=8291 src-address={net}/24 comment=\"KW-EXCL\"")
        a(f"/ip/firewall/mangle/add chain=prerouting action=accept src-address={net}/24 dst-address-list=local-net comment=\"KW-LOCAL\"")
        a(f"/ip/firewall/mangle/add chain=prerouting action=mark-routing new-routing-mark=to-warp src-address={net}/24 dst-address-list=!local-net connection-state=new passthrough=no comment=\"KW-MARK\"")
        a("")
        a(":log warning \"KETRIKA : WireGuard WARP configure\"")
        a("")

    # === MSS CLAMPING ===
    a("# MSS Clamping")
    a(":if ([:len [/ip/firewall/mangle/find where comment=\"K-MSS\"]] = 0) do={")
    a("  /ip/firewall/mangle/add chain=forward action=change-mss new-mss=1280 protocol=tcp tcp-flags=syn tcp-mss=1281-65535 passthrough=yes comment=\"K-MSS\"")
    a("}")
    a("")

    # === TTL ===
    if plan in ("performance", "business") and order.ttl_value and order.ttl_value > 0:
        a(f"# TTL {order.ttl_value}")
        a(":do { /ip/firewall/mangle/remove [/ip/firewall/mangle/find where comment~\"K-TTL\"] } on-error={}")
        for c, t in [("prerouting", "PRE"), ("postrouting", "POST"), ("forward", "FWD")]:
            a(f"/ip/firewall/mangle/add chain={c} action=change-ttl new-ttl=set:{order.ttl_value} passthrough=yes comment=\"K-TTL-{t}\"")
        a("")

    # === QOS ===
    if plan in ("performance", "business"):
        if (order.dl_limit and order.dl_limit > 0) or (order.ul_limit and order.ul_limit > 0):
            dl = f"{order.dl_limit}M" if order.dl_limit > 0 else "0"
            ul = f"{order.ul_limit}M" if order.ul_limit > 0 else "0"
            a("# QoS")
            a(":do { /queue/simple/remove [/queue/simple/find where comment=\"KETRIKA\"] } on-error={}")
            a(f"/queue/simple/add name=ketrika-qos target={net}/24 max-limit={ul}/{dl} comment=\"KETRIKA\"")
            a("")

    # === HOTSPOT ===
    if plan == "business" and order.hotspot_tickets_count and order.hotspot_tickets_count > 0:
        a("# Hotspot")
        a(f":if ([:len [/ip/hotspot/profile/find where name=\"hsprof\"]] = 0) do={{")
        a(f"  /ip/hotspot/profile/add name=hsprof hotspot-address={gw} dns-name=login.ketrika.mg html-directory=hotspot login-by=http-chap,http-pap")
        a("}")
        for pn, to, rl in [("h1h","1h","5M/10M"),("h1d","1d","5M/10M"),("h1w","1w","5M/10M"),("h1m","4w2d","10M/20M")]:
            a(f":if ([:len [/ip/hotspot/user/profile/find where name=\"{pn}\"]] = 0) do={{")
            a(f"  /ip/hotspot/user/profile/add name={pn} session-timeout={to} shared-users=1 rate-limit={rl}")
            a("}")
        a(":if ([:len [/ip/hotspot/find where name=\"hs1\"]] = 0) do={")
        a("  /ip/hotspot/add name=hs1 interface=bridge address-pool=pool1 profile=hsprof disabled=no")
        a("}")
        a("")
        for _ in range(min(order.hotspot_tickets_count, 200)):
            u = "T" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
            p = "".join(random.choices(string.digits, k=6))
            a(f":if ([:len [/ip/hotspot/user/find where name=\"{u}\"]] = 0) do={{")
            a(f"  /ip/hotspot/user/add name={u} password={p} profile=h1d server=hs1")
            a("}")
        a("")

    # === IDENTITY ===
    a(f"/system/identity/set name=\"{order.router_name}\"")
    a("")

    # === VEILLE WI-FI ===
    if order.sleep_mode and order.sleep_mode != "off" and order.sleep_start and order.sleep_end:
        if wtype == "ax":
            off = "/interface/wifi/disable [find]"
            on = "/interface/wifi/enable [find]"
        elif has24 or has5:
            off = "/interface/wireless/disable [find]"
            on = "/interface/wireless/enable [find]"
        else:
            off = on = ""
        if off:
            ss = order.sleep_start if ":" in order.sleep_start else order.sleep_start + ":00"
            se = order.sleep_end if ":" in order.sleep_end else order.sleep_end + ":00"
            a("# Veille Wi-Fi")
            a(":do { /system/scheduler/remove [/system/scheduler/find where name~\"kwifi\"] } on-error={}")
            a(f"/system/scheduler/add name=kwifi-off start-time={ss}:00 interval=1d on-event=\"{off}\"")
            a(f"/system/scheduler/add name=kwifi-on start-time={se}:00 interval=1d on-event=\"{on}\"")
            a("")

    # === FIREWALL ===
    a("# Firewall")
    for ch, act, par, tag in [
        ("input","accept","connection-state=established,related","est"),
        ("input","accept","src-address=192.168.0.0/16","lan"),
        ("input","accept","protocol=icmp","icmp"),
        ("input","drop",f"in-interface={wan}","drp"),
        ("forward","accept","connection-state=established,related","fwd"),
        ("forward","drop",f"connection-state=invalid in-interface={wan}","fdi"),
    ]:
        a(f":if ([:len [/ip/firewall/filter/find where comment=\"K-{tag}\"]] = 0) do={{")
        a(f"  /ip/firewall/filter/add chain={ch} action={act} {par} comment=\"K-{tag}\"")
        a("}")
    a("")

    # === SUCCES ===
    a(":delay 2s")
    a(":put \"\"")
    a(":put \"================================================\"")
    a(":put \"  KETRIKA MIKROTIK 301 - SUCCES\"")
    a(":put \"================================================\"")
    a(f":put \"  Routeur : {order.router_name}\"")
    if has24:
        a(f":put \"  Wi-Fi   : {s2}\"")
        a(f":put \"  Mdp     : {wp}\"")
    a(f":put \"  IP      : {gw}\"")
    if plan in ("performance", "business"):
        a(":put \"  WARP    : actif\"")
    a(":put \"  Support : wa.me/261382817100\"")
    a(":put \"================================================\"")
    a(":log warning \"KETRIKA 301 : Configuration terminee\"")

    return "\n".join(L)


def generate_tutorial_txt(order, filename):
    plan = order.plan_type
    L = [
        "================================================",
        "  KETRIKA MIKROTIK 301",
        "  GUIDE D INSTALLATION",
        "================================================",
        "",
        f"  Licence : {order.license_key}",
        f"  Client  : {order.client_name}",
        f"  Plan    : {plan.upper()}",
        "",
        "  ETAPE 1 : Ouvrir Winbox",
        "  ETAPE 2 : Cliquer sur Files",
        f"  ETAPE 3 : Glisser {filename}",
        "  ETAPE 4 : Ouvrir New Terminal",
        "  ETAPE 5 : Coller la commande :",
        "",
        f"  /import file-name={filename}",
        "",
        "  VOS IDENTIFIANTS :",
        f"  Routeur : {order.router_name}",
        f"  IP      : {order.lan_gateway}",
    ]
    if order.ssid_2g:
        L.append(f"  Wi-Fi 2.4 : {order.ssid_2g}")
    if order.ssid_5g:
        L.append(f"  Wi-Fi 5   : {order.ssid_5g}")
    if order.wifi_password:
        L.append(f"  Mdp Wi-Fi : {order.wifi_password}")
    L.extend([
        "",
        "  Support : wa.me/261382817100",
        "  KETRIKA MIKROTIK Madagascar",
        "================================================",
    ])
    return "\n".join(L)
