import requests
from bs4 import BeautifulSoup
import os
import json
import io
from PIL import Image

# 从环境变量读取配置
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
FEISHU_CHAT_ID = os.environ.get("FEISHU_CHAT_ID")

# 获取飞书访问凭证
def get_tenant_access_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }
    res = requests.post(url, json=data).json()
    return res.get("tenant_access_token")

# 上传图片到飞书，获取image_key
def upload_image(image_url, token):
    # 下载图片
    img_res = requests.get(image_url)
    img = Image.open(io.BytesIO(img_res.content))
    # 压缩图片保证不超过上传大小限制
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=80)
    buf.seek(0)
    
    # 调用上传接口
    url = "https://open.feishu.cn/open-apis/im/v1/images"
    files = {
        'image': ('image.jpg', buf, 'image/jpeg')
    }
    data = {
        'image_type': 'message'
    }
    headers = {
        'Authorization': f'Bearer {token}'
    }
    res = requests.post(url, headers=headers, files=files, data=data).json()
    if res.get("code") == 0:
        return res["data"]["image_key"]
    else:
        print(f"上传图片失败：{res}")
        return None

# 抓取Steam榜单
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

# 发送单条消息到群聊，图片直接显示
def push_to_feishu(games, token):
    # 组装富文本内容
    content = []
    title = "Steam New & Trending 最新榜单"
    
    for game in games:
        # 上传图片获取image_key
        image_key = upload_image(game["img"], token)
        if not image_key:
            continue
        # 添加游戏信息：标题+价格+图片
        game_line = [
            {"tag": "a", "href": game["link"], "text": f"{game['name']} - {game['price']}"},
            {"tag": "text", "text": "\n"}
        ]
        content.append(game_line)
        # 添加图片，飞书会自动渲染
        content.append([{"tag": "img", "image_key": image_key}])
        content.append([{"tag": "text", "text": "\n"}])
    
    # 组装请求体
    data = {
        "receive_id": FEISHU_CHAT_ID,
        "msg_type": "post",
        "content": json.dumps({
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": content
                }
            }
        })
    }
    
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
    headers = {
        "Authorization": f'Bearer {token}',
        "Content-Type": "application/json; charset=utf-8"
    }
    
    res = requests.post(url, headers=headers, json=data).json()
    if res.get("code") != 0:
        print(f"推送失败，错误信息：{res}")
        return False
    
    print("推送成功！所有图片已直接显示")
    return True

if __name__ == "__main__":
    print("开始执行 Steam 热门新品榜推送任务")
    token = get_tenant_access_token()
    games = get_steam_games()
    print(f"成功抓取当前热门新品榜前 {len(games)} 款游戏")
    push_to_feishu(games, token)
