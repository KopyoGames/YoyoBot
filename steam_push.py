import requests
import time
import json
import os
import base64
import re
from io import BytesIO
from datetime import datetime, timedelta, timezone

# 从环境变量读取配置
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")

# 解析 Steam 多种日期格式到东八区时间戳的辅助函数
def parse_steam_date_to_timestamp(date_str, tz_info):
    if not date_str:
        return 0
    # 匹配中文格式 "2024年3月28日" 或 "2024 年 3 月 28 日"
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", date_str)
    if m:
        y, mon, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return int(datetime(y, mon, d, tzinfo=tz_info).timestamp())
        
    # 匹配标准格式 "2024-03-28"
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
    if m:
        y, mon, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return int(datetime(y, mon, d, tzinfo=tz_info).timestamp())
        
    # 匹配英文格式 "28 Mar, 2024" 或 "Mar 28, 2024" (防备接口语言回退)
    months = {"Jan":1, "Feb":2, "Mar":3, "Apr":4, "May":5, "Jun":6, "Jul":7, "Aug":8, "Sep":9, "Oct":10, "Nov":11, "Dec":12}
    m = re.search(r"(\d{1,2})\s+([A-Z][a-z]{2}),\s+(\d{4})", date_str)
    if m:
        y, mon, d = int(m.group(3)), months.get(m.group(2), 1), int(m.group(1))
        return int(datetime(y, mon, d, tzinfo=tz_info).timestamp())
    m = re.search(r"([A-Z][a-z]{2})\s+(\d{1,2}),\s+(\d{4})", date_str)
    if m:
        y, mon, d = int(m.group(3)), months.get(m.group(1), 1), int(m.group(2))
        return int(datetime(y, mon, d, tzinfo=tz_info).timestamp())
        
    return 0

# 获取Steam新品榜单前30，筛选东八区昨天0点~今天0点内新发售的游戏
def get_steam_new_games():
    url = "https://store.steampowered.com/api/featuredcategories?cc=cn&l=zh"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()
        
        # 获取新品榜单前30
        new_releases = data.get("new_releases", {}).get("items", [])[:30]
        
        # 【修改点1】：强制使用 datetime 生成精确的东八区时间，摆脱服务器系统时区影响
        tz_utc_8 = timezone(timedelta(hours=8))
        now_utc8 = datetime.now(tz_utc_8)
        
        # 计算东八区今天0点和昨天0点
        today_zero_dt = now_utc8.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_zero_dt = today_zero_dt - timedelta(days=1)
        
        today_zero = int(today_zero_dt.timestamp())
        yesterday_zero = int(yesterday_zero_dt.timestamp())
        
        # 筛选【昨天0点 ~ 今天0点】之间发售的游戏
        yesterday_games = []
        for game in new_releases:
            release_date = game.get("release_date", {}).get("date", 0)
            release_timestamp = 0
            
            # 【修改点2】：兼容处理时间戳或多种格式的字符串
            if isinstance(release_date, int) and release_date > 0:
                release_timestamp = release_date
            elif isinstance(release_date, str):
                release_timestamp = parse_steam_date_to_timestamp(release_date, tz_utc_8)
                
            # 判断发售时间在东八区昨天24小时范围内
            if yesterday_zero <= release_timestamp < today_zero:
                yesterday_games.append(game)
                
        print(f"前30新品中找到 {len(yesterday_games)} 款昨天东八区全天新发售的游戏")
        return yesterday_games
    except Exception as e:
        print(f"获取Steam榜单失败：{str(e)}")
        return None

# 获取单个游戏的详情（含简介、封面图）
def get_game_detail(app_id):
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc=cn&l=zh"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()
        if not data[str(app_id)]["success"]:
            return {"desc": "暂无简介", "img_content": None}
        game_data = data[str(app_id)]["data"]
        desc = game_data.get("short_description", "暂无简介")
        # 获取封面图URL
        img_url = game_data.get("header_image", "")
        if img_url:
            # 下载图片内容
            img_res = requests.get(img_url, headers=headers, timeout=10)
            if img_res.status_code == 200:
                return {"desc": desc, "img_content": img_res.content}
        return {"desc": desc, "img_content": None}
    except Exception as e:
        print(f"获取游戏 {app_id} 详情失败：{str(e)}")
        return {"desc": "暂无简介", "img_content": None}

# 自定义机器人通过webhook推送，需要通过base64嵌入图片
def get_img_base64(img_content):
    if not img_content:
        return ""
    return base64.b64encode(img_content).decode("utf-8")

# 发送飞书卡片消息
def send_to_feishu_card(card):
    data = {
        "msg_type": "interactive",
        "card": card
    }
    try:
        res = requests.post(FEISHU_WEBHOOK, json=data, timeout=20)
        res.raise_for_status()
        result = res.json()
        print(f"飞书返回结果：{result}")
        return result
    except Exception as e:
        print(f"发送飞书消息失败：{str(e)}")
        return None

def main():
    games = get_steam_new_games()
    if games is None or len(games) == 0:
        print("昨天东八区全天没有符合条件的新发售游戏，终止推送")
        return
        
    # 【修改点3】：标题的昨日日期也强制使用东八区，防止服务器在UTC时间引起的日期漂移
    tz_utc_8 = timezone(timedelta(hours=8))
    yesterday_date = (datetime.now(tz_utc_8) - timedelta(days=1)).strftime("%Y-%m-%d")
        
    # 构建飞书卡片结构
    card = {
        "schema": "2.0",
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"📅 {yesterday_date} Steam昨日新发游戏汇总"
            },
            "template": "blue"
        },
        "body": {
            "elements": []
        }
    }
        
    # 逐个添加游戏信息
    for idx, game in enumerate(games, 1):
        name = game.get("name", "未知名称")
        app_id = game.get("id")
        if not app_id:
            continue
        # 获取游戏详情
        game_detail = get_game_detail(app_id)
        desc = game_detail["desc"]
        img_content = game_detail["img_content"]
        
        # 最多保留240字符约3行，超过截断
        if len(desc) > 240:
            desc = desc[:237] + "..."
        link = f"https://store.steampowered.com/app/{app_id}"
                
        # 添加游戏封面图：使用base64嵌入
        if img_content:
            img_base64 = get_img_base64(img_content)
            img_element = {
                "tag": "img",
                "img_key": f"data:image/jpeg;base64,{img_base64}",
                "scale_type": "fit_horizontal",
                "alt": {
                    "tag": "plain_text",
                    "content": f"{name}封面"
                }
            }
            card["body"]["elements"].append(img_element)
                
        # 添加游戏信息模块
        element = {
            "tag": "markdown",
            "content": f"**{idx}. {name}**\n{desc}\n[点击前往商店查看]({link})"
        }
        card["body"]["elements"].append(element)
        
        # 添加分隔线，最后一个游戏不加分隔线
        if idx != len(games):
            card["body"]["elements"].append({"tag": "hr"})

    # 添加统计信息
    update_time = datetime.now(tz_utc_8).strftime('%Y-%m-%d %H:%M:%S')
    info_text = f"本次共推送 {len(games)} 款昨日新发（东八区全天） | 更新时间：{update_time}"
    card["body"]["elements"].append({
        "tag": "markdown",
        "content": info_text,
        "text_size": "notation"
    })
        
    # 发送卡片消息
    result = send_to_feishu_card(card)
    if result and result.get("code") == 0:
        print("推送成功")
    else:
        print(f"推送失败：{result}")

if __name__ == "__main__":
    print("开始执行Steam昨日新发推送任务")
    main()
