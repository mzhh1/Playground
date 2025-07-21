# app.py

import os
import copy
import string
import random
import time
from flask import Flask, render_template, jsonify, request, session
from threading import Lock, Thread

app = Flask(__name__)
app.secret_key = os.urandom(24)

# 多棋盘全局变量
BOARDS = {}
BOARDS_LOCK = Lock()
CLEANUP_INTERVAL = 60  # 秒
BOARD_EXPIRE = 120     # 超过2分钟无人访问自动销毁

# 棋盘id格式
def gen_board_id():
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=8))

def _get_serializable_state(state):
    if not state:
        return {}
    state_copy = state.copy()
    state_copy.pop('segments', None)
    state_copy.pop('drawn_lines', None)
    return state_copy

def _convert_to_standard_gamestate(state, board_id, my_color=None):
    """将内部状态转换为标准的gamestate格式"""
    if not state:
        return {}
    
    # 计算当前轮到谁
    your_turn = 0
    if my_color and state.get('last_move_color') != my_color:
        your_turn = 1
    
    # 构建棋盘矩阵（简化版本，实际游戏中需要更复杂的转换）
    board_size = 7  # 六边形棋盘的大小
    board = [[0 for _ in range(board_size)] for _ in range(board_size)]
    
    # 将线条和三角形信息映射到棋盘矩阵
    # 这里简化处理，实际需要根据六边形坐标系统进行转换
    
    # 构建移动历史
    move_history = []
    if state.get('lines'):
        for line in state['lines']:
            if line.get('points') and len(line['points']) >= 2:
                # 取线条的起点作为移动位置
                pos = line['points'][0]
                move_history.append({
                    "position": {"x": pos[0], "y": pos[1]},
                    "color": line['color']
                })
    
    # 最后一步移动
    last_move = None
    if state.get('lines'):
        last_line = state['lines'][-1]
        if last_line.get('points') and len(last_line['points']) >= 2:
            pos = last_line['points'][0]
            last_move = {
                "x": pos[0],
                "y": pos[1], 
                "color": last_line['color']
            }
    
    # 计算移动次数
    move_count = len(state.get('lines', []))
    
    # 确定游戏阶段
    current_phase = "finished" if state.get('game_over', False) else "playing"
    
    # 构建标准格式的gamestate，同时保留原有的六边形游戏特定数据
    standard_state = {
        "your_turn": your_turn,
        "game_info": {
            "game_type": "六边形连线游戏",
            "board_size": board_size,
            "winning_condition": "占有三角形最多的玩家获胜",
            "current_phase": current_phase,
            "game_status": "active" if not state.get('game_over', False) else "inactive",
            "current_turn": 1 if not state.get('last_move_color') else -1
        },
        "board": board,
        "board_legend": {
            "0": "空位",
            "1": "已连线",
            "2": "红色三角形",
            "3": "蓝色三角形", 
            "4": "绿色三角形",
            "5": "黄色三角形",
            "6": "紫色三角形"
        },
        "game_progress": {
            "current_turn": 1 if not state.get('last_move_color') else -1,
            "move_count": move_count,
            "last_move": last_move,
            "move_history": move_history
        },
        "metadata": {
            "board_id": board_id,
            "created_at": "2024-06-01T12:00:00Z",  # 实际应该从board创建时间获取
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "version": "1.0"
        },
        "my_color": my_color,
        "players": state.get('players', []),
        "scores": state.get('scores', {}),
        "line_counts": state.get('line_counts', {}),
        "last_move_color": state.get('last_move_color'),
        "game_over": state.get('game_over', False),
        "message": state.get('message', ''),
        # 保留六边形游戏特定的数据结构以保持兼容性
        "points": state.get('points', []),
        "lines": state.get('lines', []),
        "captured_triangles": state.get('captured_triangles', [])
    }
    
    return standard_state

AXIAL_DIRECTIONS = [(1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1)]
def axial_add(p1, p2): return (p1[0] + p2[0], p1[1] + p2[1])

def get_line_points(p1, p2):
    distance = (abs(p1[0] - p2[0]) + abs(p1[1] - p2[1]) + abs(p1[0] + p1[1] - p2[0] - p2[1])) / 2
    if distance != 3: return None
    direction_q, direction_r = (p2[0] - p1[0]) / 3, (p2[1] - p1[1]) / 3
    is_straight_line = any(abs(d[0] - direction_q) < 1e-9 and abs(d[1] - direction_r) < 1e-9 for d in AXIAL_DIRECTIONS)
    if not is_straight_line: return None
    p_mid1, p_mid2 = (p1[0] + direction_q, p1[1] + direction_r), (p1[0] + 2 * direction_q, p1[1] + 2 * direction_r)
    if not (p_mid1[0].is_integer() and p_mid1[1].is_integer()): return None
    return [p1, (int(p_mid1[0]), int(p_mid1[1])), (int(p_mid2[0]), int(p_mid2[1])), p2]

def create_new_board():
    points, all_triangles = set(), []
    radius = 3
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            if abs(q + r) <= radius: points.add((q, r))
    for point in points:
        for d1, d2 in [(AXIAL_DIRECTIONS[0], AXIAL_DIRECTIONS[1]), (AXIAL_DIRECTIONS[0], AXIAL_DIRECTIONS[5])]:
            p1, p2, p3 = point, axial_add(point, d1), axial_add(point, d2)
            if p2 in points and p3 in points: all_triangles.append(frozenset([p1, p2, p3]))
    colors = ['#d9534f', '#428bca', '#5cb85c', '#f0ad4e', '#6e409e']
    state = {
        'players': colors,
        'points': list(points),
        'lines': [],
        'drawn_lines': set(),
        'segments': set(),
        'all_possible_triangles': [list(t) for t in set(all_triangles)],
        'captured_triangles': [],
        'scores': {color: 0 for color in colors},
        'line_counts': {color: 0 for color in colors},
        'last_move_color': None,
        'game_over': False,
        'message': "欢迎来到共享棋盘！请选择一个颜色开始游戏。"
    }
    return {
        'state': state,
        'history': [],
        'online': 0,
        'last_active': time.time()
    }

def get_board(board_id, create_if_missing=True):
    with BOARDS_LOCK:
        if board_id not in BOARDS:
            if not create_if_missing:
                return None
            BOARDS[board_id] = create_new_board()
        board = BOARDS[board_id]
        board['last_active'] = time.time()
        return board

def cleanup_boards():
    while True:
        time.sleep(CLEANUP_INTERVAL)
        now = time.time()
        with BOARDS_LOCK:
            expired = [bid for bid, b in BOARDS.items() if b['online'] <= 0 and now - b['last_active'] > BOARD_EXPIRE]
            for bid in expired:
                del BOARDS[bid]

# 启动后台清理线程
Thread(target=cleanup_boards, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return 'ok', 200

@app.route('/api/gamestate')
def get_gamestate():
    board_id = request.args.get('board_id')
    if not board_id or not board_id.isalnum() or len(board_id) != 8:
        return jsonify({'error': '无效的棋盘id'}), 400
    board = get_board(board_id, create_if_missing=True)
    my_color = session.get(f'player_color_{board_id}', None)
    
    # 返回标准格式的gamestate
    standard_gamestate = _convert_to_standard_gamestate(board['state'], board_id, my_color)
    return jsonify(standard_gamestate)

@app.route('/api/select_color', methods=['POST'])
def select_color():
    board_id = request.args.get('board_id')
    if not board_id or not board_id.isalnum() or len(board_id) != 8:
        return jsonify({'error': '无效的棋盘id'}), 400
    board = get_board(board_id)
    data = request.get_json()
    color = data.get('color')
    if color not in board['state'].get('players', []):
        return jsonify({'error': '无效的颜色'}), 400
    session[f'player_color_{board_id}'] = color
    return jsonify({'message': f'颜色已选择: {color}'})

@app.route('/api/reset', methods=['POST'])
def handle_reset():
    board_id = request.args.get('board_id')
    if not board_id or not board_id.isalnum() or len(board_id) != 8:
        return jsonify({'error': '无效的棋盘id'}), 400
    with BOARDS_LOCK:
        BOARDS[board_id] = create_new_board()
    my_color = session.get(f'player_color_{board_id}', None)
    return jsonify(_convert_to_standard_gamestate(BOARDS[board_id]['state'], board_id, my_color))

@app.route('/api/undo', methods=['POST'])
def handle_undo():
    board_id = request.args.get('board_id')
    if not board_id or not board_id.isalnum() or len(board_id) != 8:
        return jsonify({'error': '无效的棋盘id'}), 400
    board = get_board(board_id)
    if f'player_color_{board_id}' not in session:
        return jsonify({'error': '请先选择你的颜色'}), 403
    if not board['history']:
        return jsonify({'error': '没有可悔棋的步骤'}), 400
    if board['state'].get('last_move_color') != session.get(f'player_color_{board_id}'):
        return jsonify({'error': '只能撤销自己下的最后一步棋'}), 403
    board['state'] = board['history'].pop()
    my_color = session.get(f'player_color_{board_id}', None)
    return jsonify(_convert_to_standard_gamestate(board['state'], board_id, my_color))

@app.route('/api/move', methods=['POST'])
def make_move():
    board_id = request.args.get('board_id')
    if not board_id or not board_id.isalnum() or len(board_id) != 8:
        return jsonify({'error': '无效的棋盘id'}), 400
    board = get_board(board_id)
    if f'player_color_{board_id}' not in session:
        return jsonify({'error': '在放置线条前，请先选择一个颜色。'}), 403
    if board['state'].get('game_over', True):
        return jsonify({'error': '游戏已经结束！'}), 400
    board['history'].append(copy.deepcopy(board['state']))
    if len(board['history']) > 20:
        board['history'].pop(0)
    data = request.get_json()
    p1 = tuple(data['p1'])
    p2 = tuple(data['p2'])
    line_points = get_line_points(p1, p2)
    if not line_points:
        board['history'].pop()
        return jsonify({'error': '无效的移动。请选择形成长度为4的直线的两点。'}), 400
    canonical_line = tuple(sorted([p1, p2]))
    if canonical_line in board['state']['drawn_lines']:
        board['history'].pop()
        return jsonify({'error': '无效的移动。这条线已经存在。'}), 400
    current_player_color = session[f'player_color_{board_id}']
    board['state']['drawn_lines'].add(canonical_line)
    board['state']['lines'].append({'points': line_points, 'color': current_player_color})
    board['state']['line_counts'][current_player_color] += 1
    board['state']['last_move_color'] = current_player_color
    for i in range(len(line_points) - 1):
        board['state']['segments'].add(frozenset([line_points[i], line_points[i+1]]))
    captured_points_sets = {frozenset(t['points']) for t in board['state']['captured_triangles']}
    for tri_points in board['state']['all_possible_triangles']:
        tri_set = frozenset(tri_points)
        if tri_set not in captured_points_sets:
            p1_tri, p2_tri, p3_tri = tri_points[0], tri_points[1], tri_points[2]
            s1, s2, s3 = frozenset([p1_tri, p2_tri]), frozenset([p2_tri, p3_tri]), frozenset([p3_tri, p1_tri])
            if s1 in board['state']['segments'] and s2 in board['state']['segments'] and s3 in board['state']['segments']:
                board['state']['captured_triangles'].append({'points': tri_points, 'color': current_player_color})
                board['state']['scores'][current_player_color] += 1
                captured_points_sets.add(tri_set)
    if len(board['state']['captured_triangles']) == len(board['state']['all_possible_triangles']):
        board['state']['game_over'] = True
        board['state']['message'] = "游戏结束！所有三角形已被填充。"
    my_color = session.get(f'player_color_{board_id}', None)
    return jsonify(_convert_to_standard_gamestate(board['state'], board_id, my_color))

@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    board_id = request.args.get('board_id')
    action = request.args.get('action', 'inc')  # inc: 页面激活/打开，dec: 页面关闭
    if not board_id or not board_id.isalnum() or len(board_id) != 8:
        return jsonify({'error': '无效的棋盘id'}), 400
    board = get_board(board_id)
    with BOARDS_LOCK:
        if action == 'inc':
            board['online'] += 1
        elif action == 'dec':
            board['online'] = max(0, board['online'] - 1)
        board['last_active'] = time.time()
    return jsonify({'online': board['online']})

if __name__ == '__main__':
    app.run(debug=True, host='::', port=35101)