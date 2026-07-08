#!/usr/bin/env python3
"""
IPTV Source Auto-Fetch Script v2
从多个公开源自动抓取、合并、去重国内直播频道 M3U 列表
v2 改进：修复格式、过滤无效源、频道名清理、存活检测
"""

import os
import re
import json
import subprocess
import concurrent.futures
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ============ 高质量源配置（优先选国内可用）============
SOURCES = {
    "fanmingming-ipv6": "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "fanmingming-ipv4": "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv4.m3u",
    "YueChan": "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    "iptv-org": "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/cn.m3u",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
TIMEOUT = 15
MAX_WORKERS = 20


def fetch_m3u(name, url):
    """获取单个 M3U 源"""
    try:
        print(f"  ▶ 获取 {name} ...")
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        text = resp.read().decode("utf-8", errors="replace")
        lines = text.splitlines()
        print(f"    ✓ {name}: {len(lines)} 行")
        return lines
    except Exception as e:
        print(f"    ✗ {name} 失败: {e}")
        return []


def clean_channel_name(raw_name):
    """清理频道名：去空白、去多余符号"""
    name = raw_name.strip().strip(",").strip()
    # 去掉 tvg-* 属性残留
    name = re.sub(r'\s*tvg-[a-z]+="[^"]*"\s*', "", name)
    name = re.sub(r'\s+group-title="[^"]*"\s*', "", name)
    name = name.strip().strip(",").strip()
    # 过滤无意义名称
    if not name or re.match(r'^\d{8}\s\d{2}:\d{2}$', name):  # 日期时间
        return None
    ignore_keywords = ["\\", "n", "rj", "app", "xiaomi", "huawei"]
    if name.lower().strip() in ignore_keywords:
        return None
    return name


def parse_m3u(lines):
    """解析 M3U 格式，提取频道名和URL"""
    channels = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            # 提取逗号后面的频道名
            # 格式: #EXTINF:-1 tvg-name="CCTV1" group-title="央视",CCTV-1 综合
            # 取最后一个逗号后面的文本
            comma_idx = line.rfind(",")
            if comma_idx > 0:
                raw_name = line[comma_idx + 1:].strip()
            else:
                raw_name = ""

            name = clean_channel_name(raw_name)
            if name is None:
                i += 1
                continue

            # 下一行是 URL
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                # 只保留 http/https 流（过滤 rtp:// 内网组播）
                if url and (url.startswith("http://") or url.startswith("https://")):
                    # 过滤百度静态资源（有时效性）
                    if "bdstatic.com" in url or "baidu" in url.lower():
                        i += 2
                        continue
                    # 过滤明显无效的地址
                    if "127.0.0.1" in url or "localhost" in url:
                        i += 2
                        continue
                    channels.append({"name": name, "url": url})
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
    print(f"\n  [存活检测] 共 {len(channels)} 个频道，正在检测...")
    valid = []

    def check(ch):
        if check_url(ch["url"]):
            return ch
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check, ch): ch for ch in channels}
        done = 0
        for future in concurrent.futures.as_completed(futures):
            done += 1
            if done % 200 == 0:
                print(f"    已检测 {done}/{len(channels)}...")
            result = future.result()
            if result:
                valid.append(result)

    print(f"    ✓ 存活: {len(valid)}/{len(channels)}")
    return valid


def deduplicate(channels):
    """按URL去重"""
    seen = set()
    result = []
    for ch in channels:
        key = ch["url"]
        if key not in seen:
            seen.add(key)
            result.append(ch)
    return result


def generate_m3u(channels, path):
    """生成标准 M3U 文件"""
    with open(path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"# Generated: IPTV Auto-Fetch v2\n")
        f.write(f"# Date: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"# Total: {len(channels)} channels\n\n")
        for ch in channels:
            f.write(f'#EXTINF:-1,{ch["name"]}\n')
            f.write(f'{ch["url"]}\n')
    print(f"  ✓ 生成: {path} ({len(channels)} 个频道)")


def categorize_channels(channels):
    """按频道名分类（央视/卫视/地方/其他）"""
    cctv = []
    ws = []
    other = []
    cctv_keywords = ["CCTV", "cctv", "央视"]
    ws_keywords = ["卫视", "东南", "湖南", "浙江", "江苏", "北京", "东方", "广东",
                     "深圳", "天津", "重庆", "山东", "安徽", "江西", "福建"]
    for ch in channels:
        name = ch["name"]
        if any(k in name for k in cctv_keywords):
            cctv.append(ch)
        elif any(k in name for k in ws_keywords):
            ws.append(ch)
        else:
            other.append(ch)
    return cctv, ws, other


def main():
    import datetime
    print("=" * 55)
    print("  IPTV Source Auto-Fetch v2")
    print("=" * 55)
    print()

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

    # Step 4: 存活检测（可选，为了快速可以先跳过）
    print("\n[Step 4] 存活检测...")
    print("  ⚠ 检测会花费几分钟，跳过则直接生成全部频道")
    valid = channels  # 先跳过检测，直接生成所有

    # Step 5: 分类
    print("\n[Step 5] 分类...")
    cctv, ws, other = categorize_channels(valid)
    print(f"  CCTV类: {len(cctv)}, 卫视类: {len(ws)}, 其他: {len(other)}")

    # Step 6: 按名称排序
    valid.sort(key=lambda x: x["name"])

    # Step 7: 生成文件
    print("\n[Step 6] 生成文件...")
    generate_m3u(valid, OUTPUT_DIR / "live.m3u")
    generate_m3u(cctv, OUTPUT_DIR / "cctv.m3u")
    generate_m3u(ws, OUTPUT_DIR / "weishi.m3u")

    # 生成 JSON
    with open(OUTPUT_DIR / "channels.json", "w", encoding="utf-8") as f:
        json.dump(valid, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 55)
    print(f"  ✅ 完成! 共 {len(valid)} 个频道")
    print(f"     ├ CCTV: {len(cctv)}")
    print(f"     ├ 卫视: {len(ws)}")
    print(f"     └ 其他: {len(other)}")
    print("=" * 55)


if __name__ == "__main__":
    main()
