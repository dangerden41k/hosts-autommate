#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_hosts.py - merge multiple hosts-file sources into one deduplicated file,
grouped by service sections (publisher comments) and by server IP.

Usage:
  python merge_hosts.py [sources_file] [output_file]

sources_file: one URL (http/https) or local file path per line; '#' = comment.
Priority: sources listed earlier win on conflicts (same domain, different IPs).
"""
import ipaddress
import re
import sys
import urllib.request
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCES = ROOT / "sources.txt"
DEFAULT_OUTPUT = ROOT / "hosts"
USER_AGENT = "hosts-merger/1.0"

ENTRY_RE = re.compile(r"^\s*([^\s#]+)\s+(.+?)\s*$")
# section label: short plain text (letters/digits/spaces/dash), no dots/colons/URLs
LABEL_RE = re.compile(r"^[\w\-\s]{2,40}$")
LOCAL_DOMAINS = {"localhost", "localhost.localdomain", "ip6-localhost", "broadcasthost"}


def fix_label(label: str):
    """Keep clean labels, repair double-encoded ones (UTF-8 read as CP1251),
    reject mojibake with broken bytes -> caller falls back to IP grouping."""
    ok = re.compile(r"^[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9 \-]{1,39}$")
    if ok.match(label):
        return label
    try:
        repaired = label.encode("cp1251").decode("utf-8")
        if ok.match(repaired):
            return repaired
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return None


def source_tag(url_or_path: str) -> str:
    if re.match(r"^https?://", url_or_path, re.I):
        if "malw" in url_or_path:
            return "malw.link"
        if "GeoHideDNS" in url_or_path:
            m = re.search(r"/hosts/([a-z]{2})/", url_or_path)
            return "GeoHideDNS " + (m.group(1).upper() if m else "RU")
        m = re.search(r"//([^/]+)", url_or_path)
        return m.group(1) if m else url_or_path
    return Path(url_or_path).stem


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_entries(text: str, origin: str):
    """Return list of (ip, domain, section). Comment lines that look like plain
    short labels (e.g. '# OpenAI') become the section for following entries."""
    out = []
    section = None
    for n, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            label = stripped.lstrip("#").strip()
            if LABEL_RE.match(label):
                section = fix_label(label)
            continue
        line = stripped.split("#", 1)[0].strip()
        if not line:
            continue
        m = ENTRY_RE.match(line)
        if not m:
            print(f"  ! skip (no match) {origin}:{n}: {raw[:80]!r}")
            continue
        ip, domains = m.group(1), m.group(2)
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            print(f"  ! skip (bad ip) {origin}:{n}: {line[:80]!r}")
            continue
        for d in domains.split():
            d = d.lower().strip(".")
            if d:
                out.append((ip, d, section))
    return out


def merge(sources):
    """Dedupe within each source (first IP per domain wins), then merge across
    sources with first-source priority. Returns domain -> (ip, section, tag)."""
    by_domain = OrderedDict()
    conflicts = []
    total = dupes = intra = 0
    for tag, text in sources:
        seen = {}
        for ip, domain, section in parse_entries(text, tag):
            total += 1
            local = seen.get(domain)
            if local is None:
                seen[domain] = (ip, section)
            elif local[0] != ip:
                intra += 1
            else:
                dupes += 1
        for domain, (ip, section) in seen.items():
            prev = by_domain.get(domain)
            if prev is None:
                by_domain[domain] = (ip, section, tag)
            elif prev[0] == ip:
                dupes += 1
            else:
                conflicts.append((domain, prev[0], ip))
    return by_domain, total, dupes, intra, conflicts


def build_output(by_domain, tags):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# ============================================================",
        f"# Merged hosts file - generated {now} by hosts-merger",
        "# Sources (priority top-down):",
    ]
    lines += [f"#   {i + 1}. {t}" for i, t in enumerate(tags)]
    lines.append("# ============================================================")
    lines.append("")
    lines.append("127.0.0.1  localhost")
    lines.append("127.0.0.1  localhost.localdomain")
    lines.append("::1        localhost")
    lines.append("")

    # group: sections in appearance order, then IP groups, blocklist last
    groups = OrderedDict()
    for domain, (ip, section, tag) in by_domain.items():
        if domain in LOCAL_DOMAINS:
            continue
        if ip == "0.0.0.0":
            key = ("block", None)
        elif section:
            key = ("label", section)
        else:
            key = ("ip", ip)
        groups.setdefault(key, []).append((domain, ip, tag))

    ordered = [k for k in groups if k[0] != "block"] + [k for k in groups if k[0] == "block"]
    for key in ordered:
        entries = sorted(groups[key])
        first_tag = entries[0][2]
        if key[0] == "label":
            lines.append(f"# === {key[1]} ({first_tag}) ===")
        elif key[0] == "ip":
            plural = "s" if len(entries) != 1 else ""
            lines.append(f"# === {first_tag}: {key[1]} ({len(entries)} domain{plural}) ===")
        else:
            lines.append("# === Blocklist: ads and trackers (0.0.0.0) ===")
        for domain, ip, _ in entries:
            lines.append(f"{ip:<18} {domain}")
        lines.append("")
    return "\n".join(lines)


def main():
    argv = sys.argv[1:]
    sources_path = Path(argv[0]) if len(argv) > 0 else DEFAULT_SOURCES
    output_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUTPUT
    if not sources_path.is_absolute():
        sources_path = Path.cwd() / sources_path

    if not sources_path.exists():
        print(f"No sources file: {sources_path}")
        print("Create it with one URL or local path per line, e.g.:")
        print("  https://example.com/hosts")
        print("  https://raw.githubusercontent.com/user/repo/main/hosts")
        return 1

    urls = []
    for raw in sources_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            urls.append(line)
    if not urls:
        print(f"{sources_path} has no sources - add one URL or path per line.")
        return 1

    sources = []
    tags = []
    for u in urls:
        tag = source_tag(u)
        print(f"Fetching: {u}  [{tag}]")
        try:
            if re.match(r"^https?://", u, re.I):
                text = fetch(u)
            else:
                text = Path(u).read_text(encoding="utf-8", errors="replace")
            sources.append((tag, text))
            tags.append(tag)
        except Exception as e:
            print(f"  ! FAILED to load {u}: {e}")

    if not sources:
        print("No sources loaded - aborting without writing output.")
        return 1

    by_domain, total, dupes, intra, conflicts = merge(sources)
    out_text = build_output(by_domain, tags)
    output_path.write_text(out_text, encoding="utf-8", newline="\n")

    print()
    print(f"Loaded sources     : {len(sources)}")
    print(f"Raw entries        : {total}")
    print(f"Unique domains     : {len(by_domain)} (duplicates removed: {dupes})")
    if intra:
        print(f"Intra-source dupes : {intra} (same domain, different IPs in one source - first kept)")
    if conflicts:
        print(f"Cross-source conflicts : {len(conflicts)} (first source wins, first 10 shown)")
        for d, a, b in conflicts[:10]:
            print(f"  {d}: {a} kept, {b} ignored")
        if len(conflicts) > 10:
            print(f"  ... and {len(conflicts) - 10} more")
    print(f"Written            : {output_path} ({len(out_text.encode('utf-8'))} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
