import requests
from bs4 import BeautifulSoup
import os
import json

# 从环境变量读取飞书webhook地址
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK")

# 抓取Steam New & Trending榜单
def get_steam_games():
    url = "https://store.steampowered.com/explore/new/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "lxml")
    
    games = []
    items = soup.find_all("a", class_="tab_item")[:15]
    for item in items:
        name = item.find("div", class_="tab_item_name").text.strip()
        link = item["href"]
        img = item.find("img", class_="tab_item_cap_img")["src"]
        price_block = item.find("div", class_="discount_final_price")
        price = price_block.text.strip() if price_block else "免费"
        games.append({
            "name": name,
            "link": link,
            "img": img,
            "price": price
        })
    return games

# 单条卡片消息推送，使用飞书卡片支持图片直链显示
def push_to_feishu(games):
    elements = []
    
    # 添加标题
    elements.append({
        "tag": "markdown",
        "content": "## 📌 Steam New & Trending 最新榜单"
    })
    elements.append({"tag": "hr"})
    
    for game in games:
        elements.append({
            "tag": "column_set",
            "flex_mode": "none",
            "horizontal_spacing": "default",
            "background_style": "default",
            "columns": [
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 3,
                    "elements": [
                        {
                            "tag": "img",
                            "img_key": game["img"],
                            "alt": {
                                "tag": "plain_text",
                                "content": game["name"]
                            },
                            "scale_type": "fit_horizontal"
                        }
                    ]
                },
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 7,
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": f"**[{game['name']}]({game['link']})**\n💰 价格：{game['price']}"
                        }
                    ]
                }
            ]
        })
        elements.append({"tag": "hr"})
    
    # 组装飞书自定义机器人请求体，使用正确的卡片JSON 2.0结构
    data = {
        "msg_type": "interactive",
        "card": {
            "schema": "2.0",
            "header": {
                "template": "blue",
                "title": {
                    "content": "Steam New & Trending 最新榜单",
                    "tag": "plain_text"
                }
            },
            "body": {
                "elements": elements
            }
        }
    }
    
    headers = {"Content-Type": "application/json"}
    res = requests.post(FEISHU_WEBHOOK, headers=headers, data=json.dumps(data))
    result = res.json()
    
    if result.get("code") != 0:
        print(f"推送失败，错误信息：{result}")
        return False
    
    print("推送成功！所有图片已直接显示")
    return True

if __name__ == "__main__":
    print("开始执行 Steam 热门新品榜推送任务")
    games = get_steam_games()
    print(f"成功抓取当前热门新品榜前 {len(games)} 款游戏")
    push_to_feishu(games)
