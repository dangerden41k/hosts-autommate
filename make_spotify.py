# make_spotify.py - regenerate spotify_hosts.txt with a LIVE, CERT-VALID server.
#
# Self-healing order when the current IP dies:
#   1. the FRESHEST community IP parsed from Flowseal discussion 5552 (the thread
#      where norijoo posts working blocks - fetched live, best-effort),
#   2. the current IP from the existing file,
#   3. every GeoHide EU server (from the EU hosts file).
# All candidates tested with CERT VERIFICATION ON (real browser behavior -
# verify-off probes gave false "200" on MITM proxies). Nothing valid found ->
# existing file untouched. Domain list = community-authoritative (12.11.2026 post).
import re
import socket
import ssl
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EU_URL = "https://raw.githubusercontent.com/Internet-Helper/GeoHideDNS/main/hosts/eu/hosts"
THREAD_URL = "https://github.com/Flowseal/zapret-discord-youtube/discussions/5552"
OUT = ROOT / "spotify_hosts.txt"
DOMAINS = [
    "spotify.dev", "www.spotify.dev", "spotify.com", "www.spotify.com",
    "api.spotify.com", "login5.spotify.com", "encore.scdn.co",
    "gew1-spclient.spotify.com", "spclient.wg.spotify.com",
    "api-partner.spotify.com", "aet.spotify.com", "accounts.spotify.com",
    "open.spotify.com", "accounts.scdn.co", "gew1-dealer.spotify.com",
    "www-growth.scdn.co", "scdn.co", "www.scdn.co", "i.scdn.co",
]
PROBE_DOMAIN = "api.spotify.com"
# IP immediately followed by a spotify/scdn domain in the thread HTML
PAIR_RE = re.compile(
    r"(\d{1,3}(?:\.\d{1,3}){3})\s*[\n\r]+\s*((?:[\w-]+\.)*(?:spotify\.(?:com|dev|io)|scdn\.co)\b)",
    re.I,
)


def fetch(url, timeout=60):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 hosts-merger"})
            return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", errors="replace")
        except Exception as e:
            if attempt == 2:
                print(f"  ! fetch failed {url}: {e}")
                return None
            time.sleep(4 + attempt * 4)


def fetch_thread_ip():
    """Parse discussion 5552 HTML: strip all tags, then find the LAST 'IP <domain>' pair
    (newest community post, best-effort) - or None."""
    html = fetch(THREAD_URL)
    if not html:
        return None
    text = re.sub(r"<[^>]+>", " ", html)  # strip HTML markup
    text = re.sub(r"[ \t]+", " ", text)
    pairs = re.findall(
        r"(\d{1,3}(?:\.\d{1,3}){3})\s*\n?\s*((?:[\w-]+\.)*(?:spotify\.(?:com|dev|io)|scdn\.co)\b)",
        text, re.I,
    )
    if pairs:
        ip, dom = pairs[-1]
        print(f"   thread 5552 parsed: latest community pair = {ip} {dom}")
        return ip
    print("   thread 5552: no IP+domain pairs found in fetched HTML")
    return None


def probe(ip, sni, timeout=6):
    """HTTP status through this IP for SNI=sni, CERT VERIFICATION ON."""
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((ip, 443), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=sni) as tls:
                tls.sendall(f"GET / HTTP/1.1\r\nHost: {sni}\r\nUser-Agent: Mozilla/5.0\r\nConnection: close\r\n\r\n".encode())
                data = tls.recv(128)
                if data.startswith(b"HTTP/"):
                    return data.split(b"\r\n", 1)[0].decode("utf-8", "replace")
    except OSError:
        pass
    return None


def last_known_ip():
    if not OUT.exists():
        return None
    for l in OUT.read_text(encoding="utf-8", errors="replace").splitlines():
        s = l.strip()
        if s and not s.startswith("#"):
            return s.split()[0]
    return None


def eu_servers():
    text = fetch(EU_URL)
    if not text:
        return []
    return sorted({p[0] for p in
                   (l.split("#", 1)[0].split() for l in text.splitlines())
                   if len(p) >= 2 and re.match(r"^\d{1,3}(\.\d{1,3}){3}$", p[0])})


def main():
    thread_ip = fetch_thread_ip()
    current = last_known_ip()

    candidates = []
    for c in [thread_ip, current]:
        if c and c not in candidates:
            candidates.append(c)
    for s in eu_servers():
        if s not in candidates:
            candidates.append(s)

    print(f"Testing {len(candidates)} candidates (cert verification ON), order: thread -> current -> GeoHide EU")
    picked = None
    for srv in candidates:
        st = probe(srv, PROBE_DOMAIN)
        tag = []
        if srv == thread_ip:
            tag.append("thread")
        if srv == current:
            tag.append("current")
        print(f"   {srv}: {st or 'DEAD/RST'}" + (f" [{','.join(tag)}]" if tag else ""))
        if st:
            picked = srv
            break

    if picked is None:
        print("no cert-valid server found - keeping existing file")
        return 1
    print(f"PICKED: {picked}" + (" (kept current)" if picked == current and picked != thread_ip else ""))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# AUTO-GENERATED by make_spotify.py - DO NOT EDIT BY HAND",
        f"# Domain list: {THREAD_URL} (2026-11-12 post); IP candidates: thread 5552 -> current -> GeoHide EU",
        f"# Generated: {now}",
        f"# Server: {picked} (cert-validated from this machine)",
        "",
    ]
    for d in DOMAINS:
        lines.append(f"{picked:<18} {d}")
    lines.append("")
    new_text = "\n".join(lines)
    strip = lambda s: [l for l in s.splitlines() if "Generated:" not in l]
    if OUT.exists() and strip(OUT.read_text(encoding="utf-8", errors="replace")) == strip(new_text):
        print(f"spotify_hosts.txt unchanged ({len(DOMAINS)} domains) - not rewritten")
        return 0
    OUT.write_text(new_text, encoding="utf-8", newline="\n")
    print(f"spotify_hosts.txt written: {len(DOMAINS)} domains on {picked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
