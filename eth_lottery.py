import hashlib
import datetime
import time
import sys
import requests
import json
import argparse
import logging

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_block_hash(timestamp: int) -> (str, int):
    """
    获取给定时间戳之后的第一个区块的哈希。
    """
    while True:
        try:
            res = requests.get(
                f"https://api.etherscan.io/api?module=block&action=getblocknobytime&timestamp={timestamp}&closest=after&apikey=47EN1HNR7M9MJ81G1BJN7EKX4P89FZUU7E"
            )
            res.raise_for_status()
            json_response = res.json()
            if json_response.get('message') == "OK" and json_response.get("result"):
                block_num = int(json_response.get("result"))
                break
            else:
                logging.warning(f"获取区块高度API响应异常: {json_response}。正在重试...")
                time.sleep(3)
        except requests.exceptions.RequestException as e:
            logging.error(f"获取区块高度时出错: {e}")
            time.sleep(3)
        except (json.JSONDecodeError, AttributeError) as e:
            logging.error(f"解码或解析API响应时出错: {e}。正在重试...")
            time.sleep(3)

    while True:
        try:
            res = requests.get(
                f"https://api.etherscan.io/api?module=proxy&action=eth_getBlockByNumber&tag={hex(block_num)}&boolean=false&apikey=47EN1HNR7M9MJ81G1BJN7EKX4P89FZUU7E"
            )
            res.raise_for_status()
            json_response = res.json()
            if json_response.get("result"):
                block_hash = json_response.get("result").get("hash")
                if block_hash:
                    return block_hash, block_num
            
            logging.warning(f"获取区块哈希API响应异常: {json_response}。正在重试...")
            time.sleep(3)

        except requests.exceptions.RequestException as e:
            logging.error(f"获取区块哈希时出错: {e}")
            time.sleep(3)
        except (json.JSONDecodeError, AttributeError) as e:
            logging.error(f"解码或解析API响应时出错: {e}。正在重试...")
            time.sleep(3)


def _calculate_winners_fairly(lottery_id: str, participants: list, prizes: int, block_hash: str) -> list:
    """
    消除模偏差
    """
    num_participants = len(participants)
    if num_participants == 0:
        return []

    participants_hash = {
        hashlib.sha256((p + lottery_id).encode()).hexdigest(): p for p in participants
    }
    sorted_participants = sorted(participants_hash, key=str.lower, reverse=True)
    participant_ids = {i: p for i, p in enumerate(sorted_participants)}

    seed_str = f"{lottery_id}{num_participants}{prizes}{block_hash}"
    seed = hashlib.sha256(seed_str.encode()).hexdigest()

    winner_list = []
    
    # 拒绝采样的安全范围
    # 2**256 is the number of possible SHA-256 hashes
    safe_range = (2**256 // num_participants) * num_participants

    while len(winner_list) < prizes:
        seed_number = int(seed, 16)

        # 拒绝采样：如果数字超出安全范围，则重新哈希
        while seed_number >= safe_range:
            seed = hashlib.sha256(seed.encode()).hexdigest()
            seed_number = int(seed, 16)

        winner_id = seed_number % num_participants
        winner_hash = participant_ids[winner_id]

        if winner_hash not in winner_list:
            winner_list.append(winner_hash)

        # 为下一位中奖者生成新种子
        seed = hashlib.sha256(seed.encode()).hexdigest()

    return [participants_hash[h] for h in winner_list]


def draw(config: dict, timestamp: int) -> dict:
    """
    运行抽奖。
    """
    lottery_id = config["lottery_id"]
    participants = config["participants"]
    prizes = config["prizes"]

    if timestamp > int(time.time()):
        logging.info(f"等待到达抽奖时间: {datetime.datetime.fromtimestamp(timestamp)}")
        time.sleep(timestamp - int(time.time()))

    logging.info("正在获取区块哈希...")
    block_hash, block_num = get_block_hash(timestamp)
    logging.info(f"成功获取区块哈希: {block_hash} (区块高度: {block_num})")

    winners = _calculate_winners_fairly(lottery_id, participants, prizes, block_hash)

    result = {
        "lottery_id": lottery_id,
        "participants": participants,
        "prizes": prizes,
        "draw_time": datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S'),
        "block_num": block_num,
        "block_hash": block_hash,
        "winners": winners,
    }
    return result


def verify(result: dict):
    """
    验证抽奖结果。
    """
    lottery_id = result["lottery_id"]
    participants = result["participants"]
    prizes = result["prizes"]
    block_hash = result["block_hash"]
    winners = result["winners"]

    calculated_winners = _calculate_winners_fairly(lottery_id, participants, prizes, block_hash)

    if calculated_winners == winners:
        logging.info("验证成功！")
    else:
        logging.error("验证失败！")
        logging.error(f"期望的中奖者: {calculated_winners}")
        logging.error(f"实际的中奖者: {winners}")


def main():
    parser = argparse.ArgumentParser(description="公平抽奖工具。")
    parser.add_argument(
        "action", choices=["draw", "verify"], help="要执行的操作：'draw' (抽奖) 或 'verify' (验证)。"
    )
    parser.add_argument(
        "--time",
        help="抽奖时间，Unix时间戳（整数）。默认为当前时间戳。",
    )
    parser.add_argument(
        "--result_file", help="用于验证的结果文件。", default="result.json"
    )

    args = parser.parse_args()

    if args.action == "draw":
        try:
            with open("config.json", encoding='utf-8') as f:
                config = json.load(f)
        except FileNotFoundError:
            logging.error("错误: 未找到 config.json 文件。")
            return
        except json.JSONDecodeError:
            logging.error("错误: config.json 文件格式不正确。")
            return

        draw_time = int(args.time) if args.time else int(time.time())
        result = draw(config, draw_time)

        with open(args.result_file, "w", encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        logging.info(f"抽奖完成。结果已保存至 {args.result_file}")
        logging.info(f"区块高度: {result['block_num']}")
        logging.info(f"中奖者: {result['winners']}")

    elif args.action == "verify":
        try:
            with open(args.result_file, encoding='utf-8') as f:
                result = json.load(f)
        except FileNotFoundError:
            logging.error(f"错误: 未找到结果文件 {args.result_file}。")
            return
        except json.JSONDecodeError:
            logging.error(f"错误: {args.result_file} 文件格式不正确。")
            return
        verify(result)


if __name__ == "__main__":
    main()
