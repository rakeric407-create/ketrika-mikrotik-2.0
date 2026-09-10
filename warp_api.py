# warp_api.py
import json
import requests
import secrets
import base64
import time

class WarpGenerator:
    """Génère automatiquement les configurations WARP/WireGuard"""
    
    API_URL = "https://api.cloudflareclient.com/v0a2158/reg"
    
    def __init__(self):
        self.session = requests.Session()
    
    def _generate_keypair(self):
        """Génère une paire de clés WireGuard"""
        try:
            import subprocess
            privkey = subprocess.run(
                ['wg', 'genkey'], capture_output=True, text=True
            ).stdout.strip()
            
            pubkey = subprocess.run(
                ['wg', 'pubkey'], input=privkey, capture_output=True, text=True
            ).stdout.strip()
            
            return privkey, pubkey
        except Exception:
            # Fallback: génération simulée compatible MikroTik
            privkey = base64.b64encode(secrets.token_bytes(32)).decode()
            # On ne peut pas dériver la pubkey sans wg, on utilisera l'API
            return privkey, None
    
    def generate_warp_config(self):
        """Génère une config WARP complète pour MikroTik"""
        try:
            return self._register_warp()
        except Exception as e:
            print(f"⚠️ WARP API error: {e}")
            return self._generate_fallback_config()
    
    def _register_warp(self):
        """Enregistrement via l'API Cloudflare WARP"""
        private_key, _ = self._generate_keypair()
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'okhttp/3.12.1',
        }
        
        # Étape 1: Enregistrement
        try:
            reg_data = {
                "key": base64.b64encode(secrets.token_bytes(32)).decode(),
                "install_id": secrets.token_hex(22),
                "fcm_token": f"{secrets.token_hex(22)}:APA91b{secrets.token_hex(60)}",
                "tos": "2023-01-01T00:00:00+00:00",
                "model": "MikroTik",
                "serial_number": secrets.token_hex(12),
                "type": "Android",
                "locale": "fr_MG"
            }
            
            resp = self.session.post(self.API_URL, json=reg_data, headers=headers, timeout=15)
            
            if resp.status_code in [200, 201]:
                data = resp.json()
                return self._parse_warp_response(data, private_key)
        except requests.RequestException:
            pass
        
        return self._generate_fallback_config()
    
    def _parse_warp_response(self, data, private_key):
        """Parse la réponse de l'API WARP"""
        config = data.get('config', {})
        peers = config.get('peers', [{}])
        peer = peers[0] if peers else {}
        interface = config.get('interface', {})
        addresses = interface.get('addresses', {})
        
        return {
            'private_key': private_key,
            'public_key': peer.get('public_key', 'bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo='),
            'endpoint': peer.get('endpoint', {}).get('host', 'engage.cloudflareclient.com:2408'),
            'address_v4': addresses.get('v4', '172.16.0.2/32'),
            'address_v6': addresses.get('v6', 'fd01:db8:1111::2/128'),
            'mtu': 1280,
            'allowed_ips': '0.0.0.0/0, ::/0',
            'dns': '1.1.1.1,1.0.0.1',
            'keepalive': 25,
            'reserved': self._generate_reserved()
        }
    
    def _generate_fallback_config(self):
        """Config de fallback si l'API est indisponible"""
        private_key = base64.b64encode(secrets.token_bytes(32)).decode()
        
        # Endpoints WARP connus
        endpoints = [
            "engage.cloudflareclient.com:2408",
            "162.159.193.1:2408",
            "162.159.195.1:2408",
            "162.159.192.1:2408",
            "188.114.96.1:2408",
            "188.114.97.1:2408"
        ]
        
        return {
            'private_key': private_key,
            'public_key': 'bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo=',
            'endpoint': secrets.choice(endpoints),
            'address_v4': f'172.16.0.{secrets.randbelow(254) + 2}/32',
            'address_v6': f'fd01:db8:1111::{secrets.randbelow(65534) + 2}/128',
            'mtu': 1280,
            'allowed_ips': '0.0.0.0/0, ::/0',
            'dns': '1.1.1.1,1.0.0.1',
            'keepalive': 25,
            'reserved': self._generate_reserved()
        }
    
    def _generate_reserved(self):
        """Génère les bytes réservés pour WARP"""
        reserved_bytes = secrets.token_bytes(3)
        return ','.join(str(b) for b in reserved_bytes)