import sys
import os
import json
import torch
import kociemba
import serial
import time
from flask import Flask, request, jsonify, render_template_string

MOTOR_DELAY = 1.5
COM_PORT = 'COM11'
BAUD_RATE = 9600    

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from ai.model import Pilgrim
from ai.searcher import Searcher

app = Flask(__name__)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"\n[SYSTEM] Initializing AI on device: {device.type.upper()}")

WEIGHTS_PATH = os.path.join(BASE_DIR, 'models', 'p054-t000_333_e08192.pth')
GENERATOR_PATH = os.path.join(BASE_DIR, 'config', 'p054.json')
TARGET_PATH = os.path.join(BASE_DIR, 'models', 'p054-t000.pt')
INFO_PATH = os.path.join(BASE_DIR, 'logs', 'model_p054-t000_333.json')

with open(GENERATOR_PATH, "r") as f:
    data = json.load(f)
    all_moves, move_names = (data["moves"], data["move_names"]) if "moves" in data else (list(data.values())[0], list(data.values())[1])

all_moves_tensor = torch.tensor(all_moves, dtype=torch.int64, device=device)
V0 = torch.load(TARGET_PATH, weights_only=True, map_location=device)
with open(INFO_PATH, "r") as f: info = json.load(f)

model = Pilgrim(num_classes=torch.unique(V0).numel(), state_size=all_moves_tensor.size(1), 
                hd1=info["hd1"], hd2=info["hd2"], nrd=info["nrd"], dropout_rate=info.get("dropout", 0.0))
model.load_state_dict(torch.load(WEIGHTS_PATH, weights_only=False, map_location=device), strict=True)
model.eval().to(device)
model.dtype = torch.float16 if device.type == "cuda" else torch.float32
searcher = Searcher(model=model, all_moves=all_moves_tensor, V0=V0, device=device, verbose=0)

try:
    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
    print(f"[+] Connected to Master Arduino on {COM_PORT}")
except Exception:
    print("[-] Serial Connection Failed. Running in Simulation Mode.")
    ser = None

def apply_moves(state, seq_str):
    curr = state.clone()
    for m in seq_str.strip().split():
        if m in move_names:
            curr = curr[all_moves_tensor[move_names.index(m)]]
        elif '2' in m:
            base = m[0]
            curr = curr[all_moves_tensor[move_names.index(base)]]
            curr = curr[all_moves_tensor[move_names.index(base)]]
    return curr

def solve_progressive(state):
    for b in [256, 1024, 4096, 16384]:
        res = searcher.get_solution(state, B=b, num_steps=200, num_attempts=1)
        if res[0] is not None:
            return " ".join([move_names[i] for i in res[0].tolist()])
    return None

INDEX_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>AI 3D Cube Solver</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: 'Segoe UI', sans-serif; text-align: center; background-color: #1e1e1e; color: #fff; margin: 0; padding: 10px; overflow-x: hidden; }
    .container { max-width: 600px; margin: auto; }
    .box { background: #2d2d2d; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
    button { padding: 10px 14px; margin: 4px; font-weight: bold; cursor: pointer; border: none; border-radius: 6px; transition: 0.2s; }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-move { background: #3498db; color: white; width: 50px; }
    .btn-action { background: #2ecc71; color: white; width: 100%; }
    .btn-solve { background: #e67e22; color: white; width: 100%; font-size: 18px; margin-top:10px; }
    .btn-toggle { background: #f39c12; color: white; width: 100%; padding: 12px; margin-bottom: 10px; }
    .output-text { color: #f1c40f; font-family: monospace; font-size: 18px; min-height: 22px; margin: 10px 0; }
    #view3D { display: flex; flex-direction: column; align-items: center; height: 350px; }
    .scene { width: 150px; height: 150px; perspective: 800px; margin-top: 30px; cursor: grab; }
    .cube-wrapper { width: 100%; height: 100%; position: relative; transform-style: preserve-3d; transform: rotateX(-20deg) rotateY(-45deg); }
    #cube, #pivot { width: 100%; height: 100%; position: absolute; transform-style: preserve-3d; }
    .cubie { position: absolute; width: 50px; height: 50px; left: 50px; top: 50px; transform-style: preserve-3d; }
    .sticker { position: absolute; width: 46px; height: 46px; margin: 2px; border-radius: 4px; border: 2px solid #000; }
    .s-U { transform: rotateX(90deg) translateZ(25px); } .s-D { transform: rotateX(-90deg) translateZ(25px); }
    .s-R { transform: rotateY(90deg) translateZ(25px); } .s-L { transform: rotateY(-90deg) translateZ(25px); }
    .s-F { transform: translateZ(25px); } .s-B { transform: rotateY(180deg) translateZ(25px); }
    .hidden { display: none !important; }
    #cubeCanvas { background: #222; border-radius: 8px; border: 1px solid #444; cursor: pointer; }
  </style>
</head>
<body>
  <div class="container">
    <h2>AI 3D Cube Solver</h2>
    <div class="box">
      <button class="btn-toggle" id="modeToggle" onclick="toggleMode()">Switch to Paint Mode</button>
      <div id="view3D">
        <div class="scene" id="scene"><div class="cube-wrapper" id="cubeWrapper"><div id="cube"></div><div id="pivot"></div></div></div>
      </div>
      <div id="view2D" class="hidden">
        <canvas id="cubeCanvas" width="240" height="180"></canvas>
        <button class="btn-solve" style="background:#27ae60;" onclick="finishMapping()">Finish Mapping</button>
      </div>
    </div>
    <div class="box" id="controlsBox">
      <p id="scrambleStr" class="output-text">Ready...</p>
      <div id="moveButtons">
        <button class="btn-move" onclick="userMove('U')">U</button><button class="btn-move" onclick="userMove('D')">D</button>
        <button class="btn-move" onclick="userMove('R')">R</button><button class="btn-move" onclick="userMove('L')">L</button>
        <button class="btn-move" onclick="userMove('F')">F</button><button class="btn-move" onclick="userMove('B')">B</button><br>
        <button class="btn-move" onclick="userMove('U\'')">U'</button><button class="btn-move" onclick="userMove('D\'')">D'</button>
        <button class="btn-move" onclick="userMove('R\'')">R'</button><button class="btn-move" onclick="userMove('L\'')">L'</button>
        <button class="btn-move" onclick="userMove('F\'')">F'</button><button class="btn-move" onclick="userMove('B\'')">B'</button>
      </div>
      <div style="margin-top:10px;">
        <button class="btn-action" onclick="generateScramble()">Random Scramble</button>
      </div>
    </div>
    <div class="box" id="solveBox">
      <button class="btn-solve" id="solveBtn" onclick="solveCube()">Ask AI to Solve</button>
      <p id="solutionStr" class="output-text">Waiting...</p>
    </div>
  </div>
  <script>
    let currentScramble = []; let isAnimating = false; let isPaintMode = false; let cubies = [];
    const colors = ['#ffffff', '#e74c3c', '#2ecc71', '#f1c40f', '#e67e22', '#3498db'];
    const faceLetters = ['U', 'R', 'F', 'D', 'L', 'B'];
    let paintState = new Array(54).fill(0).map((_, i) => Math.floor(i/9));

    function init3DCube() {
        const cube = document.getElementById('cube'); cube.innerHTML = ''; cubies = [];
        for(let x=-1; x<=1; x++) {
            for(let y=-1; y<=1; y++) {
                for(let z=-1; z<=1; z++) {
                    let c = document.createElement('div'); c.className = 'cubie'; c.logical = {x, y, z};
                    let faces = [{a:'y',v:-1,s:'s-U',c:0},{a:'x',v:1,s:'s-R',c:1},{a:'z',v:1,s:'s-F',c:2},{a:'y',v:1,s:'s-D',c:3},{a:'x',v:-1,s:'s-L',c:4},{a:'z',v:-1,s:'s-B',c:5}];
                    faces.forEach(f => {
                        let st = document.createElement('div'); st.className = 'sticker ' + f.s;
                        if((f.a==='x'&&x===f.v)||(f.a==='y'&&y===f.v)||(f.a==='z'&&z===f.v)) st.style.background = colors[f.c];
                        c.appendChild(st);
                    });
                    c.style.transform = `translate3d(${x*50}px, ${y*50}px, ${z*50}px)`;
                    cube.appendChild(c); cubies.push(c);
                }
            }
        }
    }

    async function animateMove(move, duration) {
        if(isAnimating || !move) return;
        isAnimating = true;
        let base = move[0], mod = move[1] || '', dir = mod==="'"? -1 : (mod==='2'? 2 : 1);
        let axis, val, angle;
        if(base==='U'){axis='y';val=-1;angle=-90*dir} if(base==='D'){axis='y';val=1;angle=90*dir}
        if(base==='R'){axis='x',val=1,angle=90*dir} if(base==='L'){axis='x',val=-1,angle=-90*dir}
        if(base==='F'){axis='z',val=1,angle=90*dir} if(base==='B'){axis='z',val=-1,angle=-90*dir}

        let piv = document.getElementById('pivot');
        let moving = cubies.filter(c => c.logical[axis] === val);
        moving.forEach(c => piv.appendChild(c));
        piv.style.transition = duration > 0 ? `transform ${duration}ms ease-in-out` : 'none';
        piv.style.transform = `rotate${axis.toUpperCase()}(${angle}deg)`;

        await new Promise(r => setTimeout(r, duration + 20));
        piv.style.transition = 'none'; piv.style.transform = 'none';
        moving.forEach(c => {
            c.style.transform = `rotate${axis.toUpperCase()}(${angle}deg) ` + c.style.transform;
            document.getElementById('cube').appendChild(c);
            let {x,y,z} = c.logical; let rad = angle*Math.PI/180; let cos=Math.round(Math.cos(rad)), sin=Math.round(Math.sin(rad));
            if(axis==='x'){c.logical.y=y*cos-z*sin; c.logical.z=y*sin+z*cos}
            if(axis==='y'){c.logical.x=x*cos+z*sin; c.logical.z=-x*sin+z*cos}
            if(axis==='z'){c.logical.x=x*cos-y*sin; c.logical.y=x*sin+y*cos}
        });
        isAnimating = false;
    }

    function toggleMode() {
        if(isAnimating) return;
        isPaintMode = !isPaintMode;
        document.getElementById("modeToggle").innerText = isPaintMode ? "Return to 3D View" : "Switch to Paint Mode";
        document.getElementById("view3D").classList.toggle("hidden");
        document.getElementById("view2D").classList.toggle("hidden");
        document.getElementById("controlsBox").classList.toggle("hidden");
        document.getElementById("solveBox").classList.toggle("hidden");
        if(isPaintMode) drawPaint();
        else resetState();
    }

    function resetState() {
        currentScramble = [];
        document.getElementById("scrambleStr").innerText = "Ready...";
        document.getElementById("solutionStr").innerText = "Waiting...";
        init3DCube();
    }

    async function userMove(m) {
        if(isAnimating) return;
        currentScramble.push(m);
        document.getElementById("scrambleStr").innerText = currentScramble.join(" ");
        await animateMove(m, 300);
        fetch('/api/manual', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({move: m}) });
    }

    async function generateScramble() {
        if(isAnimating) return;
        resetState();
        const moves = ['U','D','R','L','F','B'], mods = ['', "'", '2'];
        let scrambleList = [];
        for(let i=0; i<20; i++) {
            let m = moves[Math.floor(Math.random()*6)] + mods[Math.floor(Math.random()*3)];
            scrambleList.push(m);
            currentScramble.push(m);
            await animateMove(m, 0); 
        }
        document.getElementById("scrambleStr").innerText = currentScramble.join(" ");
        fetch('/api/hardware', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({solution: scrambleList.join(" ")}) });
    }

    function finishMapping() {
        let cubeStr = paintState.map(v => faceLetters[v]).join('');
        fetch('/api/validate', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({cube_string: cubeStr}) })
        .then(res => res.json()).then(async data => {
            if(data.error) alert("Invalid Mapping: " + data.error);
            else {
                toggleMode(); 
                if(data.scramble) {
                    let moves = data.scramble.split(" ");
                    for(let m of moves) { await animateMove(m, 0); currentScramble.push(m); }
                    document.getElementById("scrambleStr").innerText = "Custom State Loaded";
                }
            }
        });
    }

    function solveCube() {
        if(isAnimating) return;
        document.getElementById("solveBtn").disabled = true;
        document.getElementById("solutionStr").innerText = "AI Solving...";
        fetch('/api/solve', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ scramble: currentScramble.join(" ") }) })
        .then(res => res.json()).then(async data => {
            document.getElementById("solveBtn").disabled = false;
            if(data.error) alert(data.error);
            else {
                document.getElementById("solutionStr").innerText = data.solution;
                fetch('/api/hardware', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({solution: data.solution}) });
                let moves = data.solution.split(" ");
                for(let m of moves) { await animateMove(m, 300); await new Promise(r => setTimeout(r, 800)); }
            }
        });
    }

    function drawPaint() {
        const ctx = document.getElementById('cubeCanvas').getContext('2d');
        ctx.clearRect(0,0,240,180);
        const offsets = [{x:54,y:0},{x:108,y:54},{x:54,y:54},{x:54,y:108},{x:0,y:54},{x:162,y:54}];
        for(let f=0; f<6; f++){
            for(let i=0; i<9; i++){
                ctx.fillStyle = colors[paintState[f*9+i]];
                ctx.fillRect(offsets[f].x+10+(i%3)*18, offsets[f].y+10+Math.floor(i/3)*18, 16, 16);
                ctx.strokeStyle = "#000"; ctx.strokeRect(offsets[f].x+10+(i%3)*18, offsets[f].y+10+Math.floor(i/3)*18, 16, 16);
            }
        }
    }

    document.getElementById('cubeCanvas').onclick = (e) => {
        if(!isPaintMode || isAnimating) return;
        const rect = e.target.getBoundingClientRect();
        const x = e.clientX - rect.left, y = e.clientY - rect.top;
        const offsets = [{x:54,y:0},{x:108,y:54},{x:54,y:54},{x:54,y:108},{x:0,y:54},{x:162,y:54}];
        for(let f=0; f<6; f++){
            for(let i=0; i<9; i++){
                let sx = offsets[f].x+10+(i%3)*18, sy = offsets[f].y+10+Math.floor(i/3)*18;
                if(x>=sx && x<=sx+16 && y>=sy && y<=sy+16) { paintState[f*9+i] = (paintState[f*9+i]+1)%6; drawPaint(); return; }
            }
        }
    };
    window.onload = init3DCube;
  </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

def send_and_wait(move):
    if not ser:
        return
    ser.write(f"{move}\n".encode())
    while True:
        line = ser.readline().decode().strip()
        if line:
            print(line)
        if line == "DONE":
            break

@app.route('/api/manual', methods=['POST'])
def manual_move():
    move = request.json.get('move')
    send_and_wait(move)
    return jsonify({'status': 'ok'})

@app.route('/api/validate', methods=['POST'])
def validate_cube():
    cube_str = request.json.get('cube_string', '')
    try:
        solution = kociemba.solve(cube_str)
        scramble = []
        for m in reversed(solution.split()):
            if "'" in m:
                scramble.append(m[0])
            elif "2" in m:
                scramble.append(m)
            else:
                scramble.append(m + "'")
        return jsonify({'scramble': " ".join(scramble)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/solve', methods=['POST'])
def solve_api():
    scramble = request.json.get('scramble', '')
    print(f"\n[AI QUESTION] State sequence: {scramble}")
    try:
        state = apply_moves(V0, scramble)
        solution = solve_progressive(state)
        print(f"[AI ANSWER] Found solution: {solution}")
        return jsonify({'solution': solution})
    except Exception as e:
        print(f"[AI ERROR] Failed: {str(e)}")
        return jsonify({'error': str(e)})

@app.route('/api/hardware', methods=['POST'])
def hardware_api():
    sol = request.json.get('solution', '')
    if sol:
        for m in sol.split():
            send_and_wait(m)
    return jsonify({'status': 'sent'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)