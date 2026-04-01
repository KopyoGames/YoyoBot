import requests
import json
import os
import base64
from datetime import datetime, timedelta, timezone

# 从环境变量读取配置
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")

# 获取Steam热门新品榜单前20
def get_steam_trending_games():
    url = "https://store.steampowered.com/api/featuredcategories?cc=cn&l=zh"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()
        
        # 直接获取 New & Trending (热门新品) 榜单前20名
        trending_games = data.get("new_releases", {}).get("items", [])[:10]
        
        print(f"成功抓取当前热门新品榜前 {len(trending_games)} 款游戏")
        return trending_games
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
    games = get_steam_trending_games()
    if not games:
        print("未获取到榜单游戏，终止推送")
        return
        
    # 获取东八区当前时间
    tz_utc_8 = timezone(timedelta(hours=8))
    now_utc8 = datetime.now(tz_utc_8)
    current_date = now_utc8.strftime("%Y-%m-%d")
        
    # 构建飞书卡片结构，调整标题和文案
    card = {
        "schema": "2.0",
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"🔥 {current_date} Steam 热门新品榜 Top 20"
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
    update_time = now_utc8.strftime('%Y-%m-%d %H:%M:%S')
    info_text = f"本次共推送 {len(games)} 款当前热门新品 | 更新时间：{update_time}"
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
    print("开始执行 Steam 热门新品榜推送任务")
    main()
