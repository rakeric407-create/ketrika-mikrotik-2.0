"""
WireGuard WARP - Pur Python (RFC 7748 Curve25519) + API Cloudflare.
Aucune dépendance externe cryptographique.
"""
import os
import base64
import requests

P = 2**255 - 19
A24 = 121665


def _cswap(swap, x2, x3):
    dummy = swap * (x2 - x3)
    return x2 - dummy, x3 + dummy


def _x25519(k_int, u_int):
    x1 = u_int
    x2, z2 = 1, 0
    x3, z3 = u_int, 1
    swap = 0
    for t in range(254, -1, -1):
        k_t = (k_int >> t) & 1
        swap ^= k_t
        x2, x3 = _cswap(swap, x2, x3)
        z2, z3 = _cswap(swap, z2, z3)
        swap = k_t
        A = (x2 + z2) % P
        AA = (A * A) % P
        B = (x2 - z2) % P
        BB = (B * B) % P
        E = (AA - BB) % P
        C = (x3 + z3) % P
        D = (x3 - z3) % P
        DA = (D * A) % P
        CB = (C * B) % P
        x3 = pow((DA + CB) % P, 2, P)
        z3 = (x1 * pow((DA - CB) % P, 2, P)) % P
        x2 = (AA * BB) % P
        z2 = (E * ((AA + A24 * E) % P)) % P
    x2, x3 = _cswap(swap, x2, x3)
    z2, z3 = _cswap(swap, z2, z3)
    return (x2 * pow(z2, P - 2, P)) % P


def _decode_scalar(k):
    k = bytearray(k)
    k[0] &= 248
    k[31] &= 127
    k[31] |= 64
    return int.from_bytes(k, "little")


def _decode_u(u):
    return int.from_bytes(u, "little") % P


def _encode(n):
    return n.to_bytes(32, "little")


def curve25519_scalarmult(scalar_bytes, u_bytes):
    return _encode(_x25519(_decode_scalar(scalar_bytes), _decode_u(u_bytes)))


BASE_POINT = b"\x09" + b"\x00" * 31


def generate_wireguard_keypair():
    priv = bytearray(os.urandom(32))
    priv[0] &= 248
    priv[31] &= 127
    priv[31] |= 64
    priv = bytes(priv)
    pub = curve25519_scalarmult(priv, BASE_POINT)
    return (
        base64.b64encode(priv).decode(),
        base64.b64encode(pub).decode()
    )


WARP_API = "https://api.cloudflareclient.com/v0a2158/reg"
WARP_HEADERS = {
    "CF-Client-Version": "a-6.11-2223",
    "User-Agent": "okhttp/3.12.1",
    "Content-Type": "application/json"
}


def register_warp():
    """
    Contacte Cloudflare pour enregistrer une cle publique reelle.
    Retourne {private_key, public_key, ipv4} ou None en cas derreur.
    """
    try:
        priv_b64, pub_b64 = generate_wireguard_keypair()
        payload = {
            "install_id": "",
            "tos": "2023-01-01T00:00:00.000Z",
            "key": pub_b64,
            "fcm_token": "",
            "type": "Android",
            "locale": "fr_FR"
        }
        r = requests.post(WARP_API, headers=WARP_HEADERS, json=payload, timeout=12)
        if r.status_code not in (200, 201):
            return None
        data = r.json()
        cfg = data.get("config", {})
        ipv4 = ""
        v4_list = cfg.get("interface", {}).get("addresses", {}).get("v4", [])
        if isinstance(v4_list, list) and len(v4_list) > 0:
            ipv4 = v4_list[0]
        elif isinstance(v4_list, str):
            ipv4 = v4_list
        return {
            "private_key": priv_b64,
            "public_key": pub_b64,
            "ipv4": ipv4 or "172.16.0.2"
        }
    except Exception:
        return None
