"""WormGPT_Keys.py — générateur de clés de licence WormGPT.

Fonctionne tout seul (Python 3.8+, aucune dépendance). Deux modes :

  1. Mode interactif (double-clic) : il demande le nom, la durée et le nombre
     de clés, puis affiche les clés et les enregistre dans keys.txt.
  2. Mode ligne de commande :
       python WormGPT_Keys.py --name "Alice" --days 365 --count 3

Une clé ressemble à :  WGPT-XXXXXXXXXX-XXXXXXXXXXXXXXXXXXXX
L'application la valide hors ligne (signature HMAC-SHA256 + date d'expiration).
"""

import argparse
import base64
import datetime
import hashlib
import hmac
import os
import re
import sys

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
_SECRET = hashlib.sha256(b"WormGPT-license-v1.0").digest()

KEY_RE = re.compile(r"^WGPT-([A-Z2-7]{10})-([A-Z2-7]+)$")


def _b32encode(data: bytes) -> str:
    s = base64.b32encode(data).decode("ascii").rstrip("=")
    return "".join(c for c in s if c in _ALPHABET)


def _b32decode(text: str) -> bytes:
    pad = "=" * ((8 - len(text) % 8) % 8)
    return base64.b32decode((text + pad).encode("ascii"))


def _sign(payload_b32: str) -> str:
    digest = hmac.new(_SECRET, payload_b32.encode("ascii"), hashlib.sha256).digest()
    return _b32encode(digest[:6])


def generate_key(owner: str, expiry: str) -> str:
    """Crée une clé signée. expiry doit être 'YYYY-MM-DD'."""
    payload = f"{owner}|{expiry}|{_b32encode(os.urandom(3))}"
    payload_b32 = _b32encode(payload.encode("utf-8"))
    return f"WGPT-{_sign(payload_b32)}-{payload_b32}"


def validate_key(key: str):
    """Vérifie une clé. Retourne {valid, owner, expiry, reason}."""
    if not key:
        return {"valid": False, "owner": "", "expiry": "", "reason": "empty"}
    m = KEY_RE.match(key.strip().upper())
    if not m:
        return {"valid": False, "owner": "", "expiry": "", "reason": "format"}
    sig, payload_b32 = m.group(1), m.group(2)
    if not hmac.compare_digest(_sign(payload_b32), sig):
        return {"valid": False, "owner": "", "expiry": "", "reason": "signature"}
    try:
        payload = _b32decode(payload_b32).decode("utf-8")
        owner, expiry, _nonce = payload.split("|", 2)
    except Exception:
        return {"valid": False, "owner": "", "expiry": "", "reason": "payload"}
    try:
        exp = datetime.date.fromisoformat(expiry)
    except ValueError:
        return {"valid": False, "owner": owner, "expiry": expiry, "reason": "date"}
    if exp < datetime.date.today():
        return {"valid": False, "owner": owner, "expiry": expiry, "reason": "expired"}
    return {"valid": True, "owner": owner, "expiry": expiry, "reason": "ok"}


def parse_expiry(days, expiry):
    if expiry:
        datetime.date.fromisoformat(expiry)  # lève ValueError si invalide
        return expiry
    if days and days > 0:
        return (datetime.date.today() + datetime.timedelta(days=days)).isoformat()
    return "9999-12-31"


def interactive():
    print("=" * 56)
    print("  WormGPT — générateur de clés de licence")
    print("=" * 56)
    while True:
        name = input("Nom du propriétaire        : ").strip()
        if name:
            break
        print("  (le nom ne peut pas être vide)")
    days_raw = input("Durée de validité (jours) : ").strip() or "365"
    try:
        days = int(days_raw)
    except ValueError:
        days = 365
    count_raw = input("Nombre de clés            : ").strip() or "1"
    try:
        count = max(1, min(50, int(count_raw)))
    except ValueError:
        count = 1
    expiry = (datetime.date.today() + datetime.timedelta(days=max(1, days))).isoformat()
    print("-" * 56)
    keys = [generate_key(name, expiry) for _ in range(count)]
    for k in keys:
        print(k)
    print("-" * 56)
    print(f"{count} clé(s) pour « {name} » — valable(s) jusqu'au {expiry}")
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "keys.txt"), "w", encoding="utf-8") as f:
            f.write(f"# WormGPT — clés pour « {name} » (expiration {expiry})\n")
            f.write("\n".join(keys) + "\n")
        print("Enregistrées dans keys.txt (à côté de ce script).")
    except OSError as exc:
        print(f"Impossible d'écrire keys.txt : {exc}")
    verify = validate_key(keys[0])
    if verify["valid"]:
        print("Test de validation : OK ✓")
    input("Appuie sur Entrée pour quitter…")


def main():
    ap = argparse.ArgumentParser(description="Générer des clés de licence WormGPT")
    ap.add_argument("--name", help="nom du propriétaire (mode interactif si absent)")
    ap.add_argument("--expiry", default="", help="expiration YYYY-MM-DD")
    ap.add_argument("--days", type=int, default=365, help="validité en jours")
    ap.add_argument("--count", type=int, default=1, help="nombre de clés")
    ap.add_argument("--check", help="vérifier une clé existante et quitter")
    args = ap.parse_args()

    if args.check:
        info = validate_key(args.check)
        if info["valid"]:
            print(f"Clé VALIDE — propriétaire : {info['owner']}, "
                  f"expiration : {info['expiry']}")
        else:
            print(f"Clé INVALIDE ({info['reason']})")
        return

    if not args.name:
        interactive()
        return

    try:
        expiry = parse_expiry(args.days, args.expiry)
    except ValueError:
        print(f"Date invalide : {args.expiry} (format attendu YYYY-MM-DD)")
        sys.exit(1)

    count = max(1, min(50, args.count))
    for _ in range(count):
        print(generate_key(args.name, expiry))
    print(f"\n# {count} clé(s) pour « {args.name} » jusqu'au {expiry}")


if __name__ == "__main__":
    main()
