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
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()
        # 获取新品榜单
        new_releases = data.get("new_releases", {}).get("items", [])
        # 取前10个
        print(f"成功获取到 {len(new_releases)} 款新品")
        return new_releases[:10]
    except Exception as e:
        print(f"获取Steam榜单失败：{str(e)}")
        return None

# 发送飞书卡片消息
def send_to_feishu_card(card):
    data = {
        "msg_type": "interactive",
        "card": card
    }
    try:
        res = requests.post(FEISHU_WEBHOOK, json=data, timeout=10)
        res.raise_for_status()
        result = res.json()
        print(f"飞书返回结果：{result}")
        return result
    except Exception as e:
        print(f"发送飞书消息失败：{str(e)}")
        return None

def main():
    games = get_steam_new_games()
    if not games:
        print("未获取到游戏数据，终止推送")
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
        desc = game.get("short_description", "暂无简介")
        # 如果简介太长就截断，保证卡片美观
        if len(desc) > 80:
            desc = desc[:77] + "..."
        app_id = game.get("id")
        if not app_id:
            continue
        link = f"https://store.steampowered.com/app/{app_id}"
        
        # 添加游戏信息模块
        element = {
            "tag": "markdown",
            "content": f"**{idx}. {name}**\n{desc}\n[点击前往商店查看]({link})"
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
    if result and result.get("code") == 0:
        print("推送成功")
    else:
        print(f"推送失败：{result}")

if __name__ == "__main__":
    print("开始执行Steam新品推送任务")
    main()
