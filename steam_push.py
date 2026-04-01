import requests
import time
import json
import os
import base64
from io import BytesIO

# 从环境变量读取配置
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")

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
        
        # 计算东八区昨天0点和今天0点的时间戳（统一转时间戳比较）
        # 获取当前东八区时间
        local_time = time.localtime()
        today_zero = int(time.mktime(time.strptime(time.strftime("%Y-%m-%d", local_time), "%Y-%m-%d")))
        yesterday_zero = today_zero - 24 * 3600  # 昨天0点 = 今天0点 - 24小时
        today_zero = yesterday_zero + 24 * 3600  # 今天0点 = 昨天0点 + 24小时
        
        print(f"筛选范围：时间戳 {yesterday_zero} ~ {today_zero}")
        print(f"对应时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(yesterday_zero))} ~ {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(today_zero))}")

        # 筛选【昨天0点 ~ 今天0点】之间发售的游戏，覆盖昨天整整24小时
        yesterday_games = []
        for idx, game in enumerate(new_releases):
            name = game.get("name", "未知名称")
            release_date = game.get("release_date", {}).get("date", 0)
            print(f"检查游戏：{name}，发售时间戳：{release_date}")
            
            # Steam榜单接口返回的date本身就是时间戳，直接用即可，仅字符串需要转换
            if isinstance(release_date, str):
                try:
                    release_date = int(time.mktime(time.strptime(release_date, "%Y-%m-%d")))
                    print(f"  转换字符串日期为时间戳：{release_date}")
                except Exception as e:
                    print(f"  日期转换失败，跳过：{str(e)}")
                    continue
            
            # 判断发售时间在东八区昨天24小时范围内
            if yesterday_zero <= release_date < today_zero:
                print(f"  ✅ 符合条件，加入推送列表")
                yesterday_games.append(game)
            else:
                print(f"  ❌ 不在筛选范围，跳过")
        
        print(f"最终找到 {len(yesterday_games)} 款符合条件的游戏")
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
    
    # 获取昨天日期，显示在标题
    yesterday_date = time.strftime("%Y-%m-%d", time.localtime(int(time.time()) - 24 * 3600))
    
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
    info_text = f"本次共推送 {len(games)} 款昨日新发（东八区全天） | 更新时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}"
    card["body"]["elements"].append({
        "tag
