from flask import Flask, jsonify, request, session
import threading
import time
import random
import string
from flask import render_template

app = Flask(__name__)
app.secret_key = 'siege-secret-key'

# 游戏数据结构
GAMES = {}
GAMES_LOCK = threading.Lock()
BOARD_SIZE = 5
MAX_PLAYERS = 5
COLORS = [1, 2, 3, 4, 5]  # 五种颜色
START_POSITIONS = {
    2: [(0,0), (4,4)],
    3: [(0,0), (4,0), (2,4)],
    4: [(0,0), (4,0), (0,4), (4,4)],
    5: [(0,0), (4,0), (0,4), (4,4), (2,2)]
}

def gen_board_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

def create_new_game():
    return {
        'players': [],  # [{id, color, start_pos, online}]
        'status': 'waiting',  # waiting/playing/finished
        'current_turn': 0,
        'move_history': [],
        'winner': None,
        'board': [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)],
        'walls': set(),  # {(x, y, direction)}
        'created_at': time.time(),
        'message': '等待玩家加入...'
    }

def get_game(board_id, create_if_missing=True):
    with GAMES_LOCK:
        if board_id not in GAMES and create_if_missing:
            GAMES[board_id] = create_new_game()
        return GAMES.get(board_id)

# 辅助函数

def is_valid_move(game, player_idx, start, target):
    # 检查目标是否在棋盘内
    x0, y0 = start
    x1, y1 = target
    if not (0 <= x1 < BOARD_SIZE and 0 <= y1 < BOARD_SIZE):
        return False, '目标超出棋盘范围'
    # 不能原地不动
    if (x0, y0) == (x1, y1):
        return False, '必须移动至少一格'
    # 只能直线移动
    dx = x1 - x0
    dy = y1 - y0
    if dx != 0 and dy != 0:
        return False, '只能上下左右直线移动'
    dist = abs(dx + dy)
    if dist < 1 or dist > 3:
        return False, '每次必须移动1~3格'
    # 检查路径上是否有墙或其他玩家
    step_x = (dx // abs(dx)) if dx != 0 else 0
    step_y = (dy // abs(dy)) if dy != 0 else 0
    cx, cy = x0, y0
    for _ in range(dist):
        nx, ny = cx + step_x, cy + step_y
        # 检查墙体
        if is_blocked(game, cx, cy, nx, ny):
            return False, '路径被墙体阻挡'
        # 检查其他玩家
        for idx, p in enumerate(game['players']):
            if idx != player_idx and p.get('pos') == (nx, ny):
                return False, '路径被其他玩家阻挡'
        cx, cy = nx, ny
    return True, ''

def is_blocked(game, x0, y0, x1, y1):
    # 判断(x0,y0)-(x1,y1)之间是否有墙
    if abs(x0-x1)+abs(y0-y1) != 1:
        return True  # 只允许相邻
    if x0 == x1:
        if y1 > y0:
            return ((x0, y0, 'down') in game['walls']) or ((x1, y1, 'up') in game['walls'])
        else:
            return ((x0, y0, 'up') in game['walls']) or ((x1, y1, 'down') in game['walls'])
    else:
        if x1 > x0:
            return ((x0, y0, 'right') in game['walls']) or ((x1, y1, 'left') in game['walls'])
        else:
            return ((x0, y0, 'left') in game['walls']) or ((x1, y1, 'right') in game['walls'])

def is_valid_wall(game, pos, direction):
    x, y = pos
    # 检查墙体是否越界
    if direction == 'up' and y == 0:
        return False, '不能在棋盘外放置墙体'
    if direction == 'down' and y == BOARD_SIZE-1:
        return False, '不能在棋盘外放置墙体'
    if direction == 'left' and x == 0:
        return False, '不能在棋盘外放置墙体'
    if direction == 'right' and x == BOARD_SIZE-1:
        return False, '不能在棋盘外放置墙体'
    # 检查是否已存在
    if (x, y, direction) in game['walls']:
        return False, '该位置已有墙体'
    return True, ''

def is_player_trapped(game, player_idx):
    # 判断玩家是否被完全困住（无合法移动）
    pos = game['players'][player_idx].get('pos')
    if not pos:
        return False
    x, y = pos
    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
        nx, ny = x+dx, y+dy
        if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
            if not is_blocked(game, x, y, nx, ny):
                occupied = False
                for idx, p in enumerate(game['players']):
                    if idx != player_idx and p.get('pos') == (nx, ny):
                        occupied = True
                        break
                if not occupied:
                    return False
    return True

def all_players_isolated(game):
    # 判断所有玩家是否被分割在不同区域
    # 用BFS分区，统计每个玩家所在区域
    from collections import deque
    board = [[-1 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    for idx, p in enumerate(game['players']):
        if p.get('pos'):
            board[p['pos'][1]][p['pos'][0]] = idx
    visited = set()
    groups = []
    for idx, p in enumerate(game['players']):
        if not p.get('pos'):
            continue
        if p['pos'] in visited:
            continue
        q = deque([p['pos']])
        group = set([idx])
        visited.add(p['pos'])
        while q:
            x, y = q.popleft()
            for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nx, ny = x+dx, y+dy
                if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                    if is_blocked(game, x, y, nx, ny):
                        continue
                    if board[ny][nx] != -1 and (nx, ny) not in visited:
                        group.add(board[ny][nx])
                        q.append((nx, ny))
                        visited.add((nx, ny))
        groups.append(group)
    # 如果每个玩家都在不同group，则隔绝
    return len(groups) == len(game['players'])

@app.route('/health')
def health():
    return 'ok', 200

@app.route('/api/gamestate')
def api_gamestate():
    board_id = request.args.get('board_id')
    if not board_id or not board_id.isalnum() or len(board_id) != 8:
        return jsonify({'error': '无效的房间id'}), 400
    game = get_game(board_id, create_if_missing=False)
    if not game:
        return jsonify({'error': '房间不存在'}), 404
    # 返回主要游戏状态
    # 墙体带颜色
    walls = [list(w) for w in game['walls']]
    return jsonify({
        'players': game['players'],
        'status': game['status'],
        'current_turn': game['current_turn'],
        'move_history': game['move_history'],
        'winner': game['winner'],
        'board': game['board'],
        'walls': walls,
        'message': game['message'],
        'board_id': board_id
    })

@app.route('/api/join', methods=['POST'])
def api_join():
    board_id = request.args.get('board_id')
    if not board_id or not board_id.isalnum() or len(board_id) != 8:
        return jsonify({'error': '无效的房间id'}), 400
    game = get_game(board_id)
    if game['status'] != 'waiting':
        return jsonify({'error': '游戏已开始，无法加入'}), 403
    if len(game['players']) >= MAX_PLAYERS:
        return jsonify({'error': '房间已满'}), 403
    # 分配颜色
    used_colors = {p['color'] for p in game['players']}
    available_colors = [c for c in COLORS if c not in used_colors]
    if not available_colors:
        return jsonify({'error': '无可用颜色'}), 403
    color = available_colors[0]
    player_id = session.get(f'player_id_{board_id}')
    if not player_id:
        player_id = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        session[f'player_id_{board_id}'] = player_id
    # 检查是否已加入
    for p in game['players']:
        if p['id'] == player_id:
            return jsonify({'message': '已加入', 'color': p['color'], 'player_id': player_id})
    game['players'].append({'id': player_id, 'color': color, 'online': True, 'start_pos': None})
    return jsonify({'message': '加入成功', 'color': color, 'player_id': player_id})

@app.route('/api/start_game', methods=['POST'])
def api_start_game():
    board_id = request.args.get('board_id')
    if not board_id or not board_id.isalnum() or len(board_id) != 8:
        return jsonify({'error': '无效的房间id'}), 400
    game = get_game(board_id)
    if game['status'] != 'waiting':
        return jsonify({'error': '游戏已开始'}), 400
    n = len(game['players'])
    if n < 1 or n > 5:
        return jsonify({'error': '玩家人数需为1~5人'}), 400
    # 分配初始位置
    for idx, p in enumerate(game['players']):
        p['start_pos'] = START_POSITIONS[n][idx]
        p['pos'] = p['start_pos']
    game['status'] = 'playing'
    game['current_turn'] = 0
    game['message'] = '游戏开始！轮到玩家1行动。'
    return jsonify({'message': '游戏已开始', 'players': game['players']})

@app.route('/api/move', methods=['POST'])
def api_move():
    board_id = request.args.get('board_id')
    if not board_id or not board_id.isalnum() or len(board_id) != 8:
        return jsonify({'error': '无效的房间id'}), 400
    game = get_game(board_id)
    if game['status'] != 'playing':
        return jsonify({'error': '游戏未在进行中'}), 400
    player_id = session.get(f'player_id_{board_id}')
    if not player_id:
        return jsonify({'error': '未识别玩家身份'}), 403
    # 检查是否轮到该玩家
    if game['players'][game['current_turn']]['id'] != player_id:
        return jsonify({'error': '未轮到你行动'}), 403
    data = request.get_json()
    target = data.get('target')  # [x, y]
    if not (isinstance(target, list) and len(target) == 2):
        return jsonify({'error': '无效的目标位置'}), 400
    player_idx = game['current_turn']
    player = game['players'][player_idx]
    start = player.get('pos') or player.get('start_pos')
    valid, msg = is_valid_move(game, player_idx, start, tuple(target))
    if not valid:
        return jsonify({'error': msg}), 400
    # 记录历史
    game['move_history'].append({'type': 'move', 'player': player_id, 'from': start, 'to': tuple(target)})
    player['pos'] = tuple(target)
    # 检查是否被困
    if is_player_trapped(game, player_idx):
        player['trapped'] = True
    else:
        player['trapped'] = False
    game['message'] = f"玩家{player_idx+1}已移动，等待筑墙..."
    return jsonify({'message': '移动成功，请筑墙', 'next': 'build'})

@app.route('/api/build', methods=['POST'])
def api_build():
    board_id = request.args.get('board_id')
    if not board_id or not board_id.isalnum() or len(board_id) != 8:
        return jsonify({'error': '无效的房间id'}), 400
    game = get_game(board_id)
    if game['status'] != 'playing':
        return jsonify({'error': '游戏未在进行中'}), 400
    player_id = session.get(f'player_id_{board_id}')
    if not player_id:
        return jsonify({'error': '未识别玩家身份'}), 403
    # 检查是否轮到该玩家
    if game['players'][game['current_turn']]['id'] != player_id:
        return jsonify({'error': '未轮到你行动'}), 403
    data = request.get_json()
    wall = data.get('wall')  # [x, y, direction]
    if not (isinstance(wall, list) and len(wall) == 3):
        return jsonify({'error': '无效的墙体参数'}), 400
    pos = tuple(wall[:2])
    direction = wall[2]
    valid, msg = is_valid_wall(game, pos, direction)
    if not valid:
        return jsonify({'error': msg}), 400
    # 记录历史
    game['move_history'].append({'type': 'build', 'player': player_id, 'wall': (pos, direction)})
    color_idx = game['players'][game['current_turn']]['color'] - 1
    game['walls'].add((pos[0], pos[1], direction, color_idx))
    # 检查是否封死所有人（简单判定：所有玩家都被困）
    all_trapped = all(is_player_trapped(game, idx) for idx in range(len(game['players'])))
    if all_trapped or all_players_isolated(game):
        game['status'] = 'finished'
        # 计分：每人可达区域格子数
        scores = []
        for idx, p in enumerate(game['players']):
            scores.append((idx, count_accessible_cells(game, p.get('pos'))))
        max_score = max(s[1] for s in scores)
        winners = [s[0] for s in scores if s[1] == max_score]
        if len(winners) == 1:
            game['winner'] = winners[0]
            game['message'] = f"游戏结束，玩家{winners[0]+1}获胜！"
        else:
            # 平分，最后筑墙者胜
            last_builder = game['current_turn']
            if last_builder in winners:
                game['winner'] = last_builder
                game['message'] = f"游戏结束，平分，最后筑墙的玩家{last_builder+1}获胜！"
            else:
                game['winner'] = winners[0]
                game['message'] = f"游戏结束，平分，玩家{winners[0]+1}获胜！"
    else:
        # 切换回合
        game['current_turn'] = (game['current_turn'] + 1) % len(game['players'])
        game['message'] = f"玩家{game['current_turn']+1}行动"
    return jsonify({'message': '筑墙成功', 'next': 'move'})

@app.route('/api/reset', methods=['POST'])
def api_reset():
    board_id = request.args.get('board_id')
    if not board_id or not board_id.isalnum() or len(board_id) != 8:
        return jsonify({'error': '无效的房间id'}), 400
    with GAMES_LOCK:
        GAMES[board_id] = create_new_game()
    return jsonify({'message': '房间已重置'})

def count_accessible_cells(game, start):
    # 统计从start出发可达的空格数量
    from collections import deque
    visited = set()
    q = deque([start])
    while q:
        x, y = q.popleft()
        if (x, y) in visited:
            continue
        visited.add((x, y))
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = x+dx, y+dy
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                if is_blocked(game, x, y, nx, ny):
                    continue
                occupied = False
                for p in game['players']:
                    if p.get('pos') == (nx, ny):
                        occupied = True
                        break
                if not occupied:
                    q.append((nx, ny))
    return len(visited) - 1  # 不计自身
@app.route('/')
def index():
    return render_template('index.html')
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=35103, debug=True)
