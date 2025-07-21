#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import subprocess
import threading
import time
import signal
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_cors import CORS
import requests
import psutil
import copy

app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app)

# 游戏配置
GAMES = {
    'hexagon_game': {
        'name': '三角连锁棋',
        'description': '在六边形网格上连线，形成三角形来得分',
        'port': 35101,
        'path': 'hexagon_game/app.py',
        'status': 'stopped',
        'process': None,
        'url': 'http://124.221.145.212:35101'
    },
    'gobang': {
        'name': '五子棋',
        'description': '经典黑白对弈，五子连珠即胜',
        'port': 35102,
        'path': 'gobang/app.py',
        'status': 'stopped',
        'process': None,
        'url': 'http://124.221.145.212:35102'
    }
}

def start_game_server(game_id):
    """启动游戏服务器"""
    game = GAMES[game_id]
    if game['status'] == 'running':
        return False, "游戏服务器已在运行"
    
    try:
        # 启动游戏服务器
        cmd = [
            sys.executable, '-m', 'gunicorn',
            '--bind', f'0.0.0.0:{game["port"]}',
            '--workers', '1',
            '--timeout', '120',
            '--access-logfile', '-',
            '--error-logfile', '-',
            'app:app'
        ]
        
        # 切换到游戏目录
        game_dir = os.path.join(os.path.dirname(__file__), game_id)
        process = subprocess.Popen(
            cmd,
            cwd=game_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )
        
        # 实时打印子进程日志
        def stream_output(pipe, prefix):
            for line in iter(pipe.readline, b''):
                print(f"[{prefix}] {line.decode().rstrip()}")
        threading.Thread(target=stream_output, args=(process.stdout, f"{game_id}-stdout"), daemon=True).start()
        threading.Thread(target=stream_output, args=(process.stderr, f"{game_id}-stderr"), daemon=True).start()

        game['process'] = process
        game['status'] = 'starting'
        
        # 等待服务器启动
        def wait_for_server():
            time.sleep(3)  # 给服务器一些启动时间
            try:
                response = requests.get(f"{game['url']}/health", timeout=5)
                if response.status_code == 200:
                    game['status'] = 'running'
                else:
                    game['status'] = 'error'
            except:
                game['status'] = 'error'
        
        threading.Thread(target=wait_for_server, daemon=True).start()
        return True, "游戏服务器启动中"
        
    except Exception as e:
        game['status'] = 'error'
        return False, f"启动失败: {str(e)}"

def stop_game_server(game_id):
    """停止游戏服务器"""
    game = GAMES[game_id]
    
    try:
        # 方法1: 如果有process对象，尝试终止它
        if game['process']:
            try:
                # 终止进程组
                if hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(game['process'].pid), signal.SIGTERM)
                else:
                    game['process'].terminate()
                
                # 等待进程结束
                try:
                    game['process'].wait(timeout=5)
                except subprocess.TimeoutExpired:
                    game['process'].kill()
            except:
                pass  # 忽略错误，继续尝试其他方法
        
        # 方法2: 查找并杀死占用端口的进程
        port = game['port']
        try:
            # 使用lsof查找占用端口的进程
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid.strip():
                        try:
                            # 发送SIGTERM信号
                            os.kill(int(pid), signal.SIGTERM)
                            time.sleep(1)
                            
                            # 检查进程是否还在运行，如果还在就强制杀死
                            try:
                                os.kill(int(pid), 0)  # 检查进程是否存在
                                os.kill(int(pid), signal.SIGKILL)  # 强制杀死
                            except OSError:
                                pass  # 进程已经不存在了
                        except (ValueError, OSError):
                            pass  # 忽略错误
        except:
            pass  # 忽略lsof命令的错误
        
        # 清理状态
        game['process'] = None
        game['status'] = 'stopped'
        return True, "游戏服务器已停止"
        
    except Exception as e:
        return False, f"停止失败: {str(e)}"

def check_game_status():
    """检查所有游戏状态"""
    for game_id, game in GAMES.items():
        if game['status'] == 'running':
            try:
                response = requests.get(f"{game['url']}/health", timeout=3)
                if response.status_code != 200:
                    game['status'] = 'error'
            except:
                game['status'] = 'error'

def get_games_for_api():
    games_copy = {}
    for k, v in GAMES.items():
        games_copy[k] = {key: value for key, value in v.items() if key != 'process'}
    return games_copy

@app.route('/')
def index():
    """游戏场主页"""
    return render_template('index.html', games=get_games_for_api())

@app.route('/api/games')
def get_games():
    """获取游戏列表"""
    check_game_status()
    return jsonify(get_games_for_api())

@app.route('/api/games/<game_id>/start', methods=['POST'])
def start_game(game_id):
    """启动游戏"""
    if game_id not in GAMES:
        return jsonify({'error': '游戏不存在'}), 404
    
    success, message = start_game_server(game_id)
    if success:
        return jsonify({'message': message, 'status': GAMES[game_id]['status']})
    else:
        return jsonify({'error': message}), 400

@app.route('/api/games/<game_id>/stop', methods=['POST'])
def stop_game(game_id):
    """停止游戏"""
    if game_id not in GAMES:
        return jsonify({'error': '游戏不存在'}), 404
    
    success, message = stop_game_server(game_id)
    if success:
        return jsonify({'message': message, 'status': GAMES[game_id]['status']})
    else:
        return jsonify({'error': message}), 400

@app.route('/api/games/<game_id>/restart', methods=['POST'])
def restart_game(game_id):
    """重启游戏"""
    if game_id not in GAMES:
        return jsonify({'error': '游戏不存在'}), 404
    
    # 先停止
    stop_game_server(game_id)
    time.sleep(1)
    
    # 再启动
    success, message = start_game_server(game_id)
    if success:
        return jsonify({'message': '游戏重启中', 'status': GAMES[game_id]['status']})
    else:
        return jsonify({'error': message}), 400

@app.route('/play/<game_id>')
def play_game(game_id):
    """进入游戏页面"""
    if game_id not in GAMES:
        return "游戏不存在", 404
    game = GAMES[game_id]
    if game['status'] != 'running':
        return redirect(url_for('index'))
    token = request.args.get('token')
    if token:
        # 保留原有query参数（如board_id）
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        url_parts = list(urlparse(game['url']))
        query = parse_qs(url_parts[4])
        query['token'] = [token]
        url_parts[4] = urlencode(query, doseq=True)
        return redirect(urlunparse(url_parts))
    return redirect(game['url'])

@app.route('/api/start_all', methods=['POST'])
def start_all_games():
    """启动所有游戏"""
    results = {}
    for game_id in GAMES:
        success, message = start_game_server(game_id)
        results[game_id] = {'success': success, 'message': message}
    
    return jsonify(results)

@app.route('/api/stop_all', methods=['POST'])
def stop_all_games():
    """停止所有游戏"""
    results = {}
    for game_id in GAMES:
        success, message = stop_game_server(game_id)
        results[game_id] = {'success': success, 'message': message}
    
    return jsonify(results)

def cleanup_on_exit():
    """退出时清理所有进程"""
    for game_id in GAMES:
        stop_game_server(game_id)

if __name__ == '__main__':
    # 注册退出处理
    import atexit
    atexit.register(cleanup_on_exit)
    
    # 启动主页服务器
    app.run(debug=True, host='0.0.0.0', port=35100)
