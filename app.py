# app.py
import os
import secrets
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from database import Database, LicenseManager
from warp_api import WarpGenerator
from script_generator import MikroTikGenerator

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Initialisation BD
db = Database()
db.init_db()

license_mgr = LicenseManager(db)
warp_gen = WarpGenerator()
script_gen = MikroTikGenerator()

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
        license_key = request.form.get('license_key', '').strip()
        router_serial = request.form.get('router_serial', '').strip()
        
        if not license_key or not router_serial:
            flash('❌ Veuillez remplir tous les champs !', 'error')
            return render_template('activate.html')
            
        result = license_mgr.activate_license(license_key, router_serial)
        if result['success']:
            session['license_key'] = license_key
            session['pack_id'] = result['pack_id']
            session['activated'] = True
            flash('✅ Clé activée avec succès !', 'success')
            return redirect(url_for('generator'))
        else:
            flash(f'❌ {result["message"]}', 'error')
    
    return render_template('activate.html')

@app.route('/generator', methods=['GET', 'POST'])
def generator():
    if not session.get('activated'):
        flash('⚠️ Activez une clé ou utilisez le mode Démo.', 'warning')
        return redirect(url_for('activate'))
    
    pack_id = session.get('pack_id', 1)
    
    if request.method == 'POST':
        try:
            config = {
                'router_name': request.form.get('router_name', 'MikroTik'),
                'wan_interface': request.form.get('wan_interface', 'ether1'),
                'lan_interface': request.form.get('lan_interface', 'ether2'),
                'wifi_mode': request.form.get('wifi_mode', 'auto'),
                'ssid_main': request.form.get('ssid_main', 'MonWiFi'),
                'ssid_password': request.form.get('ssid_password', '12345678'),
                'ssid_separate': request.form.get('ssid_separate') == 'on',
                'ssid_2g': request.form.get('ssid_2g', ''),
                'ssid_5g': request.form.get('ssid_5g', ''),
                'password_2g': request.form.get('password_2g', ''),
                'password_5g': request.form.get('password_5g', ''),
                'change_mac': request.form.get('change_mac') == 'on',
                'custom_mac': request.form.get('custom_mac', ''),
                'router_identity': request.form.get('router_identity', 'Home-Gateway'),
                'lan_subnet': request.form.get('lan_subnet', '192.168.88.0/24'),
                'gateway_ip': request.form.get('gateway_ip', '192.168.88.1'),
                'dhcp_start': request.form.get('dhcp_start', '192.168.88.10'),
                'dhcp_end': request.form.get('dhcp_end', '192.168.88.254'),
                'sleep_enabled': request.form.get('sleep_enabled') == 'on',
                'sleep_start': request.form.get('sleep_start', '23:00'),
                'sleep_end': request.form.get('sleep_end', '06:00'),
                'sleep_limit': request.form.get('sleep_limit', 'none'),
                'sleep_download': request.form.get('sleep_download', '512k'),
                'sleep_upload': request.form.get('sleep_upload', '256k'),
                'pack_id': pack_id,
                'service_type': request.form.get('service_type', 'hotspot'),
                'hotspot_name': request.form.get('hotspot_name', 'KETRIKA-SPOT'),
                'pppoe_service': request.form.get('pppoe_service', 'internet'),
                'download_limit': request.form.get('download_limit', '10M'),
                'upload_limit': request.form.get('upload_limit', '5M'),
                'user_list': request.form.get('user_list', ''),
            }
            
            if pack_id >= 2:
                config['warp'] = warp_gen.generate_warp_config()
            
            script = script_gen.generate(config, pack_id)
            
            return render_template('generator.html', 
                                 pack=PACKS[pack_id], 
                                 pack_id=pack_id,
                                 script=script,
                                 config=config,
                                 generated=True)
        except Exception as e:
            flash(f"⚠️ Erreur de génération : {str(e)}", 'error')
    
    return render_template('generator.html', 
                         pack=PACKS[pack_id], 
                         pack_id=pack_id,
                         generated=False)

@app.route('/payment')
def payment():
    return render_template('payment.html', packs=PACKS)

@app.route('/demo/<int:pack_id>')
def demo(pack_id):
    if pack_id not in PACKS:
        pack_id = 1
    session['activated'] = True
    session['pack_id'] = pack_id
    session['license_key'] = 'DEMO-MODE'
    flash(f'🔧 Mode Démo activé : {PACKS[pack_id]["name"]}', 'info')
    return redirect(url_for('generator'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    generated_key = None
    pack_selected = None
    error = None
    
    if request.method == 'POST':
        admin_pass = request.form.get('admin_pass', '')
        pack_id = int(request.form.get('pack_id', 1))
        
        if admin_pass == os.environ.get('ADMIN_KEY', 'ketrika2024'):
            generated_key = license_mgr.generate_license(pack_id)
            pack_selected = PACKS[pack_id]['name']
        else:
            error = "Mot de passe Administrateur incorrect !"
            
    return render_template('admin.html', generated_key=generated_key, pack_selected=pack_selected, error=error, packs=PACKS)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
