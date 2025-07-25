import requests
import time
import json
import os
import argparse
import logging

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_all_replies(topic_id, auth_token, content_keyword=None, created_before=None):
    base_url = f"https://www.v2ex.com/api/v2/topics/{topic_id}/replies"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Authorization": f"Bearer {auth_token}"
    }

    usernames = set()
    page = 1
    total_pages = 1  # 初始设为1，后续从响应中获取真实页数

    logging.info(f"开始获取主题 {topic_id} 的回复...")

    while page <= total_pages:
        params = {"p": page}
        try:
            response = requests.get(base_url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if not data.get("success", False):
                logging.error(f"请求失败：{data.get('message', '未知错误')}")
                break

            if page == 1:
                total_pages = data.get("pagination", {}).get("pages", 1)
                logging.info(f"总页数: {total_pages}")

            for reply in data.get("result", []):
                content = reply.get("content", "")
                created = reply.get("created", 0)
                username = reply.get("member", {}).get("username")

                if content_keyword and content_keyword not in content:
                    continue
                if created_before and created >= created_before:
                    continue
                if username:
                    usernames.add(username)

            logging.info(f"已处理第 {page} 页，当前获取到 {len(usernames)} 个用户名。")
            page += 1
        except requests.RequestException as e:
            logging.error(f"请求失败：{e}")
            break

    logging.info(f"获取回复完成。总共获取到 {len(usernames)} 个用户名。")
    return usernames


def save_to_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logging.info(f"已保存 {len(data)} 个用户名到 {filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从 V2EX API 获取回复并提取用户名。")
    parser.add_argument(
        "--topic_id", 
        type=int, 
        required=True, 
        help="V2EX 主题的 ID。"
    )
    parser.add_argument(
        "--auth_token", 
        type=str, 
        required=True, 
        help="V2EX API 的 Bearer Token。"
    )
    parser.add_argument(
        "--content_keyword", 
        type=str, 
        default=None, 
        help="可选：回复内容中包含的关键词。"
    )
    parser.add_argument(
        "--created_before", 
        type=int, 
        default=None, 
        help="可选：回复创建时间戳，只获取在此时间戳之前的回复。"
    )

    args = parser.parse_args()

    usernames = fetch_all_replies(
        args.topic_id,
        args.auth_token,
        content_keyword=args.content_keyword,
        created_before=args.created_before
    )

    # 去重保存
    usernames = list(set(usernames))
    save_to_json(usernames, "usernames.json")
