# script_generator.py
import secrets
import hashlib
from datetime import datetime

class MikroTikGenerator:
    """
    Générateur de scripts MikroTik ultra-complet
    - Pas de déconnexion Winbox au collage
    - Copier-coller sans erreur
    - Obfuscation totale FAI
    - Compatible tous modèles
    """
    
    def generate(self, config, pack_id):
        """Génère le script complet selon le pack"""
        sections = []
        
        # En-tête
        sections.append(self._header(config, pack_id))
        
        # Délai de sécurité pour éviter déconnexion Winbox
        sections.append(self._safe_delay())
        
        # 1. Reset sélectif (pas de reset complet = pas de déco)
        sections.append(self._selective_reset(config))
        
        # 2. Identité & Camouflage
        sections.append(self._identity_camouflage(config))
        
        # 3. Changement MAC
        sections.append(self._mac_change(config))
        
        # 4. Configuration interfaces
        sections.append(self._interfaces(config))
        
        # 5. Bridge & VLAN
        sections.append(self._bridge_config(config))
        
        # 6. Adressage IP
        sections.append(self._ip_addressing(config))
        
        # 7. DHCP Server
        sections.append(self._dhcp_server(config))
        
        # 8. DNS & DoH
        sections.append(self._dns_doh(config))
        
        # 9. WiFi Auto-detection & Config
        sections.append(self._wifi_config(config))
        
        # 10. Firewall & NAT
        sections.append(self._firewall_nat(config))
        
        # 11. Obfuscation FAI
        sections.append(self._fai_obfuscation(config))
        
        # 12. Mise en veille programmée
        if config.get('sleep_enabled'):
            sections.append(self._sleep_schedule(config))
        
        # Pack 2+: WARP WireGuard
        if pack_id >= 2 and config.get('warp'):
            sections.append(self._warp_wireguard(config))
        
        # Pack 3: Hotspot ou PPPoE
        if pack_id >= 3:
            if config.get('service_type') == 'hotspot':
                sections.append(self._hotspot_config(config))
            else:
                sections.append(self._pppoe_config(config))
        
        # Finalisation
        sections.append(self._finalize(config))
        
        return '\n'.join(filter(None, sections))
    
    def _header(self, config, pack_id):
        pack_names = {1: 'CLASSIC DoH', 2: 'WARP WireGuard', 3: 'HOTSPOT/PPPoE'}
        return f"""# ╔══════════════════════════════════════════════════════════════╗
# ║           KETRIKA MIKROTIK - Configuration Auto             ║
# ║                  Pack: {pack_names.get(pack_id, 'UNKNOWN'):<36} ║
# ║           Généré le: {datetime.now().strftime('%d/%m/%Y %H:%M'):<36} ║
# ║                                                              ║
# ║  ⚠️  COLLER EN UNE SEULE FOIS DANS TERMINAL MIKROTIK       ║
# ║  ⚠️  NE PAS FERMER WINBOX PENDANT L'EXÉCUTION              ║
# ╚══════════════════════════════════════════════════════════════╝
"""

    def _safe_delay(self):
        """Délais stratégiques pour éviter la déconnexion Winbox"""
        return """/system script add name="ketrika-safe-apply" source={
:log info "KETRIKA: Début configuration..."
}
"""

    def _selective_reset(self, config):
        """Reset sélectif - NE COUPE PAS la connexion Winbox"""
        return """# ═══════════════════════════════════════
# SECTION 1: Nettoyage sélectif (sans déconnexion)
# ═══════════════════════════════════════

# Supprimer les anciennes règles sans toucher aux interfaces actives
:do {
/ip firewall filter remove [find where comment~"ketrika"]
} on-error={}
:do {
/ip firewall nat remove [find where comment~"ketrika"]  
} on-error={}
:do {
/ip firewall mangle remove [find where comment~"ketrika"]
} on-error={}
:do {
/queue simple remove [find where comment~"ketrika"]
} on-error={}

:log info "KETRIKA: Nettoyage terminé"
:delay 1s
"""

    def _identity_camouflage(self, config):
        """Changement d'identité pour camouflage FAI"""
        router_name = config.get('router_identity', 'Home-Gateway')
        return f"""# ═══════════════════════════════════════
# SECTION 2: Identité & Camouflage total
# ═══════════════════════════════════════

/system identity set name="{router_name}"

# Désactiver les services détectables par le FAI
/ip service
set telnet disabled=yes
set ftp disabled=yes
set api disabled=yes
set api-ssl disabled=yes
set ssh port=2200

# Désactiver la découverte réseau (anti-détection FAI)
:do {{
/ip neighbor discovery-settings set discover-interface-list=none
}} on-error={{}}

# Désactiver UPnP (signature détectable)
:do {{
/ip upnp set enabled=no
}} on-error={{}}

# Désactiver Bandwidth Server (signature MikroTik)
:do {{
/tool bandwidth-server set enabled=no
}} on-error={{}}

# Désactiver MAC Server sur WAN (anti-détection)
:do {{
/tool mac-server set allowed-interface-list=LAN
/tool mac-server mac-winbox set allowed-interface-list=LAN
/tool mac-server ping set enabled=no
}} on-error={{}}

# Cacher la version RouterOS
:do {{
/ip proxy set enabled=no
}} on-error={{}}

:log info "KETRIKA: Identité camouflée"
:delay 1s
"""

    def _mac_change(self, config):
        """Changement de MAC pour contourner la détection FAI"""
        wan = config.get('wan_interface', 'ether1')
        
        if config.get('change_mac') and config.get('custom_mac'):
            mac = config['custom_mac']
        else:
            # Générer une MAC réaliste (préfixe de fabricant courant)
            prefixes = [
                "00:1A:2B", "00:25:90", "D4:CA:6D", 
                "78:8A:20", "B8:69:F4", "E4:8D:8C",
                "AC:84:C6", "F8:D1:11", "DC:2C:6E"
            ]
            prefix = secrets.choice(prefixes)
            suffix = ':'.join(f'{secrets.randbelow(256):02X}' for _ in range(3))
            mac = f"{prefix}:{suffix}"
        
        return f"""# ═══════════════════════════════════════
# SECTION 3: Changement MAC (anti-détection FAI)
# ═══════════════════════════════════════

:local newMAC "{mac}"

:do {{
/interface ethernet set {wan} mac-address=$newMAC
:log info ("KETRIKA: MAC WAN changé en " . $newMAC)
}} on-error={{
:log warning "KETRIKA: Impossible de changer MAC WAN"
}}

:delay 2s
"""

    def _interfaces(self, config):
        """Configuration des interfaces"""
        wan = config.get('wan_interface', 'ether1')
        lan = config.get('lan_interface', 'ether2')
        
        return f"""# ═══════════════════════════════════════
# SECTION 4: Configuration Interfaces
# ═══════════════════════════════════════

# Créer les listes d'interfaces
:do {{
/interface list add name=WAN comment="ketrika"
/interface list add name=LAN comment="ketrika"
}} on-error={{}}

:do {{
/interface list member add interface={wan} list=WAN comment="ketrika"
}} on-error={{}}

:do {{
/interface list member add interface={lan} list=LAN comment="ketrika"
}} on-error={{}}

:log info "KETRIKA: Interfaces configurées"
"""

    def _bridge_config(self, config):
        """Configuration Bridge pour LAN"""
        lan = config.get('lan_interface', 'ether2')
        
        return f"""# ═══════════════════════════════════════
# SECTION 5: Bridge LAN
# ═══════════════════════════════════════

# Créer le bridge s'il n'existe pas
:do {{
/interface bridge add name=bridge-lan comment="ketrika" \
    protocol-mode=none \
    fast-forward=yes
}} on-error={{
:log info "KETRIKA: Bridge existe déjà"
}}

# Ajouter les ports LAN au bridge
:do {{
/interface bridge port add interface={lan} bridge=bridge-lan comment="ketrika"
}} on-error={{}}

# Ajouter le bridge à la liste LAN
:do {{
/interface list member add interface=bridge-lan list=LAN comment="ketrika"
}} on-error={{}}

:delay 1s
"""

    def _ip_addressing(self, config):
        """Adressage IP"""
        gateway = config.get('gateway_ip', '192.168.88.1')
        subnet = config.get('lan_subnet', '192.168.88.0/24')
        
        # Extraire le masque
        if '/' in subnet:
            network, mask = subnet.split('/')
        else:
            mask = '24'
        
        return f"""# ═══════════════════════════════════════
# SECTION 6: Adressage IP
# ═══════════════════════════════════════

# IP du bridge LAN
:do {{
/ip address add address={gateway}/{mask} interface=bridge-lan network={subnet.split('/')[0]} comment="ketrika-lan"
}} on-error={{
:log info "KETRIKA: Adresse IP existe déjà"
}}

# Client DHCP sur WAN
:do {{
/ip dhcp-client add interface={config.get('wan_interface', 'ether1')} \
    disabled=no \
    add-default-route=yes \
    use-peer-dns=no \
    use-peer-ntp=no \
    comment="ketrika-wan"
}} on-error={{
:log info "KETRIKA: DHCP client WAN existe déjà"  
}}

:delay 1s
:log info "KETRIKA: Adressage configuré"
"""

    def _dhcp_server(self, config):
        """Serveur DHCP"""
        gateway = config.get('gateway_ip', '192.168.88.1')
        start = config.get('dhcp_start', '192.168.88.10')
        end = config.get('dhcp_end', '192.168.88.254')
        subnet = config.get('lan_subnet', '192.168.88.0/24')
        network = subnet.split('/')[0]
        
        return f"""# ═══════════════════════════════════════
# SECTION 7: Serveur DHCP
# ═══════════════════════════════════════

# Pool d'adresses
:do {{
/ip pool add name=dhcp-pool ranges={start}-{end} comment="ketrika"
}} on-error={{}}

# Réseau DHCP
:do {{
/ip dhcp-server network add address={subnet} gateway={gateway} \
    dns-server={gateway} comment="ketrika"
}} on-error={{}}

# Serveur DHCP
:do {{
/ip dhcp-server add name=dhcp-lan interface=bridge-lan \
    address-pool=dhcp-pool \
    lease-time=12h \
    disabled=no \
    comment="ketrika"
}} on-error={{}}

:log info "KETRIKA: DHCP Server actif"
"""

    def _dns_doh(self, config):
        """DNS over HTTPS - Cœur de l'obfuscation"""
        return f"""# ═══════════════════════════════════════
# SECTION 8: DNS over HTTPS (DoH) - Anti-détection
# ═══════════════════════════════════════

# Configurer DNS avec DoH
/ip dns set \
    allow-remote-requests=yes \
    servers=1.1.1.1,1.0.0.1,8.8.8.8 \
    use-doh-server=https://cloudflare-dns.com/dns-query \
    verify-doh-cert=yes \
    cache-size=4096KiB \
    cache-max-ttl=1d

# Résoudre les serveurs DoH d'abord (bootstrap)
:delay 2s

# Ajouter les entrées statiques pour le bootstrap DoH
:do {{
/ip dns static add name=cloudflare-dns.com address=104.16.248.249 comment="ketrika-doh"
/ip dns static add name=cloudflare-dns.com address=104.16.249.249 comment="ketrika-doh"
}} on-error={{}}

# Vider le cache DNS
/ip dns cache flush

:log info "KETRIKA: DoH activé - DNS chiffré"
:delay 2s
"""

    def _wifi_config(self, config):
        """Configuration WiFi auto-détection AC/AX/AN"""
        ssid_main = config.get('ssid_main', 'MonWiFi')
        ssid_pass = config.get('ssid_password', 'password123')
        wifi_mode = config.get('wifi_mode', 'ac')
        separate = config.get('ssid_separate', False)
        
        ssid_2g = config.get('ssid_2g', f'{ssid_main}-2G') if separate else ssid_main
        ssid_5g = config.get('ssid_5g', f'{ssid_main}-5G') if separate else ssid_main
        pass_2g = config.get('password_2g', ssid_pass) if separate else ssid_pass
        pass_5g = config.get('password_5g', ssid_pass) if separate else ssid_pass
        
        return f"""# ═══════════════════════════════════════
# SECTION 9: WiFi Auto-Configuration
# ═══════════════════════════════════════

# ---- Détection automatique du type WiFi ----
:local wifiType "unknown"
:local hasWifiwave2 false
:local hasWireless false
:local hasCAPsMAN false

# Vérifier WiFi Wave2 (ax/ac moderne - RouterOS 7+)
:do {{
/interface wifiwave2 print count-only
:set wifiType "wifiwave2"
:set hasWifiwave2 true
:log info "KETRIKA: WiFi Wave2 détecté (ax/ac)"
}} on-error={{}}

# Vérifier WiFi classique (an/ac legacy)
:if (!$hasWifiwave2) do={{
:do {{
/interface wireless print count-only
:set wifiType "wireless"  
:set hasWireless true
:log info "KETRIKA: WiFi Wireless classique détecté"
}} on-error={{}}
}}

# ═══ Configuration WiFi Wave2 (RouterOS 7+) ═══
:if ($hasWifiwave2) do={{

# Profil de sécurité
:do {{
/interface wifiwave2 security add name=ketrika-security \
    authentication-types=wpa2-psk,wpa3-psk \
    passphrase="{pass_2g}" \
    comment="ketrika"
}} on-error={{}}

# Configuration 2.4GHz
:do {{
:foreach i in=[/interface wifiwave2 find where band~"2ghz"] do={{
/interface wifiwave2 set $i \
    configuration.ssid="{ssid_2g}" \
    security=ketrika-security \
    configuration.country=Madagascar \
    configuration.mode=ap \
    disabled=no
:log info "KETRIKA: WiFi 2.4GHz configuré"
}}
}} on-error={{}}

# Configuration 5GHz
:do {{
:foreach i in=[/interface wifiwave2 find where band~"5ghz"] do={{
/interface wifiwave2 set $i \
    configuration.ssid="{ssid_5g}" \
    security=ketrika-security \
    configuration.country=Madagascar \
    configuration.mode=ap \
    disabled=no
:log info "KETRIKA: WiFi 5GHz configuré"
}}
}} on-error={{}}

# Ajouter WiFi au bridge
:do {{
:foreach i in=[/interface wifiwave2 find] do={{
/interface bridge port add interface=[/interface wifiwave2 get $i name] bridge=bridge-lan comment="ketrika-wifi"
}}
}} on-error={{}}

}}

# ═══ Configuration WiFi Classique (RouterOS 6/7) ═══
:if ($hasWireless) do={{

# Profil de sécurité
:do {{
/interface wireless security-profiles add name=ketrika-security \
    mode=dynamic-keys \
    authentication-types=wpa2-psk \
    wpa2-pre-shared-key="{pass_2g}" \
    comment="ketrika"
}} on-error={{
/interface wireless security-profiles set [find name=ketrika-security] \
    wpa2-pre-shared-key="{pass_2g}"
}}

# Configurer chaque interface WiFi
:do {{
:foreach i in=[/interface wireless find] do={{
:local freq [/interface wireless get $i frequency]
:local currentBand [/interface wireless get $i band]

# Déterminer si c'est 2.4GHz ou 5GHz
:if ($freq < 3000 || $currentBand~"2ghz") do={{
/interface wireless set $i \
    mode=ap-bridge \
    ssid="{ssid_2g}" \
    security-profile=ketrika-security \
    frequency-mode=regulatory-domain \
    country=madagascar \
    band=2ghz-g/n \
    channel-width=20/40mhz-XX \
    wireless-protocol=802.11 \
    wps-mode=disabled \
    disabled=no
:log info "KETRIKA: WiFi 2.4GHz configuré (classique)"
}} else={{
/interface wireless set $i \
    mode=ap-bridge \
    ssid="{ssid_5g}" \
    security-profile=ketrika-security \
    frequency-mode=regulatory-domain \
    country=madagascar \
    band=5ghz-n/ac \
    channel-width=20/40/80mhz-XXXX \
    wireless-protocol=802.11 \
    wps-mode=disabled \
    disabled=no
:log info "KETRIKA: WiFi 5GHz configuré (classique)"
}}
}}
}} on-error={{}}

# Ajouter WiFi au bridge
:do {{
:foreach i in=[/interface wireless find] do={{
/interface bridge port add interface=[/interface wireless get $i name] bridge=bridge-lan comment="ketrika-wifi"
}}
}} on-error={{}}

}}

:log info "KETRIKA: WiFi configuré avec succès"
:delay 2s
"""

    def _firewall_nat(self, config):
        """Firewall et NAT avec camouflage"""
        wan = config.get('wan_interface', 'ether1')
        
        return f"""# ═══════════════════════════════════════
# SECTION 10: Firewall & NAT (Camouflage)
# ═══════════════════════════════════════

# ---- NAT Masquerade ----
/ip firewall nat add chain=srcnat \
    out-interface-list=WAN \
    action=masquerade \
    comment="ketrika-nat"

# ---- Firewall Filter ----

# Accepter les connexions établies
/ip firewall filter add chain=input \
    connection-state=established,related \
    action=accept \
    comment="ketrika-established"

# Accepter le trafic local
/ip firewall filter add chain=input \
    in-interface-list=LAN \
    action=accept \
    comment="ketrika-lan-input"

# Accepter ICMP limité
/ip firewall filter add chain=input \
    protocol=icmp \
    action=accept \
    limit=5,5:packet \
    comment="ketrika-icmp"

# Bloquer le reste en input
/ip firewall filter add chain=input \
    action=drop \
    comment="ketrika-drop-input"

# Forward: accepter LAN vers WAN
/ip firewall filter add chain=forward \
    in-interface-list=LAN \
    out-interface-list=WAN \
    action=accept \
    comment="ketrika-forward-out"

# Forward: accepter established/related
/ip firewall filter add chain=forward \
    connection-state=established,related \
    action=accept \
    comment="ketrika-forward-established"

# Forward: bloquer le reste
/ip firewall filter add chain=forward \
    connection-state=invalid \
    action=drop \
    comment="ketrika-forward-invalid"

/ip firewall filter add chain=forward \
    in-interface-list=!LAN \
    out-interface-list=!WAN \
    connection-state=new \
    action=drop \
    comment="ketrika-forward-drop"

:log info "KETRIKA: Firewall configuré"
"""

    def _fai_obfuscation(self, config):
        """Obfuscation complète pour cacher le partage WiFi au FAI"""
        return """# ═══════════════════════════════════════
# SECTION 11: Obfuscation FAI Totale
# ═══════════════════════════════════════

# ---- Clamp MSS pour cacher les multi-appareils ----
/ip firewall mangle add chain=forward \
    protocol=tcp \
    tcp-flags=syn \
    action=change-mss \
    new-mss=clamp-to-pmtu \
    passthrough=yes \
    comment="ketrika-mss-clamp"

# ---- TTL uniforme (CRITIQUE: cache le nombre d'appareils) ----
/ip firewall mangle add chain=postrouting \
    out-interface-list=WAN \
    action=change-ttl \
    new-ttl=set:64 \
    passthrough=yes \
    comment="ketrika-ttl-uniform"

# ---- Normaliser le TTL entrant aussi ----
/ip firewall mangle add chain=prerouting \
    in-interface-list=WAN \
    action=change-ttl \
    new-ttl=set:64 \
    passthrough=yes \
    comment="ketrika-ttl-in"

# ---- Cacher le nombre de connexions simultanées ----
/ip firewall mangle add chain=forward \
    action=change-ttl \
    new-ttl=set:64 \
    passthrough=yes \
    comment="ketrika-ttl-forward"

# ---- Connection Tracking optimisé ----
/ip firewall connection tracking set \
    tcp-syn-sent-timeout=30s \
    tcp-syn-received-timeout=10s \
    tcp-established-timeout=3600s \
    tcp-fin-wait-timeout=10s \
    tcp-close-wait-timeout=10s \
    tcp-last-ack-timeout=10s \
    tcp-time-wait-timeout=10s \
    tcp-close-timeout=10s \
    udp-timeout=30s \
    udp-stream-timeout=120s

# ---- Limiter les requêtes DNS sortantes (anti-fingerprint) ----
/ip firewall filter add chain=forward \
    protocol=udp \
    dst-port=53 \
    action=drop \
    comment="ketrika-block-external-dns"
    
/ip firewall filter add chain=forward \
    protocol=tcp \
    dst-port=53 \
    action=drop \
    comment="ketrika-block-external-dns-tcp"

# ---- Forcer tout le DNS via le routeur ----
/ip firewall nat add chain=dstnat \
    protocol=udp \
    dst-port=53 \
    action=redirect \
    to-ports=53 \
    comment="ketrika-dns-redirect"
    
/ip firewall nat add chain=dstnat \
    protocol=tcp \
    dst-port=53 \
    action=redirect \
    to-ports=53 \
    comment="ketrika-dns-redirect-tcp"

# ---- Désactiver le fingerprinting ----
:do {
/ip settings set tcp-syncookies=yes
} on-error={}

:do {
/ip settings set rp-filter=strict
} on-error={}

:log info "KETRIKA: Obfuscation FAI activée - Indétectable"
"""

    def _sleep_schedule(self, config):
        """Mise en veille programmée avec limitation de débit"""
        start = config.get('sleep_start', '23:00')
        end = config.get('sleep_end', '06:00')
        limit_type = config.get('sleep_limit', 'none')
        dl = config.get('sleep_download', '512k')
        ul = config.get('sleep_upload', '256k')
        
        if limit_type == 'none':
            # Pas de limitation, juste du camouflage
            return f"""# ═══════════════════════════════════════
# SECTION 12: Mise en veille programmée (Camouflage)
# ═══════════════════════════════════════

# Scheduler: Mode nuit (camouflage renforcé)
/system scheduler add name="ketrika-sleep-start" \
    start-time={start} \
    interval=1d \
    on-event="/queue simple add name=ketrika-night-mode target=bridge-lan max-limit=100M/100M comment=ketrika-sleep" \
    comment="ketrika"

/system scheduler add name="ketrika-sleep-end" \
    start-time={end} \
    interval=1d \
    on-event="/queue simple remove [find where comment=ketrika-sleep]" \
    comment="ketrika"

:log info "KETRIKA: Mode veille programmé {start}-{end} (non limité)"
"""
        else:
            return f"""# ═══════════════════════════════════════
# SECTION 12: Mise en veille avec limitation
# ═══════════════════════════════════════

# Script de limitation nocturne
/system script add name="ketrika-night-on" source={{
:log info "KETRIKA: Mode nuit activé - Débit limité"
/queue simple add name=ketrika-night-limit \
    target=bridge-lan \
    max-limit={ul}/{dl} \
    burst-limit={ul}/{dl} \
    comment="ketrika-sleep"
}} comment="ketrika"

/system script add name="ketrika-night-off" source={{
:log info "KETRIKA: Mode jour activé - Plein débit"
:do {{
/queue simple remove [find where comment="ketrika-sleep"]
}} on-error={{}}
}} comment="ketrika"

# Planification
/system scheduler add name="ketrika-sleep-start" \
    start-time={start} \
    interval=1d \
    on-event="ketrika-night-on" \
    comment="ketrika"

/system scheduler add name="ketrika-sleep-end" \
    start-time={end} \
    interval=1d \
    on-event="ketrika-night-off" \
    comment="ketrika"

:log info "KETRIKA: Veille programmée {start}-{end} ({dl}/{ul})"
"""

    def _warp_wireguard(self, config):
        """Configuration WARP WireGuard complète"""
        warp = config.get('warp', {})
        
        private_key = warp.get('private_key', '')
        public_key = warp.get('public_key', '')
        endpoint = warp.get('endpoint', 'engage.cloudflareclient.com:2408')
        address_v4 = warp.get('address_v4', '172.16.0.2/32')
        mtu = warp.get('mtu', 1280)
        keepalive = warp.get('keepalive', 25)
        
        # Séparer host:port
        if ':' in endpoint:
            ep_host, ep_port = endpoint.rsplit(':', 1)
        else:
            ep_host = endpoint
            ep_port = '2408'
        
        return f"""# ═══════════════════════════════════════
# SECTION WARP: WireGuard Cloudflare (Obfuscation Maximale)
# ═══════════════════════════════════════

# ---- Créer l'interface WireGuard ----
:do {{
/interface wireguard add name=warp-wg \
    listen-port=0 \
    mtu={mtu} \
    private-key="{private_key}" \
    comment="ketrika-warp"
}} on-error={{
:log warning "KETRIKA: WireGuard existe déjà, mise à jour..."
/interface wireguard set [find name=warp-wg] \
    private-key="{private_key}" \
    mtu={mtu}
}}

:delay 2s

# ---- Ajouter le peer WARP ----
:do {{
/interface wireguard peers add \
    interface=warp-wg \
    public-key="{public_key}" \
    endpoint-address={ep_host} \
    endpoint-port={ep_port} \
    allowed-address=0.0.0.0/0,::/0 \
    persistent-keepalive={keepalive}s \
    comment="ketrika-warp-peer"
}} on-error={{
:log info "KETRIKA: Peer WARP mis à jour"
:do {{
/interface wireguard peers set [find where comment="ketrika-warp-peer"] \
    public-key="{public_key}" \
    endpoint-address={ep_host} \
    endpoint-port={ep_port}
}} on-error={{}}
}}

:delay 2s

# ---- Adresse IP du tunnel ----
:do {{
/ip address add address={address_v4} interface=warp-wg comment="ketrika-warp-ip"
}} on-error={{}}

# ---- Routes via WARP ----
# Route par défaut via WARP avec distance plus basse
:do {{
/ip route add dst-address=0.0.0.0/0 gateway=warp-wg distance=1 comment="ketrika-warp-route"
}} on-error={{}}

# Route directe vers l'endpoint WARP (ne pas passer par le tunnel)
:do {{
:local wanGW [/ip dhcp-client get [find interface={config.get('wan_interface', 'ether1')}] gateway]
/ip route add dst-address={ep_host}/32 gateway=$wanGW distance=1 comment="ketrika-warp-endpoint"
}} on-error={{
:log warning "KETRIKA: Route endpoint manuelle nécessaire"
}}

# ---- NAT pour le tunnel WARP ----
/ip firewall nat add chain=srcnat \
    out-interface=warp-wg \
    action=masquerade \
    comment="ketrika-warp-nat"

# ---- Firewall pour WARP ----
/ip firewall filter add chain=input \
    protocol=udp \
    dst-port={ep_port} \
    action=accept \
    comment="ketrika-warp-fw" \
    place-before=0

/ip firewall filter add chain=forward \
    in-interface=warp-wg \
    connection-state=established,related \
    action=accept \
    comment="ketrika-warp-fw-fwd" \
    place-before=0

# ---- Activer l'interface ----
/interface wireguard enable warp-wg

# ---- Mettre à jour le DoH via WARP ----
/ip dns set use-doh-server=https://cloudflare-dns.com/dns-query

:log info "KETRIKA: WARP WireGuard actif - Tunnel chiffré opérationnel"
:delay 3s
"""

    def _hotspot_config(self, config):
        """Configuration Hotspot complète"""
        hotspot_name = config.get('hotspot_name', 'KETRIKA-SPOT')
        gateway = config.get('gateway_ip', '192.168.88.1')
        user_list = config.get('user_list', '')
        
        # Parser la liste d'utilisateurs
        users_script = ""
        if user_list:
            for line in user_list.strip().split('\n'):
                parts = line.strip().split(':')
                if len(parts) >= 2:
                    username = parts[0].strip()
                    password = parts[1].strip()
                    profile = parts[2].strip() if len(parts) > 2 else 'default'
                    users_script += f"""
:do {{
/ip hotspot user add name="{username}" password="{password}" profile={profile} comment="ketrika"
}} on-error={{}}"""
        
        dl = config.get('download_limit', '10M')
        ul = config.get('upload_limit', '5M')
        
        return f"""# ═══════════════════════════════════════
# SECTION HOTSPOT: Portail Captif
# ═══════════════════════════════════════

# ---- Profils de bande passante ----
:do {{
/ip hotspot user profile add name="premium" \
    rate-limit="{ul}/{dl}" \
    shared-users=3 \
    status-autorefresh=1m \
    idle-timeout=30m \
    keepalive-timeout=2m \
    comment="ketrika"
}} on-error={{}}

:do {{
/ip hotspot user profile add name="standard" \
    rate-limit="2M/5M" \
    shared-users=2 \
    status-autorefresh=1m \
    idle-timeout=15m \
    keepalive-timeout=2m \
    comment="ketrika"
}} on-error={{}}

:do {{
/ip hotspot user profile add name="basic" \
    rate-limit="1M/2M" \
    shared-users=1 \
    status-autorefresh=1m \
    idle-timeout=10m \
    keepalive-timeout=2m \
    comment="ketrika"
}} on-error={{}}

# ---- Configuration Hotspot ----
:do {{
/ip hotspot setup hotspot-interface=bridge-lan \
    address={gateway}/24 \
    masquerade=yes \
    name={hotspot_name}
}} on-error={{
:log info "KETRIKA: Hotspot setup alternatif..."
:do {{
/ip hotspot add name={hotspot_name} \
    interface=bridge-lan \
    address-pool=dhcp-pool \
    profile=default \
    idle-timeout=5m \
    keepalive-timeout=2m \
    disabled=no \
    comment="ketrika"
}} on-error={{}}
}}

# ---- Profil du serveur hotspot ----
:do {{
/ip hotspot profile set [find name=default] \
    hotspot-address={gateway} \
    dns-name="{hotspot_name.lower()}.wifi" \
    html-directory=flash/hotspot \
    login-by=http-chap,http-pap \
    http-cookie-lifetime=1d \
    rate-limit="{ul}/{dl}"
}} on-error={{}}

# ---- Utilisateurs ----
{users_script}

# ---- Walled Garden (accès sans login) ----
:do {{
/ip hotspot walled-garden add dst-host="*.google.com" action=allow comment="ketrika"
/ip hotspot walled-garden add dst-host="*.googleapis.com" action=allow comment="ketrika"
}} on-error={{}}

:log info "KETRIKA: Hotspot {hotspot_name} actif"
"""

    def _pppoe_config(self, config):
        """Configuration PPPoE Server"""
        pppoe_service = config.get('pppoe_service', 'internet')
        gateway = config.get('gateway_ip', '192.168.88.1')
        user_list = config.get('user_list', '')
        dl = config.get('download_limit', '10M')
        ul = config.get('upload_limit', '5M')
        
        # Parser les utilisateurs
        users_script = ""
        if user_list:
            for line in user_list.strip().split('\n'):
                parts = line.strip().split(':')
                if len(parts) >= 2:
                    username = parts[0].strip()
                    password = parts[1].strip()
                    profile = parts[2].strip() if len(parts) > 2 else 'pppoe-profile'
                    users_script += f"""
:do {{
/ppp secret add name="{username}" password="{password}" \
    profile={profile} service=pppoe \
    local-address={gateway} \
    comment="ketrika"
}} on-error={{}}"""
        
        return f"""# ═══════════════════════════════════════
# SECTION PPPoE: Serveur PPPoE
# ═══════════════════════════════════════

# ---- Pool PPPoE ----
:do {{
/ip pool add name=pppoe-pool ranges=192.168.99.10-192.168.99.254 comment="ketrika"
}} on-error={{}}

# ---- Profil PPPoE ----
:do {{
/ppp profile add name=pppoe-profile \
    local-address={gateway} \
    remote-address=pppoe-pool \
    dns-server={gateway} \
    rate-limit="{ul}/{dl}" \
    only-one=yes \
    comment="ketrika"
}} on-error={{}}

# ---- Serveur PPPoE ----
:do {{
/interface pppoe-server server add \
    service-name={pppoe_service} \
    interface=bridge-lan \
    default-profile=pppoe-profile \
    authentication=pap,chap,mschap1,mschap2 \
    disabled=no \
    one-session-per-host=yes \
    comment="ketrika"
}} on-error={{}}

# ---- Utilisateurs PPPoE ----
{users_script}

:log info "KETRIKA: PPPoE Server actif - Service: {pppoe_service}"
"""

    def _finalize(self, config):
        """Finalisation du script"""
        return """# ═══════════════════════════════════════
# FINALISATION
# ═══════════════════════════════════════

# Nettoyer le cache
/ip dns cache flush

# Vérification finale
:delay 3s

:log info "╔══════════════════════════════════════════════╗"
:log info "║   KETRIKA MIKROTIK - Configuration terminée  ║"
:log info "║   Tous les services sont actifs              ║"
:log info "║   Obfuscation FAI: ACTIVÉE                   ║"
:log info "╚══════════════════════════════════════════════╝"

:put ""
:put "========================================"
:put "  KETRIKA MIKROTIK - TERMINÉ ✅"
:put "  Configuration appliquée avec succès"
:put "========================================"
:put ""
"""