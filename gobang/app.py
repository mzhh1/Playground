import os
import copy
import string
import random
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request, session
from threading import Lock, Thread

app = Flask(__name__)
app.secret_key = os.urandom(24)

# 多棋盘全局变量
BOARDS = {}
BOARDS_LOCK = Lock()
CLEANUP_INTERVAL = 60  # 秒
BOARD_EXPIRE = 120     # 超过2分钟无人访问自动销毁

# 棋盘id生成
def gen_board_id():
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=8))

def create_new_board():
    size = 15
    now = datetime.now().isoformat() + 'Z'
    state = {
        'size': size,
        'board': [[0 for _ in range(size)] for _ in range(size)],
        'players': [1, -1],  # 1=黑，-1=白
        'last_move': None,
        'last_move_color': None,
        'winner': None,
        'game_over': False,
        'message': "欢迎来到五子棋！请选择颜色开始游戏。"
    }
    return {
        'state': state,
        'history': [],
        'online': 0,
        'last_active': time.time(),
        'created_at': now
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
    my_color = request.args.get('my_color', None)
    if my_color is not None:
        try:
            my_color = int(my_color)
            if my_color not in [1, -1]:
                my_color = None
        except Exception:
            my_color = None
    if my_color is None:
        my_color = session.get(f'player_color_{board_id}', None)
        if my_color is not None:
            try:
                my_color = int(my_color)
                if my_color not in [1, -1]:
                    my_color = None
            except Exception:
                my_color = None
    if not board_id or not board_id.isalnum() or len(board_id) != 8:
        return jsonify({'error': '无效的棋盘id'}), 400
    board = get_board(board_id, create_if_missing=True)
    state = board['state']

    # 构建move_history
    move_history = []
    for h in board['history']:
        if h.get('last_move'):
            move = h['last_move']
            move_history.append({
                'position': {'x': move['x'], 'y': move['y']},
                'color': move['color']
            })
    if state['last_move']:
        move = state['last_move']
        move_history.append({
            'position': {'x': move['x'], 'y': move['y']},
            'color': move['color']
        })
    last_move_data = state['last_move'] if state['last_move'] else None

    # 当前回合
    if state['last_move_color'] is None:
        current_turn = 1
    else:
        current_turn = -state['last_move_color']

    # your_turn判断
    your_turn = 1 if (my_color is not None and my_color == current_turn) else 0

    return jsonify({
        'your_turn': your_turn,
        'game_info': {
            'game_type': '五子棋 (Gomoku)',
            'board_size': state['size'],
            'winning_condition': '连成5子获胜',
            'current_phase': 'playing' if not state['game_over'] else 'finished',
            'game_status': 'active' if not state['game_over'] else 'inactive',
            'current_turn': current_turn
        },
        'board': state['board'],
        'board_legend': {
            '0': '空位',
            '1': '黑棋',
            '-1': '白棋'
        },
        'game_progress': {
            'current_turn': current_turn,
            'move_count': len(move_history),
            'last_move': last_move_data,
            'move_history': move_history
        },
        'metadata': {
            'board_id': board_id,
            'created_at': board.get('created_at', datetime.now().isoformat() + 'Z'),
            'last_updated': datetime.now().isoformat() + 'Z',
            'version': '1.0'
        },
        'my_color': my_color,
        'winner': state['winner'],
        'game_over': state['game_over'],
        'message': state['message']
    })

@app.route('/api/select_color', methods=['POST'])
def select_color():
    board_id = request.args.get('board_id')
    if not board_id or not board_id.isalnum() or len(board_id) != 8:
        return jsonify({'error': '无效的棋盘id'}), 400
    board = get_board(board_id)
    data = request.get_json()
    color = data.get('color')
    if color not in [1, -1]:
        return jsonify({'error': '无效的颜色'}), 400
    session[f'player_color_{board_id}'] = color
    return jsonify({'message': f'颜色已选择: {"黑" if color == 1 else "白"}'})

@app.route('/api/reset', methods=['POST'])
def handle_reset():
    board_id = request.args.get('board_id')
    if not board_id or not board_id.isalnum() or len(board_id) != 8:
        return jsonify({'error': '无效的棋盘id'}), 400
    with BOARDS_LOCK:
        BOARDS[board_id] = create_new_board()
    return jsonify(BOARDS[board_id]['state'])

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
    return jsonify(board['state'])

@app.route('/api/move', methods=['POST'])
def make_move():
    board_id = request.args.get('board_id')
    if not board_id or not board_id.isalnum() or len(board_id) != 8:
        return jsonify({'error': '无效的棋盘id'}), 400
    board = get_board(board_id)
    if f'player_color_{board_id}' not in session:
        return jsonify({'error': '请先选择你的颜色'}), 403
    if board['state'].get('game_over', True):
        return jsonify({'error': '游戏已经结束！'}), 400
    data = request.get_json()
    x, y = data.get('x'), data.get('y')
    size = board['state']['size']
    if not (isinstance(x, int) and isinstance(y, int) and 0 <= x < size and 0 <= y < size):
        return jsonify({'error': '无效的落子点'}), 400
    my_color = session[f'player_color_{board_id}']
    # 轮流下
    if board['state']['last_move_color'] is None:
        if my_color != 1:
            return jsonify({'error': '黑棋先行'}), 403
    else:
        if my_color == board['state']['last_move_color']:
            return jsonify({'error': '请等待对方下棋'}), 403
    # 不能重复落子
    if board['state']['board'][y][x] != 0:
        return jsonify({'error': '该位置已有棋子'}), 400
    # 记录历史
    board['history'].append(copy.deepcopy(board['state']))
    if len(board['history']) > 20:
        board['history'].pop(0)
    # 落子
    board['state']['board'][y][x] = my_color
    board['state']['last_move'] = {'x': x, 'y': y, 'color': my_color}
    board['state']['last_move_color'] = my_color
    # 判断胜负
    if check_win(board['state']['board'], x, y, my_color):
        board['state']['winner'] = my_color
        board['state']['game_over'] = True
        board['state']['message'] = f"游戏结束！胜者：{'黑棋' if my_color == 1 else '白棋'}"
    else:
        if all(all(cell != 0 for cell in row) for row in board['state']['board']):
            board['state']['game_over'] = True
            board['state']['message'] = '游戏结束，平局！'
    return jsonify(board['state'])

def check_win(board, x, y, color):
    size = len(board)
    directions = [ (1,0), (0,1), (1,1), (1,-1) ]
    for dx, dy in directions:
        count = 1
        for dir in [1, -1]:
            nx, ny = x, y
            while True:
                nx += dx * dir
                ny += dy * dir
                if 0 <= nx < size and 0 <= ny < size and board[ny][nx] == color:
                    count += 1
                else:
                    break
        if count >= 5:
            return True
    return False 