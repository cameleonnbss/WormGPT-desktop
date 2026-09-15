"""OSINT toolkit for the agent mode (passive reconnaissance, stdlib only).

Every function is read-only against public data sources and returns a compact
text digest that is fed back to the model. All output is bounded so a recon
pass can never flood the context window.

Public sources used (no API key, no account):

    DNS        Cloudflare DNS-over-HTTPS (JSON), with a socket fallback
    WHOIS      RDAP (rdap.org) — the JSON/HTTPS successor of whois
    HTTP       direct request: status, headers, server, page title
    IP         ip-api.com (free JSON endpoint) — geo, ASN, ISP
    Ports      TCP connect scan on a bounded list
    Subdomains certificate transparency (crt.sh) + DNS brute force
    Usernames  presence check across common public sites

The port scan and the username sweep are active by nature: they stay bounded
(short timeouts, small lists) and the user still confirms every command when
the agent runs in "ask" mode.
"""

import ipaddress
import json
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request

UA = "WormGPT-Desktop/1.1 (+local OSINT module)"
TIMEOUT = 12
MAX_OUT = 4000
MAX_PORTS = 64
MAX_SUBS = 120
MAX_SITES = 12

_DOH = "https://cloudflare-dns.com/dns-query"
_RDAP = "https://rdap.org/domain/"
_CRT = "https://crt.sh/?q=%25.{domain}&output=json"
_IPAPI = ("http://ip-api.com/json/{q}?fields=status,message,country,regionName,"
          "city,zip,lat,lon,timezone,isp,org,as,reverse,query")

COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993,
                995, 1433, 1521, 2049, 2082, 2083, 3000, 3128, 3306, 3389,
                4444, 5000, 5432, 5900, 6379, 7001, 8000, 8006, 8080, 8081,
                8443, 8888, 9000, 9090, 9200, 27017]

RECORD_TYPES = ("A", "AAAA", "MX", "NS", "TXT", "SOA", "CNAME", "CAA")

_SUB_WORDS = ["www", "mail", "webmail", "smtp", "imap", "pop", "ns1", "ns2",
              "dns", "dev", "staging", "stage", "test", "beta", "api", "app",
              "admin", "portal", "vpn", "remote", "ftp", "git", "gitlab",
              "jenkins", "ci", "cdn", "static", "assets", "img", "media",
              "db", "mysql", "pgsql", "redis", "monitor", "grafana", "kibana",
              "status", "docs", "wiki", "blog", "shop", "store", "secure",
              "auth", "sso", "intranet", "backup", "demo", "sandbox"]

_SITES = [
    ("GitHub", "https://github.com/{u}"),
    ("GitLab", "https://gitlab.com/{u}"),
    ("Reddit", "https://www.reddit.com/user/{u}"),
    ("Instagram", "https://www.instagram.com/{u}/"),
    ("TikTok", "https://www.tiktok.com/@{u}"),
    ("Pinterest", "https://www.pinterest.com/{u}/"),
    ("Steam", "https://steamcommunity.com/id/{u}"),
    ("Twitch", "https://www.twitch.tv/{u}"),
    ("Medium", "https://medium.com/@{u}"),
    ("Docker Hub", "https://hub.docker.com/u/{u}"),
    ("HackerNews", "https://news.ycombinator.com/user?id={u}"),
    ("Keybase", "https://keybase.io/{u}"),
]


# --------------------------------------------------------------------------- helpers

def _clip(text, limit=MAX_OUT):
    text = str(text or "")
    return text if len(text) <= limit else text[:limit] + "\n… (truncated)"


def _clean(target):
    """Strip scheme/path so 'https://x.com/a' -> 'x.com'."""
    t = str(target or "").strip()
    if "://" in t:
        t = t.split("://", 1)[1]
    return t.split("/", 1)[0].split("?", 1)[0].split(":", 1)[0].lower()


def _get(url, headers=None, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    ctx = ssl.create_default_context()
    return urllib.request.urlopen(req, timeout=timeout, context=ctx)


def _get_json(url, headers=None, timeout=TIMEOUT):
    with _get(url, headers, timeout) as resp:
        raw = resp.read(2_000_000)
    return json.loads(raw.decode("utf-8", "replace"))


# ------------------------------------------------------------------- DNS / whois

def dns_lookup(domain, record_type="A"):
    """Resolve DNS records through DNS-over-HTTPS (no local resolver needed)."""
    name = _clean(domain)
    rtype = (str(record_type or "A").strip().upper() or "A")
    if rtype not in RECORD_TYPES and rtype != "ANY":
        rtype = "A"
    if not name:
        return "[empty domain]"
    lines = []
    types = [rtype] if rtype != "ANY" else ["A", "AAAA", "MX", "NS", "TXT"]
    for rt in types:
        try:
            data = _get_json(
                f"{_DOH}?name={urllib.parse.quote(name)}&type={rt}",
                headers={"User-Agent": UA, "Accept": "application/dns-json"})
        except Exception as exc:
            lines.append(f"{rt}: [error: {exc}]")
            continue
        answers = data.get("Answer") or []
        if not answers:
            lines.append(f"{rt}: (none)")
            continue
        for a in answers:
            lines.append(f"{rt}: {a.get('data', '')}")
    if len(lines) == 1 and lines[0].endswith("[error]"):
        return _dns_socket(name)
    return _clip("\n".join(lines))


def _dns_socket(name):
    """Fallback resolution when DoH is unreachable."""
    try:
        infos = socket.getaddrinfo(name, None)
        addrs = sorted({i[4][0] for i in infos})
        return _clip("\n".join(f"A: {a}" for a in addrs) or "(none)")
    except Exception as exc:
        return f"[dns error: {exc}]"


def whois_lookup(domain):
    """Domain registration data via RDAP (JSON successor of whois)."""
    name = _clean(domain)
    if not name:
        return "[empty domain]"
    try:
        data = _get_json(_RDAP + urllib.parse.quote(name))
    except urllib.error.HTTPError as exc:
        return f"[rdap error {exc.code}] — no registration data for {name}"
    except Exception as exc:
        return f"[rdap error: {exc}]"
    out = [f"domain: {data.get('ldhName', name)}"]
    for ev in data.get("events") or []:
        if ev.get("eventAction") in ("registration", "expiration",
                                     "last changed"):
            out.append(f"{ev['eventAction']}: {ev.get('eventDate', '')}")
    for ent in data.get("entities") or []:
        roles = ",".join(ent.get("roles") or [])
        vcard = ent.get("vcardArray") or []
        name_val = ""
        if len(vcard) > 1:
            for item in vcard[1]:
                if item and item[0] == "fn":
                    name_val = item[3]
        if roles or name_val:
            out.append(f"{roles or 'entity'}: {name_val or ent.get('handle', '')}")
    for ns in data.get("nameservers") or []:
        out.append(f"ns: {ns.get('ldhName', '')}")
    out.append(f"status: {', '.join(data.get('status') or [])}")
    return _clip("\n".join(out))


# ------------------------------------------------------------------ http / ip

def http_probe(url):
    """Fetch a URL and report status, headers, server and page title."""
    target = str(url or "").strip()
    if not target:
        return "[empty url]"
    if "://" not in target:
        target = "https://" + target
    try:
        with _get(target) as resp:
            body = resp.read(200_000).decode("utf-8", "replace")
            status = resp.status
            headers = dict(resp.headers)
            final = resp.geturl()
    except urllib.error.HTTPError as exc:
        return f"[http {exc.code} {exc.reason}] {target}"
    except Exception as exc:
        return f"[probe error: {exc}]"
    keep = ("server", "x-powered-by", "content-type", "strict-transport-security",
            "content-security-policy", "x-frame-options", "set-cookie",
            "location", "via", "x-generator")
    out = [f"url: {final}", f"status: {status}"]
    for k, v in headers.items():
        if k.lower() in keep:
            out.append(f"{k}: {v[:200]}")
    title = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
    if title:
        out.append("title: " + re.sub(r"\s+", " ", title.group(1))[:200])
    tech = sorted(set(re.findall(r"(?:wordpress|drupal|joomla|react|angular|"
                                 r"vue|next\.js|nginx|apache|iis|cloudflare|"
                                 r"shopify|woocommerce)", body, re.I)))
    if tech:
        out.append("technologies: " + ", ".join(tech))
    return _clip("\n".join(out))


def ip_info(ip):
    """Geolocation / ASN / ISP for an IP or hostname (ip-api.com)."""
    query = str(ip or "").strip()
    if not query:
        return "[empty ip]"
    try:
        data = _get_json(_IPAPI.format(q=urllib.parse.quote(query)))
    except Exception as exc:
        return f"[ip error: {exc}]"
    if data.get("status") != "success":
        return f"[ip error: {data.get('message', 'lookup failed')}]"
    rows = [("query", "query"), ("reverse", "ptr"), ("country", "country"),
            ("regionName", "region"), ("city", "city"), ("zip", "zip"),
            ("lat", "lat"), ("lon", "lon"), ("timezone", "timezone"),
            ("isp", "isp"), ("org", "org"), ("as", "asn")]
    return _clip("\n".join(f"{label}: {data.get(key, '')}"
                           for key, label in rows if data.get(key) not in (None, "")))


def port_scan(host, ports=""):
    """TCP connect scan (bounded). ``ports`` = "22,80,443" or "1-1024"."""
    target = _clean(host)
    if not target:
        return "[empty host]"
    wanted = _parse_ports(ports) or COMMON_PORTS
    wanted = wanted[:MAX_PORTS]
    open_ports, closed = [], 0
    try:
        ip = socket.gethostbyname(target)
    except Exception as exc:
        return f"[resolve error: {exc}]"
    for port in wanted:
        s = socket.socket()
        s.settimeout(0.9)
        try:
            if s.connect_ex((ip, port)) == 0:
                open_ports.append(port)
            else:
                closed += 1
        except Exception:
            closed += 1
        finally:
            s.close()
    if not open_ports:
        return f"host: {target} ({ip})\nno open port among {len(wanted)} tested"
    return _clip(f"host: {target} ({ip})\nopen: "
                 + ", ".join(str(p) for p in open_ports)
                 + f"\nscanned: {len(wanted)} ports")


def _parse_ports(spec):
    spec = str(spec or "").strip()
    if not spec:
        return []
    out = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if "-" in chunk:
            try:
                a, b = chunk.split("-", 1)
                a, b = int(a), int(b)
            except ValueError:
                continue
            if a > b:
                a, b = b, a
            out.extend(range(max(1, a), min(65535, b) + 1))
        elif chunk.isdigit():
            out.append(int(chunk))
    seen, uniq = set(), []
    for p in out:
        if 1 <= p <= 65535 and p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


# --------------------------------------------------------------- subdomains

def subdomains(domain, brute=True):
    """Passive (crt.sh) + optional DNS brute-force subdomain enumeration."""
    name = _clean(domain)
    if not name:
        return "[empty domain]"
    found = {}
    try:
        data = _get_json(_CRT.format(domain=urllib.parse.quote(name)))
        for row in data if isinstance(data, list) else []:
            for value in str(row.get("name_value", "")).splitlines():
                value = value.strip().lower().lstrip("*.")
                if value.endswith(name) and value != name:
                    found[value] = "crt.sh"
    except Exception as exc:
        found["(crt.sh unavailable)"] = str(exc)[:80]
    if brute:
        for word in _SUB_WORDS[:MAX_SUBS]:
            candidate = f"{word}.{name}"
            try:
                socket.getaddrinfo(candidate, None)
                found.setdefault(candidate, "dns")
            except Exception:
                continue
            if len(found) >= MAX_SUBS:
                break
    if not found:
        return f"[no subdomain found for {name}]"
    lines = [f"{host}  ({src})" for host, src in sorted(found.items())]
    return _clip(f"subdomains of {name} ({len(lines)}):\n" + "\n".join(lines))


# ------------------------------------------------------------------ identity

def username_recon(username):
    """Check where a username exists across common public sites."""
    user = str(username or "").strip().lstrip("@")
    if not user or not re.fullmatch(r"[A-Za-z0-9._\-]{2,40}", user):
        return "[invalid username]"
    hits, misses = [], 0
    for label, pattern in _SITES[:MAX_SITES]:
        url = pattern.format(u=urllib.parse.quote(user))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA},
                                         method="GET")
            with urllib.request.urlopen(req, timeout=8,
                                        context=ssl.create_default_context()) as r:
                if r.status < 400:
                    hits.append(f"{label}: {url}")
                else:
                    misses += 1
        except Exception:
            misses += 1
    if not hits:
        return f"username '{user}': no public profile found ({misses} sites checked)"
    return _clip(f"username '{user}' found on:\n" + "\n".join(hits))


def email_recon(email):
    """MX records + gravatar + provider hints for an email address."""
    addr = str(email or "").strip()
    if "@" not in addr:
        return "[invalid email]"
    local, domain = addr.rsplit("@", 1)
    out = [f"address: {addr}", f"local part: {local}", f"domain: {domain}"]
    out.append("--- MX ---")
    out.append(dns_lookup(domain, "MX"))
    import hashlib
    digest = hashlib.md5(addr.strip().lower().encode("utf-8")).hexdigest()
    out.append("--- gravatar ---")
    try:
        url = f"https://www.gravatar.com/avatar/{digest}?d=404"
        with _get(url) as resp:
            out.append(f"profile: yes ({resp.status})")
    except urllib.error.HTTPError as exc:
        out.append("profile: no" if exc.code == 404 else f"profile: http {exc.code}")
    except Exception as exc:
        out.append(f"profile: [error: {exc}]")
    return _clip("\n".join(out))


def is_valid_ip(text):
    try:
        ipaddress.ip_address(str(text).strip())
        return True
    except ValueError:
        return False


# ------------------------------------------------------------------- tool schema

TOOLS = [
    {"type": "function", "function": {
        "name": "dns_lookup",
        "description": ("Resolve DNS records for a domain (A, AAAA, MX, NS, "
                        "TXT, SOA, CNAME, CAA or ANY) through DNS-over-HTTPS."),
        "parameters": {"type": "object", "properties": {
            "domain": {"type": "string"},
            "record_type": {"type": "string",
                            "description": "A, MX, TXT, NS… (default A)"}},
            "required": ["domain"]}}},
    {"type": "function", "function": {
        "name": "whois_lookup",
        "description": ("Domain registration data (registrar, dates, "
                        "nameservers, status) via RDAP."),
        "parameters": {"type": "object", "properties": {
            "domain": {"type": "string"}}, "required": ["domain"]}}},
    {"type": "function", "function": {
        "name": "http_probe",
        "description": ("Fetch a URL and report status, server headers, page "
                        "title and detected technologies."),
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {
        "name": "ip_info",
        "description": ("Geolocation, ASN, ISP and reverse DNS for an IP "
                        "address or hostname."),
        "parameters": {"type": "object", "properties": {
            "ip": {"type": "string"}}, "required": ["ip"]}}},
    {"type": "function", "function": {
        "name": "port_scan",
        "description": ("TCP connect scan of a host. Defaults to a common "
                        "port list; pass ports like \"22,80,443\" or "
                        "\"1-1024\" (max 64 ports per call)."),
        "parameters": {"type": "object", "properties": {
            "host": {"type": "string"},
            "ports": {"type": "string"}}, "required": ["host"]}}},
    {"type": "function", "function": {
        "name": "subdomains",
        "description": ("Enumerate subdomains of a domain: certificate "
                        "transparency (crt.sh) plus a small DNS brute force."),
        "parameters": {"type": "object", "properties": {
            "domain": {"type": "string"}}, "required": ["domain"]}}},
    {"type": "function", "function": {
        "name": "username_recon",
        "description": ("Check on which public sites a username exists "
                        "(GitHub, Reddit, Instagram, Steam, …)."),
        "parameters": {"type": "object", "properties": {
            "username": {"type": "string"}}, "required": ["username"]}}},
    {"type": "function", "function": {
        "name": "email_recon",
        "description": ("Recon on an email address: MX records, gravatar "
                        "presence and provider hints."),
        "parameters": {"type": "object", "properties": {
            "email": {"type": "string"}}, "required": ["email"]}}},
]
