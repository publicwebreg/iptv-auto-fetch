#!/usr/bin/env python3
"""
IPTV Source Auto-Fetch Script v3
从多个公开源自动抓取、合并、去重国内直播频道 M3U 列表
v3 改进：保留 tvg-logo/group-title/频道名中文/统一换行符 CRLF
"""
import os
import re
import json
import urllib.request
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
TIMEOUT = 10

# 源列表（fanmingming 从中国访问慢，放到最后或者跳过）
SOURCES = {
    "iptv-org": "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/cn.m3u",
    "YueChan": "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    "fanmingming-ipv6": "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TIMEOUT = 20


def fetch_m3u(name, url):
    """获取单个 M3U 源"""
    try:
        print(f"  ▶ 获取 {name} ...")
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        text = resp.read().decode("utf-8", errors="replace")
        # 统一换行为 \n
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = text.splitlines()
        print(f"    ✓ {name}: {len(lines)} 行")
        return lines
    except Exception as e:
        print(f"    ✗ {name} 失败: {e}")
        return []


# 单属性提取正则
ATTR_RE = re.compile(r'(tvg-id|tvg-name|tvg-logo|group-title)="([^"]*)"')

# 无意义频道名过滤
IGNORE_NAMES = {"\\", "n", "rj", "app", "xiaomi", "huawei", ""}


def parse_extinf(line):
    """解析 EXTINF 行，返回 (tags_dict, channel_name) 或 None"""
    if not line.startswith("#EXTINF:"):
        return None

    # 取最后一个逗号后面的文本作为频道名
    comma_idx = line.rfind(",")
    if comma_idx < 0:
        return None
    raw_name = line[comma_idx + 1:].strip()

    # 过滤无意义名称
    if not raw_name or raw_name.lower() in IGNORE_NAMES:
        return None
    if re.match(r'^\d{8}\s\d{2}:\d{2}$', raw_name):  # 日期时间
        return None

    # 取逗号之前的属性部分，逐个提取
    attr_part = line[:comma_idx]
    tags = {}
    for m in ATTR_RE.finditer(attr_part):
        key = m.group(1).replace("-", "_")  # tvg-id → tvg_id
        val = m.group(2).strip()
        if val:
            tags[key] = val

    return tags, raw_name


def parse_m3u(lines):
    """解析 M3U 格式，提取频道信息和URL，只保留 http/https"""
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

            # 下一行是 URL
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                # 只保留 http/https 流
                if url and (url.startswith("http://") or url.startswith("https://")):
                    # 过滤百度静态资源（有时效性）
                    if "bdstatic.com" in url or "baidu" in url.lower():
                        i += 2
                        continue
                    # 过滤明显无效的地址
                    if "127.0.0.1" in url or "localhost" in url:
                        i += 2
                        continue
                    channels.append({
                        "name": ch_name,
                        "url": url,
                        "tvg_id": tags.get("tvg_id", ""),
                        "tvg_name": tags.get("tvg_name", ""),
                        "tvg_logo": tags.get("tvg_logo", ""),
                        "group_title": tags.get("group_title", ""),
                    })
            i += 2
        else:
            i += 1
    return channels


def check_url(url):
    """快速检测URL是否可访问（HEAD请求）"""
    try:
        req = urllib.request.Request(url, method="HEAD", headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status == 200
    except Exception:
        return False


def validate_channels(channels):
    """并发检测频道有效性"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    print(f"\n  [存活检测] 共 {len(channels)} 个频道，正在检测...")
    valid = []

    def check(ch):
        if check_url(ch["url"]):
            return ch
        return None

    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(check, ch): ch for ch in channels}
        done = 0
        for future in as_completed(futures):
            done += 1
            if done % 200 == 0:
                print(f"    已检测 {done}/{len(channels)}...")
            result = future.result()
            if result:
                valid.append(result)

    print(f"    ✓ 存活: {len(valid)}/{len(channels)}")
    return valid


def deduplicate(channels):
    """按URL去重（同URL保留第一个）"""
    seen = set()
    result = []
    for ch in channels:
        key = ch["url"]
        if key not in seen:
            seen.add(key)
            result.append(ch)
    return result


def generate_m3u(channels, path):
    """生成标准 M3U 文件，保留 tvg-logo/group-title"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"# Generated: IPTV Auto-Fetch v3\n")
        f.write(f"# Date: {now}\n")
        f.write(f"# Total: {len(channels)} channels\n\n")
        for ch in channels:
            # 构建带属性的 EXTINF
            attrs = []
            if ch.get("tvg_id"):
                attrs.append(f'tvg-id="{ch["tvg_id"]}"')
            if ch.get("tvg_name"):
                attrs.append(f'tvg-name="{ch["tvg_name"]}"')
            if ch.get("tvg_logo"):
                attrs.append(f'tvg-logo="{ch["tvg_logo"]}"')
            if ch.get("group_title"):
                attrs.append(f'group-title="{ch["group_title"]}"')

            attr_str = " ".join(attrs)
            if attr_str:
                f.write(f'#EXTINF:-1 {attr_str},{ch["name"]}\n')
            else:
                f.write(f'#EXTINF:-1,{ch["name"]}\n')
            f.write(f'{ch["url"]}\n')
    print(f"  ✓ 生成: {path} ({len(channels)} 个频道)")


def categorize_channels(channels):
    """按 group_title 或频道名分类"""
    cctv = []
    ws = []
    other = []
    cctv_kw = {"央视", "cctv", "CCTV"}
    ws_kw = {"卫视", "东南", "湖南", "浙江", "江苏", "北京", "东方", "广东",
             "深圳", "天津", "重庆", "山东", "安徽", "江西", "福建",
             "深圳", "哈尔滨", "辽宁", "黑龙江", "旅游", "海南", "河北",
             "河南", "湖北", "广西", "四川", "贵州", "云南", "陕西",
             "甘肃", "宁夏", "青海", "西藏", "新疆", "内蒙古",
             "卫视", "Sichuan", "Guangdong", "Jiangsu", "Zhejiang"}

    for ch in channels:
        grp = ch.get("group_title", "")
        name = ch["name"]
        # 先看 group_title
        if any(k in grp for k in cctv_kw):
            cctv.append(ch)
        elif any(k in name for k in ("CCTV", "cctv", "央视")):
            cctv.append(ch)
        elif any(k in grp for k in ws_kw):
            ws.append(ch)
        elif any(k in name for k in ws_kw):
            ws.append(ch)
        else:
            other.append(ch)
    return cctv, ws, other


import sys

def main():
    print("=" * 55, flush=True)
    print("  IPTV Source Auto-Fetch v3", flush=True)
    print("  保留台标/分组/中文名", flush=True)
    print("=" * 55, flush=True)
    print(flush=True)

    # Step 1: 获取源
    print("[Step 1] 获取源...")
    all_lines = []
    for name, url in SOURCES.items():
        lines = fetch_m3u(name, url)
        all_lines.extend(lines)
    print(f"\n  共获取 {len(all_lines)} 行原始数据")

    # Step 2: 解析频道
    print("\n[Step 2] 解析频道...")
    channels = parse_m3u(all_lines)
    print(f"  解析出 {len(channels)} 个频道")

    # Step 3: 去重
    print("\n[Step 3] 去重...")
    channels = deduplicate(channels)
    print(f"  去重后 {len(channels)} 个")

    if len(channels) == 0:
        print("\n  ❌ 没有解析到任何频道，请检查源是否可访问")
        return

    # Step 4: 存活检测（可选跳过）
    print("\n[Step 4] 存活检测...")
    # 先不启用存活检测，保留全部频道
    valid = channels

    # Step 5: 分类
    print("\n[Step 5] 分类...")
    cctv, ws, other = categorize_channels(valid)
    print(f"  CCTV类: {len(cctv)}, 卫视类: {len(ws)}, 其他: {len(other)}")

    # 按名称排序
    def sort_key(ch):
        name = ch["name"]
        # 数字优先
        m = re.search(r'(\d+)', name)
        num = int(m.group(1)) if m else 999
        return (not bool(m), num, name)

    for lst in [valid, cctv, ws, other]:
        lst.sort(key=sort_key)

    # Step 6: 生成文件
    print("\n[Step 6] 生成文件...")
    generate_m3u(valid, OUTPUT_DIR / "live.m3u")
    generate_m3u(cctv, OUTPUT_DIR / "cctv.m3u")
    generate_m3u(ws, OUTPUT_DIR / "weishi.m3u")

    # 生成 JSON
    with open(OUTPUT_DIR / "channels.json", "w", encoding="utf-8") as f:
        json.dump(valid, f, ensure_ascii=False, indent=2)

    # 统计
    with_logo = sum(1 for ch in valid if ch.get("tvg_logo"))
    with_group = sum(1 for ch in valid if ch.get("group_title"))
    print(f"\n  📊 元数据统计:")
    print(f"     有台标(tvg-logo): {with_logo}/{len(valid)}")
    print(f"     有分组(group-title): {with_group}/{len(valid)}")

    print("\n" + "=" * 55)
    print(f"  ✅ 完成! 共 {len(valid)} 个频道")
    print(f"     ├ CCTV: {len(cctv)}")
    print(f"     ├ 卫视: {len(ws)}")
    print(f"     └ 其他: {len(other)}")
    print("=" * 55)


if __name__ == "__main__":
    main()
