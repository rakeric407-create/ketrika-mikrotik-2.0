# app.py
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from database import Database, LicenseManager
from warp_api import WarpGenerator
from script_generator import MikroTikGenerator
import os
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

db = Database()
license_mgr = LicenseManager(db)
warp_gen = WarpGenerator()
script_gen = MikroTikGenerator()

# ============== PACKS ==============
PACKS = {
    1: {
        "name": "PACK CLASSIC DoH",
        "price": 20000,
        "currency": "Ar",
        "features": [
            "DNS over HTTPS (DoH)",
            "Changement MAC automatique",
            "Activation WiFi auto (AC/AX/AN)",
            "Séparation SSID",
            "Camouflage FAI complet",
            "Mise en veille programmable"
        ]
    },
    2: {
        "name": "PACK WARP WireGuard",
        "price": 40000,
        "currency": "Ar",
        "features": [
            "Tout le Pack Classic",
            "WARP Cloudflare intégré",
            "WireGuard auto-généré",
            "Obfuscation totale",
            "Double camouflage FAI",
            "Tunnel chiffré complet"
        ]
    },
    3: {
        "name": "PACK HOTSPOT / PPPoE",
        "price": 60000,
        "currency": "Ar",
        "features": [
            "Tout le Pack WARP",
            "Hotspot OU PPPoE (au choix)",
            "Gestion utilisateurs",
            "Limitation bande passante",
            "Portail captif personnalisé",
            "Monitoring complet"
        ]
    }
}

@app.route('/')
def index():
    return render_template('index.html', packs=PACKS)

@app.route('/activate', methods=['GET', 'POST'])
def activate():
    if request.method == 'POST':
        license_key = request.form.get('license_key')
        router_serial = request.form.get('router_serial')
        
        result = license_mgr.activate_license(license_key, router_serial)
        if result['success']:
            session['license_key'] = license_key
            session['pack_id'] = result['pack_id']
            session['activated'] = True
            flash('✅ Clé activée avec succès!', 'success')
            return redirect(url_for('generator'))
        else:
            flash(f'❌ {result["message"]}', 'error')
    
    return render_template('activate.html')

@app.route('/generator', methods=['GET', 'POST'])
def generator():
    if not session.get('activated'):
        flash('⚠️ Veuillez activer votre clé d\'abord', 'warning')
        return redirect(url_for('activate'))
    
    pack_id = session.get('pack_id', 1)
    
    if request.method == 'POST':
        config = {
            # Infos de base
            'router_name': request.form.get('router_name', 'MikroTik'),
            'wan_interface': request.form.get('wan_interface', 'ether1'),
            'lan_interface': request.form.get('lan_interface', 'ether2'),
            
            # WiFi
            'wifi_mode': request.form.get('wifi_mode', 'ac'),
            'ssid_main': request.form.get('ssid_main', 'MonWiFi'),
            'ssid_password': request.form.get('ssid_password', ''),
            'ssid_separate': request.form.get('ssid_separate') == 'on',
            'ssid_2g': request.form.get('ssid_2g', ''),
            'ssid_5g': request.form.get('ssid_5g', ''),
            'password_2g': request.form.get('password_2g', ''),
            'password_5g': request.form.get('password_5g', ''),
            
            # Camouflage
            'change_mac': request.form.get('change_mac') == 'on',
            'custom_mac': request.form.get('custom_mac', ''),
            'router_identity': request.form.get('router_identity', 'Home-Gateway'),
            
            # Réseau
            'lan_subnet': request.form.get('lan_subnet', '192.168.88.0/24'),
            'gateway_ip': request.form.get('gateway_ip', '192.168.88.1'),
            'dhcp_start': request.form.get('dhcp_start', '192.168.88.10'),
            'dhcp_end': request.form.get('dhcp_end', '192.168.88.254'),
            
            # Mise en veille
            'sleep_enabled': request.form.get('sleep_enabled') == 'on',
            'sleep_start': request.form.get('sleep_start', '23:00'),
            'sleep_end': request.form.get('sleep_end', '06:00'),
            'sleep_limit': request.form.get('sleep_limit', 'none'),
            'sleep_download': request.form.get('sleep_download', '512k'),
            'sleep_upload': request.form.get('sleep_upload', '256k'),
            
            # Pack spécifique
            'pack_id': pack_id,
            
            # Pack 3 options
            'service_type': request.form.get('service_type', 'hotspot'),
            'hotspot_name': request.form.get('hotspot_name', 'KETRIKA-SPOT'),
            'pppoe_service': request.form.get('pppoe_service', 'internet'),
            'bandwidth_limit': request.form.get('bandwidth_limit', 'none'),
            'download_limit': request.form.get('download_limit', '10M'),
            'upload_limit': request.form.get('upload_limit', '5M'),
            'user_list': request.form.get('user_list', ''),
        }
        
        # Génération WARP si Pack 2 ou 3
        warp_config = None
        if pack_id >= 2:
            warp_config = warp_gen.generate_warp_config()
            config['warp'] = warp_config
        
        # Générer le script
        script = script_gen.generate(config, pack_id)
        
        return render_template('generator.html', 
                             pack=PACKS[pack_id], 
                             pack_id=pack_id,
                             script=script,
                             config=config,
                             generated=True)
    
    return render_template('generator.html', 
                         pack=PACKS[pack_id], 
                         pack_id=pack_id,
                         generated=False)

@app.route('/payment')
def payment():
    return render_template('payment.html', packs=PACKS)

@app.route('/api/generate-key', methods=['POST'])
def api_generate_key():
    """Admin: Génère une clé de licence"""
    admin_key = request.json.get('admin_key')
    if admin_key != os.environ.get('ADMIN_KEY', 'ketrika-admin-2024'):
        return jsonify({'error': 'Non autorisé'}), 403
    
    pack_id = request.json.get('pack_id', 1)
    key = license_mgr.generate_license(pack_id)
    return jsonify({'license_key': key, 'pack_id': pack_id})

@app.route('/api/check-license', methods=['POST'])
def api_check_license():
    key = request.json.get('license_key')
    result = license_mgr.check_license(key)
    return jsonify(result)

# Demo mode pour tester
@app.route('/demo/<int:pack_id>')
def demo(pack_id):
    if pack_id not in PACKS:
        pack_id = 1
    session['activated'] = True
    session['pack_id'] = pack_id
    session['license_key'] = 'DEMO-MODE'
    flash(f'🔧 Mode démo activé - {PACKS[pack_id]["name"]}', 'info')
    return redirect(url_for('generator'))

if __name__ == '__main__':
    db.init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)