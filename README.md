# 🎮 游戏场 - 游戏管理中心

一个现代化的游戏管理平台，可以轻松启动、停止和管理多个游戏服务器。

## 🌟 功能特性

- **统一管理**: 在一个界面中管理所有游戏服务器
- **一键操作**: 启动、停止、重启所有游戏
- **实时状态**: 实时显示每个游戏的运行状态
- **现代化UI**: 美观的响应式界面设计
- **自动检测**: 自动检测游戏服务器状态
- **进程管理**: 使用gunicorn确保服务器稳定运行

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动游戏场

```bash
# 方法1: 使用启动脚本
python start_playground.py

# 方法2: 直接运行
python main.py

# 方法3: 使用gunicorn
gunicorn --bind 0.0.0.0:35100 --workers 1 main:app
```

### 3. 访问游戏场

打开浏览器访问: http://localhost:35100

## 🎯 游戏管理

### 当前支持的游戏

1. **六边形连线游戏** (端口: 35101)
   - 在六边形网格上连线，形成三角形来得分
   - 支持多人同时游戏
   - 实时状态同步

### 添加新游戏

1. 在游戏配置中添加新游戏:

```python
GAMES = {
    'hexagon_game': {
        'name': '六边形连线游戏',
        'description': '在六边形网格上连线，形成三角形来得分',
        'port': 35101,
        'path': 'hexagon_game/app.py',
        'status': 'stopped',
        'process': None,
        'url': 'http://localhost:35101'
    },
    'your_new_game': {
        'name': '你的新游戏',
        'description': '游戏描述',
        'port': 35102,
        'path': 'your_game/app.py',
        'status': 'stopped',
        'process': None,
        'url': 'http://localhost:35102'
    }
}
```

2. 确保新游戏目录包含 `app.py` 文件，并且可以通过 gunicorn 启动

## 🛠️ API 接口

### 游戏管理接口

- `GET /api/games` - 获取所有游戏状态
- `POST /api/games/{game_id}/start` - 启动指定游戏
- `POST /api/games/{game_id}/stop` - 停止指定游戏
- `POST /api/games/{game_id}/restart` - 重启指定游戏
- `POST /api/start_all` - 启动所有游戏
- `POST /api/stop_all` - 停止所有游戏

### 游戏访问接口

- `GET /play/{game_id}` - 进入指定游戏

## 📁 项目结构

```
Playground/
├── main.py                 # 主服务器文件
├── start_playground.py     # 启动脚本
├── requirements.txt        # 依赖文件
├── README.md              # 项目说明
├── templates/
│   └── index.html         # 主页模板
└── hexagon_game/          # 六边形游戏
    ├── app.py
    ├── templates/
    └── static/
```

## 🔧 配置说明

### 端口配置

- 主页服务器: 35100
- 六边形游戏: 35101
- 新游戏建议使用: 35102, 35103, ...

### 环境要求

- Python 3.7+
- Flask 2.3+
- Gunicorn 21.2+
- 其他依赖见 requirements.txt

## 🐛 故障排除

### 常见问题

1. **端口被占用**
   ```bash
   # 查看端口占用
   lsof -i :35100
   lsof -i :35101
   
   # 杀死占用进程
   kill -9 <PID>
   ```

2. **游戏启动失败**
   - 检查游戏目录是否存在
   - 确认 app.py 文件存在且可执行
   - 查看 gunicorn 日志

3. **权限问题**
   ```bash
   # 给启动脚本执行权限
   chmod +x start_playground.py
   ```

## 📝 开发说明

### 添加新功能

1. 在 `main.py` 中添加新的路由和功能
2. 在 `templates/index.html` 中更新前端界面
3. 测试新功能并更新文档

### 代码规范

- 使用中文注释
- 遵循 PEP 8 代码规范
- 添加适当的错误处理
- 保持代码简洁可读

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**享受游戏时光！** 🎮✨ 

## 🧩 子项目（游戏）开发规范

为保证各游戏子项目能被Playground统一管理和良好运行，需遵循以下规范：

### 1. 目录结构
- 每个游戏应为独立子目录（如 /hexagon_game/），目录下需包含：
  - `app.py`：Flask主程序，必须提供入口
  - `templates/`：前端模板（如有）
  - `static/`：静态资源（如有）
  - `README.md`：子项目说明（推荐）
  - `example_gamestate.json`：游戏状态示例文件（推荐）

### 2. 启动方式
- 必须支持通过 gunicorn 启动：
  ```bash
  gunicorn --bind 0.0.0.0:<端口> --workers 1 app:app
  ```
- `app.py` 中需定义 `app = Flask(__name__)` 并暴露 `app` 变量。

### 3. 健康检查
- 必须实现 `/health` 路由，返回 200 和简单内容（如 'ok'），用于主服务健康检查。
  ```python
  @app.route('/health')
  def health():
      return 'ok', 200
  ```

### 4. 游戏状态API规范
- 必须实现 `/api/gamestate` 路由，返回统一且尽量完整的游戏状态格式
- 支持通过 `board_id` 参数指定游戏房间/棋盘
- 支持通过 `my_color` 参数指定玩家颜色（可选）
- 返回的JSON参照以下字段结构，可以根据实际游戏内容更改：

```json
{
  "your_turn": 1,                    // 是否轮到当前玩家 (1=是, 0=否)
  "game_info": {                     // 游戏基本信息
    "game_type": "游戏名称",
    "board_size": 15,                // 棋盘大小
    "winning_condition": "获胜条件",
    "current_phase": "playing",      // playing/finished
    "game_status": "active",         // active/inactive
    "current_turn": 1                // 当前轮到谁 (1/-1)
  },
  "board": [                         // 棋盘状态矩阵,推荐使用数字保存状态

  ],
  "board_legend": {                  // 棋盘数值说明
    "0": "空位",
    "1": "玩家1",
    "-1": "玩家2"
  },
  "game_progress": {                 // 游戏进度
    "current_turn": 1,               // 当前回合
    "move_count": 5,                 // 已下棋子数
    "last_move": {                   // 最后一步
      "x": 7,
      "y": 7,
      "color": 1
    },
    "move_history": [                // 走子历史
      {
        "position": {"x": 7, "y": 7},
        "color": 1
      }
    ]
  },
  "metadata": {                      // 元数据
    "board_id": "abc12345",
    "created_at": "2024-06-01T12:00:00Z",
    "last_updated": "2024-06-01T12:05:00Z",
    "version": "1.0"
  },
  "my_color": 1                      // 当前玩家颜色/角色
}
```

### 6. 示例文件推荐要求
- 提供 `example_gamestate.json` 文件
- 示例文件应展示游戏进行中的典型状态
- 包含所有必需字段的完整示例

### 7. 日志输出
- gunicorn 启动时日志应输出到标准输出/标准错误，便于主服务收集和调试。
- 推荐在关键接口、异常处增加日志，便于排查问题。

### 8. API 设计
- 推荐所有业务接口以 `/api/` 开头，避免与静态页面路由冲突。
- 如需多房间/多棋盘，建议所有接口参数化（如 `?board_id=xxxx`）。
- 返回内容统一使用 JSON。
- 错误处理要完善，返回合适的HTTP状态码和错误信息。

### 9. 依赖管理
- 如有额外依赖，请在主项目 `requirements.txt` 中注明，或在子项目目录下提供 `requirements.txt` 并在主README说明。

### 10. 代码规范
- 代码需有适当中文注释，遵循 PEP8。
- 错误处理要完善，避免接口抛出未捕获异常。
- 保持接口和主服务解耦，不要依赖主服务内部实现。
- 使用统一的数值表示（0/1/-1），避免字符串表示。

### 11. 文档
- 推荐每个子项目有独立 `README.md`，说明玩法、接口、依赖、启动方式等。
- 必须包含API接口说明和示例。
- 说明游戏规则和获胜条件。 