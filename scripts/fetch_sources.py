#!/usr/bin/env python3
"""
IPTV Source Auto-Fetch Script
从多个公开源自动抓取、合并、去重国内直播频道 M3U 列表
"""

import os
import re
import json
import requests
from pathlib import Path
from urllib.parse import urlparse

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ============ 源配置 ============
SOURCES = {
    "iptv-org": "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/cn.m3u",
    "YueChan-Live": "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    "fanmingming-1": "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "fanmingming-2": "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv4.m3u",
    "CCSH": "https://raw.githubusercontent.com/CCSH/IPTV/main/live.m3u",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

TIMEOUT = 30


def fetch_m3u(name: str, url: str) -> list[str]:
    """获取单个 M3U 源，返回行列表"""
    try:
        print(f"  ▶ 正在获取 {name} ...")
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        lines = resp.text.splitlines()
        print(f"    ✓ {name}: {len(lines)} 行")
        return lines
    except Exception as e:
        print(f"    ✗ {name} 失败: {e}")
        return []


def parse_channels(lines: list[str]) -> list[dict]:
    """解析 M3U 格式，提取频道名和URL"""
    channels = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            # 提取频道名
            match = re.search(r'tvg-name="([^"]*)"', line)
            if not match:
                match = re.search(r'tvg-id="([^"]*)"', line)
            if not match:
                match = re.search(r'group-title="([^"]*)"', line)
            name_match = re.search(r',(.+)$', line)
            name = name_match.group(1).strip() if name_match else "未知频道"

            # 下一行是URL
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url and not url.startswith("#"):
                    channels.append({"name": name, "url": url})
            i += 2
        else:
            i += 1
    return channels


def deduplicate(channels: list[dict]) -> list[dict]:
    """按URL去重"""
    seen = set()
    result = []
    for ch in channels:
        key = ch["url"]
        if key not in seen:
            seen.add(key)
            result.append(ch)
    return result


def generate_m3u(channels: list[dict], path: Path):
    """生成 M3U 文件"""
    with open(path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"# Generated: auto-fetch\n")
        f.write(f"# Total: {len(channels)} channels\n\n")
        for ch in channels:
            f.write(f'#EXTINF:-1,{ch["name"]}\n')
            f.write(f'{ch["url"]}\n')
    print(f"  ✓ 已生成: {path} ({len(channels)} 个频道)")


def generate_txt(channels: list[dict], path: Path):
    """生成纯文本 URL 列表"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# IPTV Channel List - {len(channels)} channels\n\n")
        for ch in channels:
            f.write(f'{ch["name"]},{ch["url"]}\n')
    print(f"  ✓ 已生成: {path}")


def generate_json(channels: list[dict], path: Path):
    """生成 JSON 格式"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(channels, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 已生成: {path}")


def main():
    print("=" * 50)
    print("  IPTV Source Auto-Fetch")
    print("=" * 50)
    print()

    # Step 1: 获取所有源
    print("[Step 1] 获取源...")
    all_lines = []
    for name, url in SOURCES.items():
        lines = fetch_m3u(name, url)
        all_lines.extend(lines)
    print(f"\n  共获取 {len(all_lines)} 行原始数据")

    # Step 2: 解析频道
    print("\n[Step 2] 解析频道...")
    channels = parse_channels(all_lines)
    print(f"  解析出 {len(channels)} 个频道")

    # Step 3: 去重
    print("\n[Step 3] 去重...")
    channels = deduplicate(channels)
    print(f"  去重后 {len(channels)} 个频道")

    # Step 4: 按名称排序
    channels.sort(key=lambda x: x["name"])

    # Step 5: 生成输出文件
    print("\n[Step 4] 生成文件...")
    generate_m3u(channels, OUTPUT_DIR / "live.m3u")
    generate_m3u(channels, OUTPUT_DIR / "live.txt")  # 兼容格式
    generate_txt(channels, OUTPUT_DIR / "channels.txt")
    generate_json(channels, OUTPUT_DIR / "channels.json")

    # Step 6: 统计
    print("\n" + "=" * 50)
    print(f"  ✅ 完成! 共 {len(channels)} 个频道")
    print("=" * 50)


if __name__ == "__main__":
    main()
