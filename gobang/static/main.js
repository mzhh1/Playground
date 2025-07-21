const SVG_NS = "http://www.w3.org/2000/svg";
const board = document.getElementById('game-board');
const statusBox = document.getElementById('status-box');
const colorSelector = document.getElementById('color-selector');
const resetButton = document.getElementById('reset-button');
const undoButton = document.getElementById('undo-button');
const helpButton = document.getElementById('help-button');

let gameState = {};
let myColor = null;
let selectedPoint = null;
let isFetching = false;

function getBoardId() {
    const url = new URL(window.location.href);
    let boardId = url.searchParams.get('board_id');
    if (!boardId || !/^[A-Za-z0-9]{8}$/.test(boardId)) {
        boardId = Array.from({length:8},()=>"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789".charAt(Math.floor(Math.random()*62))).join("");
        url.searchParams.set('board_id', boardId);
        window.location.replace(url.toString());
        return null;
    }
    return boardId;
}
const BOARD_ID = getBoardId();
if (!BOARD_ID) throw new Error('board_id未初始化');

async function apiFetch(url, options={}) {
    const u = new URL(url, window.location.origin);
    u.searchParams.set('board_id', BOARD_ID);
    return fetch(u.toString(), options);
}

function drawBoard() {
    if (!gameState.board) return;
    board.innerHTML = '';
    const size = gameState.size || 15;
    const cellSize = 26;
    const margin = 20;
    board.setAttribute('width', cellSize * (size-1) + margin*2);
    board.setAttribute('height', cellSize * (size-1) + margin*2);
    board.setAttribute('viewBox', `0 0 ${cellSize * (size-1) + margin*2} ${cellSize * (size-1) + margin*2}`);
    // 画网格
    for (let i = 0; i < size; i++) {
        const lineH = document.createElementNS(SVG_NS, 'line');
        lineH.setAttribute('x1', margin);
        lineH.setAttribute('y1', margin + i*cellSize);
        lineH.setAttribute('x2', margin + cellSize*(size-1));
        lineH.setAttribute('y2', margin + i*cellSize);
        lineH.setAttribute('stroke', '#888');
        lineH.setAttribute('stroke-width', 1);
        board.appendChild(lineH);
        const lineV = document.createElementNS(SVG_NS, 'line');
        lineV.setAttribute('x1', margin + i*cellSize);
        lineV.setAttribute('y1', margin);
        lineV.setAttribute('x2', margin + i*cellSize);
        lineV.setAttribute('y2', margin + cellSize*(size-1));
        lineV.setAttribute('stroke', '#888');
        lineV.setAttribute('stroke-width', 1);
        board.appendChild(lineV);
    }
    // 画棋子
    for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
            const val = gameState.board[y][x];
            if (val === 1 || val === -1) {
                const stone = document.createElementNS(SVG_NS, 'circle');
                stone.setAttribute('cx', margin + x*cellSize);
                stone.setAttribute('cy', margin + y*cellSize);
                stone.setAttribute('r', 10);
                stone.setAttribute('fill', val === 1 ? '#222' : '#fff');
                stone.setAttribute('stroke', '#222');
                stone.setAttribute('stroke-width', 2);
                board.appendChild(stone);
            }
            // 可落子点
            if (val === 0 && isMyTurn() && !gameState.game_over) {
                const pt = document.createElementNS(SVG_NS, 'circle');
                pt.setAttribute('cx', margin + x*cellSize);
                pt.setAttribute('cy', margin + y*cellSize);
                pt.setAttribute('r', 6);
                pt.setAttribute('fill', '#bbb');
                pt.setAttribute('opacity', 0.01);
                pt.style.cursor = 'pointer';
                pt.addEventListener('mouseenter', ()=>{pt.setAttribute('opacity',0.25);});
                pt.addEventListener('mouseleave', ()=>{pt.setAttribute('opacity',0.01);});
                pt.addEventListener('click', ()=>onPointClick(x, y));
                board.appendChild(pt);
            }
        }
    }
}

function isMyTurn() {
    if (myColor !== 1 && myColor !== -1) return false;
    if (!gameState.last_move_color) return myColor === 1; // 黑棋先行
    return myColor !== gameState.last_move_color;
}

function updateUI() {
    if (!gameState.players) return;
    if (colorSelector.children.length === 0) {
        [1, -1].forEach(color => {
            const btn = document.createElement('button');
            btn.className = 'color-btn';
            btn.style.backgroundColor = color === 1 ? '#222' : '#fff';
            btn.style.color = color === 1 ? '#fff' : '#222';
            btn.dataset.color = color;
            btn.textContent = color === 1 ? '黑' : '白';
            btn.addEventListener('click', () => selectMyColor(color));
            colorSelector.appendChild(btn);
        });
    }
    document.querySelectorAll('#color-selector .color-btn').forEach(btn => btn.classList.toggle('selected', Number(btn.dataset.color) === myColor));
    // 状态
    if (gameState.game_over) {
        statusBox.textContent = gameState.message || '游戏结束';
        statusBox.style.backgroundColor = '#eee';
        statusBox.style.color = '#222';
    } else if (myColor !== 1 && myColor !== -1) {
        statusBox.textContent = '请选择你的颜色';
        statusBox.style.backgroundColor = '#eee';
        statusBox.style.color = '#222';
    } else if (isMyTurn()) {
        statusBox.textContent = '轮到你下棋';
        statusBox.style.backgroundColor = myColor === 1 ? '#222' : '#fff';
        statusBox.style.color = myColor === 1 ? '#fff' : '#222';
    } else {
        statusBox.textContent = '等待对方下棋...';
        statusBox.style.backgroundColor = '#eee';
        statusBox.style.color = '#222';
    }
    // 悔棋按钮
    undoButton.disabled = (myColor !== 1 && myColor !== -1) || gameState.last_move_color !== myColor;
    drawBoard();
    // 胜负弹窗
    if (gameState.game_over && gameState.winner && !window._victoryShown) {
        window._victoryShown = true;
        const div = document.createElement('div');
        div.innerHTML = `<div style="position:fixed;z-index:9999;left:0;top:0;width:100vw;height:100vh;background:rgba(0,0,0,0.4);display:flex;align-items:center;justify-content:center;"><div style="background:#fff;padding:32px 24px;border-radius:12px;box-shadow:0 8px 32px #0002;text-align:center;min-width:260px;"><h2>游戏结束</h2><div style="margin:18px 0;font-size:1.1em;">胜者：<b>${gameState.winner === 1 ? '黑棋' : '白棋'}</b></div><button style="margin-top:10px;padding:8px 24px;font-size:1em;border-radius:6px;border:none;background:#428bca;color:#fff;cursor:pointer;" onclick="this.closest('div[style*=&quot;position:fixed&quot;]').remove();">关闭</button></div></div>`;
        document.body.appendChild(div.firstChild);
    }
    if (!gameState.game_over) {
        window._victoryShown = false;
    }
}

async function onPointClick(x, y) {
    if (!isMyTurn() || gameState.game_over) return;
    try {
        const response = await apiFetch('/api/move', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ x, y }) });
        if (!response.ok) {
            const data = await response.json();
            alert('错误: ' + data.error);
        }
        await fetchGameState();
    } catch (error) { console.error("请求失败:", error); }
}

async function selectMyColor(color) {
    try {
        const response = await apiFetch('/api/select_color', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ color }) });
        if (!response.ok) {
            const data = await response.json();
            alert('错误: ' + data.error);
        }
        myColor = color;
        await fetchGameState();
    } catch (error) { console.error("请求失败:", error); }
}

undoButton.addEventListener('click', async () => {
    try {
        const response = await apiFetch('/api/undo', { method: 'POST' });
        if (!response.ok) {
            const data = await response.json();
            alert('错误: ' + data.error);
        }
        await fetchGameState();
    } catch (error) { console.error("请求失败:", error); }
});

resetButton.addEventListener('click', async () => {
    try {
        const response = await apiFetch('/api/reset', { method: 'POST' });
        if (!response.ok) {
            const data = await response.json();
            alert('错误: ' + data.error);
        }
        await fetchGameState();
    } catch (error) { console.error("请求失败:", error); }
});

helpButton.addEventListener('click', () => {
    if (document.getElementById('help-modal')) return;
    const helpDiv = document.createElement('div');
    helpDiv.id = 'help-modal';
    helpDiv.innerHTML = `
    <div style="position:fixed;z-index:10000;left:0;top:0;width:100vw;height:100vh;background:rgba(0,0,0,0.35);display:flex;align-items:center;justify-content:center;">
      <div style="background:#fff;max-width:95vw;width:400px;padding:28px 18px 18px 18px;border-radius:14px;box-shadow:0 8px 32px #0002;text-align:left;position:relative;font-size:1.05em;line-height:1.7;">
        <button style="position:absolute;right:12px;top:10px;font-size:1.3em;background:none;border:none;cursor:pointer;color:#888;" onclick="this.closest('#help-modal').remove()">×</button>
        <h2 style="text-align:center;margin-top:0;font-size:1.3em;">五子棋玩法说明</h2>
        <div style="max-height:60vh;overflow:auto;">
          <ol style="padding-left:1.2em;">
            <li>棋盘为 <b>15x15</b> 方格，玩家在交叉点落子。</li>
            <li>仅有黑白两色，<b>黑棋先行</b>，玩家交替落子，必须等对方下完才能下。</li>
            <li>任意一方率先连成<b>5子</b>即胜，游戏结束。</li>
            <li>支持<b>悔棋</b>（只能撤销自己最后一步）和<b>棋盘重置</b>。</li>
            <li>可通过分享链接实现多人对弈，支持多棋盘隔离。</li>
          </ol>
          <div style="margin:12px 0 0 0;">操作说明：</div>
          <ul style="line-height:1.7;font-size:1em;">
            <li>点击“选择你的颜色”按钮，选择黑棋或白棋身份。</li>
            <li>轮到你时，点击棋盘交叉点即可落子。</li>
            <li>点击“悔棋”可撤销自己最后一步。</li>
            <li>点击“重置”可重新开始新一局。</li>
          </ul>
        </div>
      </div>
    </div>`;
    document.body.appendChild(helpDiv);
});

async function fetchGameState() {
    if (isFetching) return;
    isFetching = true;
    try {
        const response = await apiFetch('/api/gamestate');
        if (response.ok) {
            const data = await response.json();
            // 适配新结构
            gameState = {};
            gameState.size = data.game_info.board_size;
            gameState.board = data.board;
            gameState.board_legend = data.board_legend;
            gameState.last_move_color = data.game_progress.last_move ? data.game_progress.last_move.color : null;
            gameState.game_over = data.game_over;
            gameState.winner = data.winner;
            gameState.players = [1, -1];
            gameState.message = data.message;
            // 其它字段可按需补充
            myColor = data.my_color;
            updateUI();
        }
    } catch (error) { console.error("请求失败:", error); }
    isFetching = false;
}

setInterval(fetchGameState, 2000);
fetchGameState(); 