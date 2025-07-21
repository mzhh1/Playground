const BOARD_SIZE = 5;
const COLORS = ['#222', '#e74c3c', '#3498db', '#27ae60', '#f1c40f'];

const board = document.getElementById('game-board');
const statusBox = document.getElementById('status-box');
const playersList = document.getElementById('players-list');
const joinBtn = document.getElementById('join-btn');
const startBtn = document.getElementById('start-btn');
const moveBtn = document.getElementById('move-btn');
const buildBtn = document.getElementById('build-btn');
const resetBtn = document.getElementById('reset-btn');
const helpBtn = document.getElementById('help-btn');

let gameState = {};
let myPlayerId = null;
let myColorIdx = null;
let myIdx = null;
let selectedMove = null;
let selectedWall = null;
let movePath = null; // [{x, y}]
let moveCount = 0;

function resetMoveState() {
    movePath = null;
    moveCount = 0;
    window._siege_moved = null;
}

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

function renderPlayers() {
    if (!gameState.players) return;
    playersList.innerHTML = '<b>玩家列表</b><br>';
    gameState.players.forEach((p, idx) => {
        const color = COLORS[(p.color-1)%COLORS.length];
        const me = (myPlayerId && p.id === myPlayerId) ? '（你）' : '';
        playersList.innerHTML += `<div style="margin:4px 0;"><span style="display:inline-block;width:16px;height:16px;border-radius:50%;background:${color};margin-right:6px;"></span>玩家${idx+1}${me}</div>`;
    });
}

function renderBoard() {
    board.innerHTML = '';
    if (!gameState.players) return;
    const cellSize = 48;
    const margin = 24;
    board.setAttribute('width', cellSize * BOARD_SIZE + margin*2);
    board.setAttribute('height', cellSize * BOARD_SIZE + margin*2);
    board.setAttribute('viewBox', `0 0 ${cellSize * BOARD_SIZE + margin*2} ${cellSize * BOARD_SIZE + margin*2}`);
    // 画网格
    for (let i = 0; i <= BOARD_SIZE; i++) {
        const lineH = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        lineH.setAttribute('x1', margin);
        lineH.setAttribute('y1', margin + i*cellSize);
        lineH.setAttribute('x2', margin + BOARD_SIZE*cellSize);
        lineH.setAttribute('y2', margin + i*cellSize);
        lineH.setAttribute('stroke', '#888');
        lineH.setAttribute('stroke-width', 1);
        board.appendChild(lineH);
        const lineV = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        lineV.setAttribute('x1', margin + i*cellSize);
        lineV.setAttribute('y1', margin);
        lineV.setAttribute('x2', margin + i*cellSize);
        lineV.setAttribute('y2', margin + BOARD_SIZE*cellSize);
        lineV.setAttribute('stroke', '#888');
        lineV.setAttribute('stroke-width', 1);
        board.appendChild(lineV);
    }
    // 画玩家
    gameState.players.forEach((p, idx) => {
        const pos = p.pos || p.start_pos;
        if (!pos) return;
        const color = COLORS[(p.color-1)%COLORS.length];
        const stone = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        stone.setAttribute('cx', margin + pos[0]*cellSize + cellSize/2);
        stone.setAttribute('cy', margin + pos[1]*cellSize + cellSize/2);
        stone.setAttribute('r', 18);
        stone.setAttribute('fill', color);
        stone.setAttribute('stroke', '#222');
        stone.setAttribute('stroke-width', 2);
        board.appendChild(stone);
    });
    // 画墙体
    if (gameState.walls) {
        gameState.walls.forEach(w => {
            const [x, y, dir, wallColorIdx] = w.length === 4 ? w : [...w, 0];
            let x1, y1, x2, y2;
            if (dir === 'up') {
                x1 = margin + x*cellSize;
                y1 = margin + y*cellSize;
                x2 = margin + (x+1)*cellSize;
                y2 = margin + y*cellSize;
            } else if (dir === 'down') {
                x1 = margin + x*cellSize;
                y1 = margin + (y+1)*cellSize;
                x2 = margin + (x+1)*cellSize;
                y2 = margin + (y+1)*cellSize;
            } else if (dir === 'left') {
                x1 = margin + x*cellSize;
                y1 = margin + y*cellSize;
                x2 = margin + x*cellSize;
                y2 = margin + (y+1)*cellSize;
            } else if (dir === 'right') {
                x1 = margin + (x+1)*cellSize;
                y1 = margin + y*cellSize;
                x2 = margin + (x+1)*cellSize;
                y2 = margin + (y+1)*cellSize;
            }
            const wallLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            wallLine.setAttribute('x1', x1);
            wallLine.setAttribute('y1', y1);
            wallLine.setAttribute('x2', x2);
            wallLine.setAttribute('y2', y2);
            wallLine.setAttribute('stroke', COLORS[wallColorIdx] || '#b52');
            wallLine.setAttribute('stroke-width', 7);
            wallLine.setAttribute('stroke-linecap', 'round');
            board.appendChild(wallLine);
        });
    }
    // 交互逻辑
    if (gameState.status === 'playing' && myIdx === gameState.current_turn) {
        const me = gameState.players[myIdx];
        let curPos = me.pos || me.start_pos;
        let path = movePath || [curPos];
        let steps = path.length - 1;
        // 1. 可继续移动点
        if (steps < 3) {
            for (let dir of [[0,1],[0,-1],[1,0],[-1,0]]) {
                const [dx, dy] = dir;
                const last = path[path.length-1];
                const tx = last[0]+dx, ty = last[1]+dy;
                if (tx < 0 || tx >= BOARD_SIZE || ty < 0 || ty >= BOARD_SIZE) continue;
                // 检查是否已在路径中（不允许回头）
                if (path.some(([px,py])=>px===tx&&py===ty)) continue;
                // 检查是否有其他玩家
                let occupied = false;
                gameState.players.forEach((p, idx) => {
                    if (idx !== myIdx && p.pos && p.pos[0]===tx && p.pos[1]===ty) occupied = true;
                });
                if (occupied) continue;
                // 检查墙体
                if (isBlocked(gameState, last[0], last[1], tx, ty)) continue;
                // 可移动点
                const moveCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                moveCircle.setAttribute('cx', margin + tx*cellSize + cellSize/2);
                moveCircle.setAttribute('cy', margin + ty*cellSize + cellSize/2);
                moveCircle.setAttribute('r', 12);
                moveCircle.setAttribute('fill', '#fff');
                moveCircle.setAttribute('opacity', 0.01);
                moveCircle.style.cursor = 'pointer';
                moveCircle.addEventListener('mouseenter', ()=>{moveCircle.setAttribute('opacity',0.25);});
                moveCircle.addEventListener('mouseleave', ()=>{moveCircle.setAttribute('opacity',0.01);});
                moveCircle.addEventListener('click', async ()=>{
                    await onMove([tx, ty]);
                });
                board.appendChild(moveCircle);
            }
        }
        // 2. 可筑墙边
        if (steps >= 1) {
            const last = path[path.length-1];
            const dirs = [
                {dir:'up',    x:last[0], y:last[1]},
                {dir:'down',  x:last[0], y:last[1]},
                {dir:'left',  x:last[0], y:last[1]},
                {dir:'right', x:last[0], y:last[1]}
            ];
            dirs.forEach(({dir, x, y}) => {
                if ((dir==='up'&&y===0)||(dir==='down'&&y===BOARD_SIZE-1)||(dir==='left'&&x===0)||(dir==='right'&&x===BOARD_SIZE-1)) return;
                if (gameState.walls.some(w => w[0]===x && w[1]===y && w[2]===dir)) return;
                const wallLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                if (dir==='up'||dir==='down') {
                    wallLine.setAttribute('x1', margin+x*cellSize);
                    wallLine.setAttribute('y1', dir==='up'?margin+y*cellSize:margin+(y+1)*cellSize);
                    wallLine.setAttribute('x2', margin+(x+1)*cellSize);
                    wallLine.setAttribute('y2', dir==='up'?margin+y*cellSize:margin+(y+1)*cellSize);
                } else {
                    wallLine.setAttribute('x1', dir==='left'?margin+x*cellSize:margin+(x+1)*cellSize);
                    wallLine.setAttribute('y1', margin+y*cellSize);
                    wallLine.setAttribute('x2', dir==='left'?margin+x*cellSize:margin+(x+1)*cellSize);
                    wallLine.setAttribute('y2', margin+(y+1)*cellSize);
                }
                wallLine.setAttribute('stroke', COLORS[me.color-1]);
                wallLine.setAttribute('stroke-width', 7);
                wallLine.setAttribute('stroke-linecap', 'round');
                wallLine.setAttribute('opacity', 0.18);
                wallLine.style.cursor = 'pointer';
                wallLine.addEventListener('mouseenter', ()=>{wallLine.setAttribute('opacity',0.7);});
                wallLine.addEventListener('mouseleave', ()=>{wallLine.setAttribute('opacity',0.18);});
                wallLine.addEventListener('click', async ()=>{
                    await onBuild([x, y, dir]);
                });
                board.appendChild(wallLine);
            });
        }
    }
}

function isBlocked(gameState, x0, y0, x1, y1) {
    if (Math.abs(x0-x1)+Math.abs(y0-y1) !== 1) return true;
    for (const w of gameState.walls) {
        if (x0 === x1) {
            if (y1 > y0 && ((w[0]===x0&&w[1]===y0&&w[2]==='down')||(w[0]===x1&&w[1]===y1&&w[2]==='up'))) return true;
            if (y1 < y0 && ((w[0]===x0&&w[1]===y0&&w[2]==='up')||(w[0]===x1&&w[1]===y1&&w[2]==='down'))) return true;
        } else if (y0 === y1) {
            if (x1 > x0 && ((w[0]===x0&&w[1]===y0&&w[2]==='right')||(w[0]===x1&&w[1]===y1&&w[2]==='left'))) return true;
            if (x1 < x0 && ((w[0]===x0&&w[1]===y0&&w[2]==='left')||(w[0]===x1&&w[1]===y1&&w[2]==='right'))) return true;
        }
    }
    return false;
}

function updateUI() {
    renderPlayers();
    renderBoard();
    // 状态栏
    if (gameState.status === 'playing' && myIdx === gameState.current_turn) {
        let steps = movePath ? movePath.length-1 : 0;
        if (steps < 3) {
            statusBox.textContent = `已移动${steps}步，请移动并筑墙`;
        } else {
            statusBox.textContent = `已移动3步，请筑墙`;
        }
    } else {
        statusBox.textContent = gameState.message || '';
    }
    // 按钮状态
    // joinBtn.disabled = !!myPlayerId; // 移除joinBtn相关逻辑
    startBtn.disabled = !myPlayerId || gameState.status !== 'waiting';
    // moveBtn.disabled = true; // 移除moveBtn相关逻辑
    // buildBtn.disabled = true; // 移除buildBtn相关逻辑
    // if (gameState.status === 'playing' && myIdx === gameState.current_turn) {
    //     moveBtn.disabled = false;
    // }
    // if (gameState.status === 'playing' && myIdx === gameState.current_turn && selectedMove) {
    //     buildBtn.disabled = false;
    // }
}

async function fetchGameState() {
    try {
        const response = await apiFetch('/api/gamestate');
        if (response.ok) {
            const data = await response.json();
            gameState = data;
            // 识别自己
            myPlayerId = localStorage.getItem('siege_player_id_'+BOARD_ID) || null;
            myIdx = null;
            if (gameState.players) {
                gameState.players.forEach((p, idx) => {
                    if (myPlayerId && p.id === myPlayerId) myIdx = idx;
                });
            }
            // 检查自己是否还在房间，不在则自动加入
            if (myPlayerId && (!gameState.players || !gameState.players.some(p => p.id === myPlayerId))) {
                await autoJoin();
                // 重新获取状态
                const resp2 = await apiFetch('/api/gamestate');
                if (resp2.ok) {
                    const data2 = await resp2.json();
                    gameState = data2;
                    myPlayerId = localStorage.getItem('siege_player_id_'+BOARD_ID) || null;
                    myIdx = null;
                    if (gameState.players) {
                        gameState.players.forEach((p, idx) => {
                            if (myPlayerId && p.id === myPlayerId) myIdx = idx;
                        });
                    }
                }
            }
            updateUI();
        }
    } catch (e) { console.error(e); }
}

async function autoJoin() {
    const response = await apiFetch('/api/join', {method:'POST'});
    const data = await response.json();
    if (data.player_id) {
        myPlayerId = data.player_id;
        localStorage.setItem('siege_player_id_'+BOARD_ID, myPlayerId);
    }
}

// 页面加载自动加入
window.addEventListener('DOMContentLoaded', async () => {
    await autoJoin();
    await fetchGameState();
});

startBtn.onclick = async () => {
    await apiFetch('/api/start_game', {method:'POST'});
    await fetchGameState();
};

resetBtn.onclick = async () => {
    await apiFetch('/api/reset', {method:'POST'});
    localStorage.removeItem('siege_player_id_'+BOARD_ID);
    myPlayerId = null;
    await autoJoin();
    await fetchGameState();
};

async function onMove(target) {
    if (!myPlayerId || myIdx !== gameState.current_turn) return;
    if (!movePath) movePath = [gameState.players[myIdx].pos || gameState.players[myIdx].start_pos];
    // 只允许一步
    if (movePath.length > 0 && (Math.abs(target[0]-movePath[movePath.length-1][0]) + Math.abs(target[1]-movePath[movePath.length-1][1]) !== 1)) return;
    movePath.push(target);
    const response = await apiFetch('/api/move', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({target})});
    const data = await response.json();
    if (data.error) {
        alert('移动失败：'+data.error);
        resetMoveState();
        await fetchGameState();
        return;
    }
    // 不自动进入筑墙，允许继续移动
    await fetchGameState();
}

async function onBuild(wall) {
    if (!myPlayerId || myIdx !== gameState.current_turn) return;
    resetMoveState();
    const response = await apiFetch('/api/build', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({wall})});
    const data = await response.json();
    if (data.error) {
        alert('筑墙失败：'+data.error);
    }
    await fetchGameState();
}

helpBtn.onclick = () => {
    if (document.getElementById('help-modal')) return;
    const helpDiv = document.createElement('div');
    helpDiv.id = 'help-modal';
    helpDiv.innerHTML = `
    <div style="position:fixed;z-index:10000;left:0;top:0;width:100vw;height:100vh;background:rgba(0,0,0,0.35);display:flex;align-items:center;justify-content:center;">
      <div style="background:#fff;max-width:95vw;width:420px;padding:28px 18px 18px 18px;border-radius:14px;box-shadow:0 8px 32px #0002;text-align:left;position:relative;font-size:1.05em;line-height:1.7;">
        <button style="position:absolute;right:12px;top:10px;font-size:1.3em;background:none;border:none;cursor:pointer;color:#888;" onclick="this.closest('#help-modal').remove()">×</button>
        <h2 style="text-align:center;margin-top:0;font-size:1.3em;">围城棋玩法说明</h2>
        <div style="max-height:60vh;overflow:auto;">
          <ol style="padding-left:1.2em;">
            <li>2~5人游戏，每人分配不同颜色和固定初始点。</li>
            <li>每回合分两步：<b>移动</b>（直线1~3格，不能穿墙/越子/原地不动），<b>筑墙</b>（在落点四周放一堵墙）。</li>
            <li>墙体不能重复、不能封死所有玩家最后一条出路。</li>
            <li>当所有玩家被完全隔绝或无法行动时，游戏结束。</li>
            <li>每人计算自己所在封闭区域的空格数，最多者胜。平分则最后筑墙者胜。</li>
          </ol>
          <div style="margin:12px 0 0 0;">操作说明：</div>
          <ul style="line-height:1.7;font-size:1em;">
            <li>点击“加入房间”后等待其他玩家，房主可点击“开始游戏”。</li>
            <li>轮到你时，点击棋盘高亮点进行移动，随后输入墙体方向（up/down/left/right）筑墙。</li>
            <li>点击“重置”可重新开始。</li>
          </ul>
        </div>
      </div>
    </div>`;
    document.body.appendChild(helpDiv);
};

// 页面切换/回合切换时重置movePath
window.addEventListener('DOMContentLoaded', () => { resetMoveState(); });
setInterval(()=>{ resetMoveState(); fetchGameState(); }, 2000);
fetchGameState(); 