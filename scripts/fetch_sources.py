#!/usr/bin/env python3
"""
IPTV Source Auto-Fetch Script v4
核心改进：存活检测 + 只保留可播源
"""
import os, re, json, sys, subprocess
import urllib.request
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

SOURCES = {
    "iptv-org": "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/cn.m3u",
    "YueChan": "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    "fanmingming": "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
}

# ============ 已知可用的高质量回退源 ============
FALLBACK = [
    # (频道名, URL, group_title, tvg_logo)
    # CCTV 各频道（多路源）
    ("CCTV-1综合", "https://liveplay-srs.voc.com.cn/hls/tv/134_180adf.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV1.png"),
    ("CCTV-1综合", "http://69.30.245.50/live/cctv1.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV1.png"),
    ("CCTV-1综合", "http://198.204.240.250:82/live/cctv1.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV1.png"),
    ("CCTV-1综合", "http://74.91.26.218:82/live/cctv1hd.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV1.png"),
    ("CCTV-2财经", "http://74.91.26.218:82/live/cctv2hd.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV2.png"),
    ("CCTV-3综艺", "http://74.91.26.218:82/live/cctv3hd.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV3.png"),
    ("CCTV-4中文国际", "http://74.91.26.218:82/live/cctv4hd.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV4.png"),
    ("CCTV-4K", "http://198.204.240.250:82/live/cctv4k.m3u8", "央视频道", ""),
    ("CCTV-6电影", "http://69.30.245.50/live/cctv6.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV6.png"),
    ("CCTV-6电影", "http://198.204.240.250:82/live/cctv6.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV6.png"),
    ("CCTV-7国防军事", "http://74.91.26.218:82/live/cctv7hd.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV7.png"),
    ("CCTV-8电视剧", "http://74.91.26.218:82/live/cctv8hd.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV8.png"),
    ("CCTV-8K", "http://192.151.150.154/live/cctv8k.m3u8", "央视频道", ""),
    ("CCTV-8K", "http://198.204.240.250:82/live/cctv8k.m3u8", "央视频道", ""),
    ("CCTV-9纪录", "https://xykt-fix.github.io/Y77.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV9.png"),
    ("CCTV-10科教", "http://74.91.26.218:82/live/cctv10hd.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV10.png"),
    ("CCTV-11戏曲", "http://74.91.26.218:82/live/cctv11hd.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV11.png"),
    ("CCTV-11戏曲", "https://xykt-fix.github.io/play/a02b/index.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV11.png"),
    ("CCTV-12社会与法", "http://74.91.26.218:82/live/cctv12hd.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV12.png"),
    ("CCTV-13新闻", "http://74.91.26.218:82/live/cctv13hd.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV13.png"),
    ("CCTV-14少儿", "http://74.91.26.218:82/live/cctv14hd.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV14.png"),
    ("CCTV-15音乐", "http://74.91.26.218:82/live/cctv15hd.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV15.png"),
    ("CCTV-15音乐", "https://xykt-fix.github.io/play/a02e/index.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV15.png"),
    ("CCTV-16奥林匹克", "http://74.91.26.218:82/live/cctv16hd.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV16.png"),
    ("CCTV-17农业农村", "http://74.91.26.218:82/live/cctv17hd.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CCTV17.png"),
    # CGTN
    ("CGTN英语", "https://english-livetx.cgtn.com/hls/yypdyyctzb_hd.m3u8", "央视频道", "https://live.fanmingming.cn/tv/CGTN.png"),
    ("CGTN纪录", "https://docu-livetx.cgtn.com/hls/yspdydzb/yspdydzb_hd.m3u8", "央视频道", ""),
    # 其他频道
    ("Ando TV", "http://play.kankanlive.com/live/1711956137852982.m3u8", "其他", ""),
    ("面包台 Bread TV", "https://video.bread-tv.com:8091/hls-live24/online/index.m3u8", "其他", ""),
    ("之江纪录", "https://zhjliveback.cztv.com/livezb/ggnew/ggnew.m3u8", "浙江", ""),
    ("浙江国际", "https://zhjliveback.cztv.com/livezb/gjnew/gjnew.m3u8", "浙江", ""),
    ("浙江少儿", "https://zhjliveback.cztv.com/livezb/shaoernew/shaoernew.m3u8", "浙江", ""),
    ("浙江教科", "https://zhjliveback.cztv.com/livezb/jknew/jknew.m3u8", "浙江", ""),
    ("浙江民生", "https://zhjliveback.cztv.com/livezb/msnew/msnew.m3u8", "浙江", ""),
    ("浙江经济", "https://zhjliveback.cztv.com/livezb/jjnew/jjnew.m3u8", "浙江", ""),
    ("浙江新闻", "https://zhjliveback.cztv.com/livezb/xwnew/xwnew.m3u8", "浙江", ""),
    ("浙江钱江", "https://zhjliveback.cztv.com/livezb/qjnew/qjnew.m3u8", "浙江", ""),
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TIMEOUT = 10
HEALTH_TIMEOUT = 4  # 存活检测超时（秒）

# ============ 工具函数 ============

def fetch_m3u(name, url):
    print(f"  ▶ 获取 {name} ...", flush=True)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        text = resp.read().decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
        print(f"    ✓ {name}: {len(text.splitlines())} 行", flush=True)
        return text.splitlines()
    except Exception as e:
        print(f"    ✗ {name}: {e}", flush=True)
        return []


ATTR_RE = re.compile(r'(tvg-id|tvg-name|tvg-logo|group-title)="([^"]*)"')
IGNORE_NAMES = {"\\", "n", "rj", "app", "xiaomi", "huawei", ""}


def parse_extinf(line):
    if not line.startswith("#EXTINF:"):
        return None
    comma_idx = line.rfind(",")
    if comma_idx < 0:
        return None
    raw_name = line[comma_idx + 1:].strip()
    if not raw_name or raw_name.lower() in IGNORE_NAMES:
        return None
    if re.match(r'^\d{8}\s\d{2}:\d{2}$', raw_name):
        return None
    tags = {}
    for m in ATTR_RE.finditer(line[:comma_idx]):
        key = m.group(1).replace("-", "_")
        val = m.group(2).strip()
        if val:
            tags[key] = val
    return tags, raw_name


def parse_m3u(lines):
    channels = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            result = parse_extinf(line)
            if result is None:
                i += 1
                continue
            tags, ch_name = result
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url and (url.startswith("http://") or url.startswith("https://")):
                    if "bdstatic.com" in url or "baidu" in url.lower():
                        i += 2; continue
                    if "127.0.0.1" in url or "localhost" in url:
                        i += 2; continue
                    # 过滤 fanmingming IPv6 (移动内网 403)
                    if "2409:8087:" in url:
                        i += 2; continue
                    channels.append({
                        "name": ch_name, "url": url,
                        "tvg_id": tags.get("tvg_id", ""),
                        "tvg_name": tags.get("tvg_name", ""),
                        "tvg_logo": tags.get("tvg_logo", ""),
                        "group_title": tags.get("group_title", ""),
                    })
            i += 2
        else:
            i += 1
    return channels


def health_check(ch):
    """curl 检测频道是否可访问（更可靠超时）"""
    try:
        result = subprocess.run(
            ["curl", "-sI", "--connect-timeout", "3", "--max-time", "5",
             "-A", "Mozilla/5.0", "-o", "/dev/null", "-w", "%{http_code}",
             ch["url"]],
            capture_output=True, text=True, timeout=8
        )
        code = result.stdout.strip()
        return code == "200" or code == "302" or code == "301"
    except Exception:
        return False


def add_fallback(channels):
    """加入已知可用的回退源，同URL合并元数据"""
    existing = {ch["url"]: ch for ch in channels}
    for name, url, group, logo in FALLBACK:
        if url in existing:
            # 合并：用 fallback 的台标和分组覆盖
            ch = existing[url]
            if logo and not ch.get("tvg_logo"):
                ch["tvg_logo"] = logo
            if not ch.get("group_title"):
                ch["group_title"] = group
            if not ch.get("tvg_name"):
                ch["tvg_name"] = name
        else:
            channels.append({
                "name": name, "url": url,
                "tvg_id": "", "tvg_name": name,
                "tvg_logo": logo, "group_title": group,
            })
    return channels


def deduplicate(channels):
    seen = set()
    result = []
    for ch in channels:
        if ch["url"] not in seen:
            seen.add(ch["url"])
            result.append(ch)
    return result


def gen_m3u(channels, path, label=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"# Generated: IPTV Auto-Fetch v4 {label}\n")
        f.write(f"# Date: {now}\n")
        f.write(f"# Total: {len(channels)} channels\n\n")
        for ch in channels:
            attrs = []
            if ch.get("tvg_id"):    attrs.append(f'tvg-id="{ch["tvg_id"]}"')
            if ch.get("tvg_name"):  attrs.append(f'tvg-name="{ch["tvg_name"]}"')
            if ch.get("tvg_logo"):  attrs.append(f'tvg-logo="{ch["tvg_logo"]}"')
            if ch.get("group_title"): attrs.append(f'group-title="{ch["group_title"]}"')
            attr_str = " ".join(attrs)
            f.write(f'#EXTINF:-1 {attr_str},{ch["name"]}\n' if attr_str else f'#EXTINF:-1,{ch["name"]}\n')
            f.write(f'{ch["url"]}\n')
    print(f"  ✓ {path} ({len(channels)} 个频道)", flush=True)


def categorize(channels):
    cctv, ws, other = [], [], []
    for ch in channels:
        grp = ch.get("group_title", "")
        name = ch["name"]
        if "央视" in grp or "CCTV" in grp or "CCTV" in name or "cctv" in name:
            cctv.append(ch)
        elif "卫视" in grp or any(k in name for k in ("卫视", "东南", "湖南", "浙江", "江苏",
                    "北京", "东方", "广东", "深圳", "天津", "重庆", "山东",
                    "安徽", "江西", "福建", "四川", "贵州", "云南", "陕西",
                    "辽宁", "黑龙江", "湖北", "河南", "海南", "河北", "广西")):
            ws.append(ch)
        else:
            other.append(ch)
    return cctv, ws, other


def sort_key(ch):
    name = ch["name"]
    m = re.search(r'(\d+)', name)
    num = int(m.group(1)) if m else 999
    return (not bool(m), num, name)


def main():
    print("=" * 55, flush=True)
    print("  IPTV Source Auto-Fetch v4", flush=True)
    print("  存活检测 + 仅保留可播源", flush=True)
    print("=" * 55, flush=True)

    # Step 1: 获取源
    print("\n[Step 1] 获取源...", flush=True)
    all_lines = []
    for name, url in SOURCES.items():
        all_lines.extend(fetch_m3u(name, url))
    print(f"\n  共 {len(all_lines)} 行原始数据", flush=True)

    # Step 2: 解析
    print("\n[Step 2] 解析频道...", flush=True)
    channels = parse_m3u(all_lines)
    print(f"  解析出 {len(channels)} 个频道", flush=True)

    # Step 3: 去重
    channels = deduplicate(channels)
    print(f"  去重后 {len(channels)} 个", flush=True)

    # Step 4: 加入已知可用回退源
    print("\n[Step 3] 加入已知可用源...", flush=True)
    channels = add_fallback(channels)
    print(f"  加入后共 {len(channels)} 个", flush=True)

    # Step 5: 存活检测（并发）
    print("\n[Step 4] 存活检测...", flush=True)
    print(f"  测试 {len(channels)} 个频道...", flush=True)
    valid = []

    def check(ch):
        return (health_check(ch), ch)

    with ThreadPoolExecutor(max_workers=30) as ex:
        futures = {ex.submit(check, ch): ch["name"] for ch in channels}
        done = 0
        for future in as_completed(futures):
            name = futures[future]
            done += 1
            try:
                alive, ch = future.result(timeout=8)
                if alive:
                    valid.append(ch)
            except Exception:
                pass  # 超时/异常的视为不可播
            if done % 30 == 0 or done == len(channels):
                print(f"    {done}/{len(channels)}... ✅{len(valid)}", flush=True)
    print(f"\n  ✅ 可播: {len(valid)}/{len(channels)}", flush=True)

    if len(valid) == 0:
        print("\n  ❌ 全部不可播！", flush=True)
        # 至少输出 fallback
        valid = [{"name": n, "url": u, "tvg_id": "", "tvg_name": n,
                   "tvg_logo": l, "group_title": g}
                 for n, u, g, l in FALLBACK]

    # Step 6: 分类
    print("\n[Step 5] 分类...", flush=True)
    cctv, ws, other = categorize(valid)
    print(f"  CCTV: {len(cctv)}, 卫视: {len(ws)}, 其他: {len(other)}", flush=True)

    for lst in [valid, cctv, ws, other]:
        lst.sort(key=sort_key)

    # Step 7: 生成文件
    print("\n[Step 6] 生成文件...", flush=True)
    gen_m3u(valid, OUTPUT_DIR / "live.m3u")
    gen_m3u(cctv, OUTPUT_DIR / "cctv.m3u")
    gen_m3u(ws, OUTPUT_DIR / "weishi.m3u")

    with open(OUTPUT_DIR / "channels.json", "w", encoding="utf-8") as f:
        json.dump(valid, f, ensure_ascii=False, indent=2)

    with_logo = sum(1 for ch in valid if ch.get("tvg_logo"))
    with_group = sum(1 for ch in valid if ch.get("group_title"))
    print(f"\n  📊 统计: {len(valid)} 频道, 台标 {with_logo}, 分组 {with_group}", flush=True)
    print("=" * 55, flush=True)


if __name__ == "__main__":
    main()
