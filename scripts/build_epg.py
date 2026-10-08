#!/usr/bin/env python3
"""
Builds a compact JSON TV guide for the Roku channel from a big XMLTV file.
Собирает компактную JSON-телепрограмму для Roku-канала из большого XMLTV.

Output (site/epg/):
  now.json          {tvgId: [[start, stop, title], ...]}  programmes around "now" for every channel
  c/<tvgId>.json    [[start, stop, title], ...]           archive window + 2 days ahead for one channel
  meta.json         build info
Times are Unix seconds (UTC). / Время — секунды Unix (UTC).
"""
import gzip, io, json, os, re, sys, time, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

PLAYLIST_URL = os.environ.get("PLAYLIST_URL", "")
PLAYLIST_FILE = os.environ.get("PLAYLIST_FILE", "")
EPG_URLS = [u.strip() for u in os.environ.get("EPG_URLS", "https://iptvx.one/epg/epg.xml.gz").split(",") if u.strip()]
OUT = os.environ.get("OUT_DIR", "site/epg")
NOW_AFTER = 6 * 3600       # now.json: what is on now + next 6 h / что идёт сейчас + 6 ч вперёд
FUTURE = 2 * 86400         # per-channel: 2 days ahead / 2 дня вперёд
UA = {"User-Agent": "Mozilla/5.0 (EPG builder)"}

ATTR = re.compile(r'([a-zA-Z0-9_-]+)="([^"]*)"')


def safe_name(tvg_id):
    # Must match safeEpgName() in the Roku app / Должно совпадать с safeEpgName() в Roku-приложении
    return re.sub(r"[^A-Za-z0-9_.-]", "_", tvg_id.lower())


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


def read_playlist():
    if PLAYLIST_FILE:
        text = open(PLAYLIST_FILE, encoding="utf-8", errors="replace").read()
    elif PLAYLIST_URL:
        text = fetch(PLAYLIST_URL).decode("utf-8", errors="replace")
    else:
        sys.exit("Set PLAYLIST_URL (secret) or PLAYLIST_FILE")
    chans = {}  # tvgId -> {days, names}
    for line in text.splitlines():
        if not line.startswith("#EXTINF"):
            continue
        a = {k.lower(): v for k, v in ATTR.findall(line)}
        tid = a.get("tvg-id", "")
        if not tid or tid.startswith("no_epg"):
            continue
        title = line.rsplit(",", 1)[-1].strip() if "," in line else ""
        days = int(a.get("catchup-days") or a.get("tvg-rec") or 1)
        c = chans.setdefault(tid, {"days": 0, "names": set()})
        c["days"] = max(c["days"], days)
        if title:
            c["names"].add(title.lower())
        if a.get("tvg-name"):
            c["names"].add(a["tvg-name"].lower())
    return chans


def xmltv_time(v):
    v = v.strip()
    fmt = "%Y%m%d%H%M%S %z" if len(v) > 14 else "%Y%m%d%H%M%S"
    dt = datetime.strptime(v if len(v) > 14 else v[:14], fmt)
    return int(dt.timestamp())


def main():
    now = int(time.time())
    chans = read_playlist()
    print(f"playlist: {len(chans)} channels with tvg-id")

    by_id = {k.lower(): k for k in chans}
    by_name = {}
    for k, c in chans.items():
        for n in c["names"]:
            by_name.setdefault(n, k)

    progs = {k: [] for k in chans}
    for url in EPG_URLS:
        print("downloading", url)
        data = fetch(url)
        print(f"  {len(data)/1e6:.1f} MB")
        xml_to_pl = {}  # XMLTV channel id -> playlist tvg-id
        mapped = set()
        for ev, el in ET.iterparse(io.BytesIO(data), events=("end",)):
            if el.tag == "channel":
                xid = el.get("id", "")
                target = by_id.get(xid.lower())
                if target is None:
                    for dn in el.findall("display-name"):
                        target = by_name.get((dn.text or "").strip().lower()) or by_id.get((dn.text or "").strip().lower())
                        if target:
                            break
                if target and target not in mapped:
                    xml_to_pl[xid] = target
                    mapped.add(target)
                el.clear()
            elif el.tag == "programme":
                target = xml_to_pl.get(el.get("channel", ""))
                if target:
                    try:
                        s = xmltv_time(el.get("start"))
                        e = xmltv_time(el.get("stop"))
                    except Exception:
                        el.clear()
                        continue
                    lo = now - chans[target]["days"] * 86400 - 3600
                    if e >= lo and s <= now + FUTURE:
                        t = el.findtext("title") or ""
                        progs[target].append([s, e, t.strip()])
                el.clear()
        del data

    os.makedirs(os.path.join(OUT, "c"), exist_ok=True)
    now_map = {}
    written = 0
    for k, lst in progs.items():
        if not lst:
            continue
        lst.sort(key=lambda p: p[0])
        with open(os.path.join(OUT, "c", safe_name(k) + ".json"), "w", encoding="utf-8") as f:
            json.dump(lst, f, ensure_ascii=False, separators=(",", ":"))
        written += 1
        near = [p for p in lst if p[1] >= now and p[0] <= now + NOW_AFTER]
        if near:
            now_map[k] = near
    with open(os.path.join(OUT, "now.json"), "w", encoding="utf-8") as f:
        json.dump(now_map, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(OUT, "meta.json"), "w") as f:
        json.dump({"generated": now, "channels": written, "sources": EPG_URLS}, f)
    open(os.path.join(os.path.dirname(OUT), "index.html"), "w").write("<p>EPG for Roku</p>")
    size = os.path.getsize(os.path.join(OUT, "now.json"))
    print(f"done: {written}/{len(chans)} channels have EPG, now.json {size/1e3:.0f} kB")


if __name__ == "__main__":
    main()
