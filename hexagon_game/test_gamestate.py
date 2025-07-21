#!/usr/bin/env python3
"""
测试六边形游戏的gamestate接口
"""

import requests
import json
import time

def test_gamestate_api():
    """测试gamestate接口"""
    base_url = "http://localhost:35101"
    board_id = "Test1234"
    
    print("🧪 测试六边形游戏gamestate接口")
    print("=" * 50)
    
    # 1. 测试获取游戏状态
    print("1. 测试获取游戏状态...")
    try:
        response = requests.get(f"{base_url}/api/gamestate?board_id={board_id}")
        if response.status_code == 200:
            data = response.json()
            print("✅ 成功获取游戏状态")
            print(f"   游戏类型: {data.get('game_info', {}).get('game_type', 'N/A')}")
            print(f"   棋盘大小: {data.get('game_info', {}).get('board_size', 'N/A')}")
            print(f"   游戏阶段: {data.get('game_info', {}).get('current_phase', 'N/A')}")
            print(f"   玩家数量: {len(data.get('players', []))}")
            print(f"   是否轮到玩家: {data.get('your_turn', 'N/A')}")
            print(f"   我的颜色: {data.get('my_color', 'N/A')}")
            print(f"   游戏结束: {data.get('game_over', 'N/A')}")
            
            # 检查必需字段
            required_fields = [
                'your_turn', 'game_info', 'board', 'board_legend', 
                'game_progress', 'metadata', 'players', 'scores', 
                'line_counts', 'game_over', 'message'
            ]
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                print(f"❌ 缺少必需字段: {missing_fields}")
            else:
                print("✅ 所有必需字段都存在")
                
        else:
            print(f"❌ 获取游戏状态失败: {response.status_code}")
            print(f"   响应: {response.text}")
    except Exception as e:
        print(f"❌ 请求失败: {e}")
    
    print()
    
    # 2. 测试选择颜色
    print("2. 测试选择颜色...")
    try:
        session = requests.Session()
        color_data = {"color": "#d9534f"}
        response = session.post(
            f"{base_url}/api/select_color?board_id={board_id}",
            json=color_data
        )
        if response.status_code == 200:
            print("✅ 成功选择颜色")
            data = response.json()
            print(f"   响应: {data.get('message', 'N/A')}")
        else:
            print(f"❌ 选择颜色失败: {response.status_code}")
            print(f"   响应: {response.text}")
    except Exception as e:
        print(f"❌ 请求失败: {e}")
    
    print()
    
    # 3. 再次获取游戏状态，检查颜色是否设置
    print("3. 再次获取游戏状态（检查颜色设置）...")
    try:
        response = session.get(f"{base_url}/api/gamestate?board_id={board_id}")
        if response.status_code == 200:
            data = response.json()
            my_color = data.get('my_color')
            if my_color == "#d9534f":
                print("✅ 颜色设置成功")
                print(f"   我的颜色: {my_color}")
            else:
                print(f"❌ 颜色设置失败，期望: #d9534f，实际: {my_color}")
        else:
            print(f"❌ 获取游戏状态失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 请求失败: {e}")
    
    print()
    print("🎯 测试完成！")

if __name__ == "__main__":
    test_gamestate_api() 