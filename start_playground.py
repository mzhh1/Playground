#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import signal
import time

def main():
    """启动游戏场主页服务器"""
    print("🎮 启动游戏场主页服务器...")
    print("📍 主页地址: http://localhost:35100")
    print("📁 游戏目录: hexagon_game")
    print("⏹️  按 Ctrl+C 停止服务器")
    print("-" * 50)
    
    # 确保在正确的目录中运行
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # 启动gunicorn服务器
    cmd = [
        sys.executable, '-m', 'gunicorn',
        '--bind', '0.0.0.0:35100',
        '--workers', '1',
        '--timeout', '120',
        '--access-logfile', '-',
        '--error-logfile', '-',
        '--log-level', 'info',
        '--chdir', script_dir,  # 指定工作目录
        'main:app'
    ]
    
    try:
        process = subprocess.Popen(cmd)
        process.wait()
    except KeyboardInterrupt:
        print("\n🛑 正在停止服务器...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        print("✅ 服务器已停止")

if __name__ == '__main__':
    main() 