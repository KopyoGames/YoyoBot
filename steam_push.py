import requests
import time
import json
import os

# 从环境变量读取配置
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")

# 获取Steam新品榜单前10
def get_steam_new_games():
    url = "https://store.steampowered.com/api/featuredcategories?cc=cn&l=zh"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    res = requests.get(url, headers=headers)
    data = res.json()
    # 获取新品榜单
    new_releases = data.get("new_releases", {}).get("items", [])
    # 取前10个
    return new_releases[:10]

# 发送飞书卡片消息
def send_to_feishu_card(card):
    data = {
        "msg_type": "interactive",
        "card": card
    }
    res = requests.post(FEISHU_WEBHOOK, json=data)
    return res.json()

def main():
    games = get_steam_new_games()
    if not games:
        print("获取榜单失败")
        return
    
    # 构建飞书卡片结构
    card = {
        "schema": "2.0",
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "📌 今日Steam新品榜单Top10"
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
        price = game.get("price_overview", {}).get("final_formatted", "无价格信息")
        link = f"https://store.steampowered.com/app/{game.get('id')}"
        
        # 添加游戏信息模块
        element = {
            "tag": "markdown",
            "content": f"**{idx}. {name}**\n价格：{price}\n[点击前往商店查看]({link})"
        }
        card["body"]["elements"].append(element)
        # 添加分隔线，最后一个游戏不加分隔线
        if idx != len(games):
            card["body"]["elements"].append({"tag": "hr"})
    
    # 添加更新时间
    time_text = f"数据更新时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}"
    card["body"]["elements"].append({
        "tag": "note",
        "elements": [
            {
                "tag": "plain_text",
                "content": time_text
            }
        ]
    })
    
    # 发送卡片消息
    result = send_to_feishu_card(card)
    print(result)

if __name__ == "__main__":
    main()
