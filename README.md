# IPTV Auto Fetch

基于 GitHub Actions 的 IPTV 直播源自动抓取更新。

## 功能

- ⏰ 每 6 小时自动抓取多个公开源
- 🔍 自动解析 M3U 格式、提取频道名和 URL
- 🔄 智能去重、按频道名排序
- 📦 输出 M3U/TXT/JSON 三种格式
- ⚡ 支持手动触发更新

## 部署

1. Fork 本仓库到你的 GitHub 账号
2. 仓库 → Settings → Secrets and variables → Actions：
   - 如使用私有仓库，添加 `GH_PAT` 为你的 Personal Access Token
3. 进入 Actions 标签页，手动触发一次验证
4. 后续每 6 小时自动运行

## 输出文件

| 文件 | 格式 | 说明 |
|------|------|------|
| `output/live.m3u` | M3U | 标准播放列表 |
| `output/channels.txt` | TXT | 频道名+URL，每行一个 |
| `output/channels.json` | JSON | 结构化数据 |

## 源列表

- iptv-org/iptv
- YueChan/Live
- fanmingming/live
- CCSH/IPTV
