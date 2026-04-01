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
    items = soup.find_all("a", class_="tab_item")[:20]
    for item in items:
        name = item.find("div", class_="tab_item_name").text.strip()
        link = item["href"]
        price_block = item.find("div", class_="discount_final_price")
        price = price_block.text.strip() if price_block else "免费"
        img = item.find("img", class_="tab_item_cap_img")["src"]
        games.append({
            "name": name,
            "link": link,
            "price": price,
            "img": img
        })
    return games

# 单条消息推送，使用文本格式，保留封面图
def push_to_feishu(games):
    content = "📌 Steam New & Trending 最新榜单\n\n"
    for idx, game in enumerate(games, 1):
        content += f"{idx}. {game['name']}\n"
        content += f"价格：{game['price']}\n"
        content += f"链接：{game['link']}\n"
        content += f"封面：{game['img']}\n\n"
    
    data = {
        "msg_type": "text",
        "content": {
            "text": content
        }
    }
    
    headers = {"Content-Type": "application/json"}
    res = requests.post(FEISHU_WEBHOOK, headers=headers, data=json.dumps(data))
    result = res.json()
    
    if result.get("code") != 0:
        print(f"推送失败，错误信息：{result}")
        return False
    print("推送成功！")
    return True

if __name__ == "__main__":
    print("开始执行 Steam 热门新品榜推送任务")
    games = get_steam_games()
    print(f"成功抓取当前热门新品榜前 {len(games)} 款游戏")
    push_to_feishu(games)
