//const API_URL = "http://127.0.0.1:8000";
//const WS_URL = "ws://127.0.0.1:8000/ws/simulate";
const CLOUD_URL = "https://dynami-learn.onrender.com"
const API_URL = `https://${CLOUD_URL}`;
const WS_URL = `wss://${CLOUD_URL}/ws/simulate`;

let ws = null;
let isRunning = false;
let systemPeriods = [];
let maxAbsDisp = 0.00001;

// Multi-Chart Storage
let activeCharts = [];

// --- CHART PLUGINS ---
const quakePlugin = {
    id: 'quakeLine',
    afterDraw: (chart) => {
        const type = document.getElementById("force-type").value;
        if (type === 'pulse') {
            const duration = parseFloat(document.getElementById("num-dur").value);
            const T_norm = chart.config.options.scales.x.customPeriod || 1.0;
            const normVal = duration / T_norm;
            const xAxis = chart.scales.x;

            if (normVal >= xAxis.min && normVal <= xAxis.max) {
                const ctx = chart.ctx;
                const xPixel = xAxis.getPixelForValue(normVal);
                const yAxis = chart.scales.y;
                ctx.save();
                ctx.beginPath();
                ctx.moveTo(xPixel, yAxis.top);
                ctx.lineTo(xPixel, yAxis.bottom);
                ctx.lineWidth = 2;
                ctx.strokeStyle = '#10b981';
                ctx.setLineDash([5, 5]);
                ctx.stroke();
                ctx.fillStyle = '#10b981';
                ctx.textAlign = 'left';
                ctx.fillText('Quake End', xPixel + 5, yAxis.top + 10);
                ctx.restore();
            }
        }
    }
};
Chart.register(quakePlugin);

// --- INIT ---
// --- INIT ---
window.onload = function() {
    console.log("Initializing...");

    // 1. קודם כל: הגדרת ברירת מחדל ויצירת סליידרים לריסון
    // חובה שזה יקרה לפני כל דבר אחר!
    const dofSelect = document.getElementById('dof-select');
    if(dofSelect) dofSelect.value = "2";

    onDofChange(); // יוצר את ה-HTML של הריסון (z1, z2)

    // 2. רק עכשיו אפשר לסנכרן את שאר הכפתורים
    syncInputs('E', true);
    syncInputs('M', true);
    syncInputs('F', true);
    syncInputs('dur', true);

    // 3. עדכון פרופיל גיאומטרי
    updateProfileType();

    // 4. חישוב ראשוני (עם השהייה קטנה לביטחון שהשרת עונה)
    setTimeout(() => {
        calculateSystem();
    }, 500);

    // הערה: מחקתי את הקוד של btn-calc כי יש כבר onclick="calculateSystem()" ב-HTML.
};

// --- TABS LOGIC ---
function initTabsAndCharts(periods) {
    const header = document.getElementById('tabs-header');
    const body = document.getElementById('tabs-body');

    header.innerHTML = '';
    body.innerHTML = '';
    activeCharts.forEach(c => c.destroy());
    activeCharts = [];

    periods.forEach((T, i) => {
        const modeNum = i + 1;
        const btn = document.createElement('button');
        btn.className = `tab-btn ${i === 0 ? 'active' : ''}`;
        btn.innerText = `Mode ${modeNum} (T=${T.toFixed(3)}s)`;
        btn.onclick = () => switchTab(i);
        header.appendChild(btn);

        const contentDiv = document.createElement('div');
        contentDiv.className = `tab-content ${i === 0 ? 'active' : ''}`;
        contentDiv.id = `tab-content-${i}`;

        const canvasContainer = document.createElement('div');
        canvasContainer.className = 'chart-container';
        const canvas = document.createElement('canvas');
        canvas.id = `chart-${i}`;

        canvasContainer.appendChild(canvas);
        contentDiv.appendChild(canvasContainer);
        body.appendChild(contentDiv);

        const ctx = canvas.getContext('2d');
        const newChart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: [
                    { label: 'Disp', data: [], borderColor: '#38bdf8', borderWidth: 2, pointRadius: 0, hidden: !document.getElementById('chk-x').checked },
                    { label: 'Vel', data: [], borderColor: '#10b981', borderWidth: 2, pointRadius: 0, hidden: !document.getElementById('chk-v').checked },
                    { label: 'Acc', data: [], borderColor: '#f59e0b', borderWidth: 2, pointRadius: 0, hidden: !document.getElementById('chk-a').checked }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                    x: {
                        type: 'linear', min: 0, max: 20, grid: { color: '#334155' },
                        title: { display: true, text: `Normalized Time (t / T${modeNum})`, color: '#94a3b8' },
                        customPeriod: T
                    },
                    y: { grid: { color: '#334155' }, ticks: { color: '#94a3b8', callback: (v) => Number(v).toExponential(1) } }
                },
                plugins: { legend: { display: false } }
            }
        });
        activeCharts.push({ chart: newChart, period: T });
    });
}

function switchTab(index) {
    const btns = document.querySelectorAll('.tab-btn');
    btns.forEach((b, i) => b.classList.toggle('active', i === index));

    const contents = document.querySelectorAll('.tab-content');
    contents.forEach((c, i) => c.classList.toggle('active', i === index));
}

// --- WEBSOCKET & LOCKING ---
function toggleSimulation() {
    const btn = document.getElementById("btn-sim");
    if (isRunning) {
        if (ws) ws.close();
        isRunning = false;
        btn.innerText = "Start Simulation";
        btn.classList.remove("running");

        // --- תוקן: שחרור נעילה ---
        document.body.classList.remove("sim-running");
    } else {
        startWebSocket();
    }
}

function startWebSocket() {
    if (ws) ws.close();

    const payload = {
        model_req: getModelPayload(),
        sim_req: {
            t0: 0, dt: 0.02,
            force_function: {
                type: document.getElementById("force-type").value,
                amp: 1000,
                freq: parseFloat(document.getElementById("num-F").value) * 2 * Math.PI,
                duration: parseFloat(document.getElementById("num-dur").value)
            },
            damping_ratios: getDampingValues()
        }
    };

    ws = new WebSocket(WS_URL);
    const btn = document.getElementById("btn-sim");
    btn.innerText = "Connecting...";

    ws.onopen = () => {
        ws.send(JSON.stringify(payload));
        isRunning = true;
        btn.innerText = "Stop Simulation";
        btn.classList.add("running");

        // --- תוקן: הפעלת נעילה ---
        document.body.classList.add("sim-running");

        activeCharts.forEach(obj => {
            obj.chart.data.datasets.forEach(ds => ds.data = []);
            obj.chart.update();
        });
        maxAbsDisp = 0.00001;
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'DATA') {
            activeCharts.forEach(obj => {
                const chart = obj.chart;
                const T = obj.period;
                const normT = msg.t / T;

                chart.data.datasets[0].data.push({ x: normT, y: msg.x });
                chart.data.datasets[1].data.push({ x: normT, y: msg.v });
                chart.data.datasets[2].data.push({ x: normT, y: msg.a });

                const win = 20;
                const ax = chart.options.scales.x;
                if (normT > win) { ax.min = normT - win; ax.max = normT; }
                else { ax.min = 0; ax.max = win; }

                chart.update('none');
            });

            drawFrame(msg.all_x);
        }
        else if (msg.type === 'ERROR') {
            alert("Sim Error: " + msg.message);
            toggleSimulation();
        }
    };
    ws.onclose = () => { if (isRunning) toggleSimulation(); };
}

// --- HELPERS ---
function updateGraphVisibility() {
    activeCharts.forEach(obj => {
        const c = obj.chart;
        c.setDatasetVisibility(0, document.getElementById('chk-x').checked);
        c.setDatasetVisibility(1, document.getElementById('chk-v').checked);
        c.setDatasetVisibility(2, document.getElementById('chk-a').checked);
        c.update();
    });
}

function syncInputs(id, fS) {
    const s = document.getElementById('slide-' + id), n = document.getElementById('num-' + id);
    if (fS) n.value = s.value; else s.value = n.value;
    if (['r', 'b', 'h'].includes(id)) updateGeometry();
    if (id === 'F') document.getElementById('val-w').innerText = `(ω=${(parseFloat(n.value) * 6.28).toFixed(1)})`;
}

function validateInput(id) {
    const n = document.getElementById('num-' + id), s = document.getElementById('slide-' + id);
    let v = parseFloat(n.value);
    if (isNaN(v)) v = parseFloat(n.min);
    n.value = v; s.value = v;
    if (['r', 'b', 'h'].includes(id)) updateGeometry();
}

function onDofChange() {
        // --- תיקון: איפוס מלא למניעת התנגשות מימדים ---
        resetSimulation();
        // ---------------------------------------------

        const c = parseInt(document.getElementById('dof-select').value);
        const d = document.getElementById('damping-container');
        d.innerHTML = '';
        for (let i = 1; i <= c; i++) {
            d.innerHTML += `<div class="label-row"><label style="width:30px">ζ${i}:</label><div class="input-group" style="flex:1"><input type="range" id="slide-z${i}" min="0" max="1" step="0.01" value="0.02" oninput="syncZeta(${i},true)"><input type="number" id="num-z${i}" value="0.02" min="0" max="1" step="0.01" oninput="syncZeta(${i},false)"></div></div>`;
        }
        drawFrame(new Array(c).fill(0));
        calculateSystem();
    }

window.syncZeta = function(i, s) {
    const sl = document.getElementById(`slide-z${i}`), nm = document.getElementById(`num-z${i}`);
    if (s) nm.value = sl.value; else sl.value = nm.value;
}

function getDampingValues() {
    const c = parseInt(document.getElementById('dof-select').value);
    let a = [];
    for (let i = 1; i <= c; i++) a.push(parseFloat(document.getElementById(`num-z${i}`).value));
    return a;
}

function toggleDuration() {
    document.getElementById('dur-box').style.display = document.getElementById('force-type').value === 'pulse' ? 'block' : 'none';
}

function updateProfileType() {
    const t = document.getElementById('profile-type').value;
    const b = document.getElementById('geo-inputs');
    if (t === 'circle') {
        b.innerHTML = `<div class="label-row"><label>Radius (r) [m]:</label></div><div class="input-group"><input type="range" id="slide-r" min="0.1" max="0.6" step="0.01" value="0.25" oninput="syncInputs('r',true)"><input type="number" id="num-r" value="0.25" min="0.01" max="0.6" step="0.01" oninput="syncInputs('r',false)" onchange="validateInput('r')"></div>`;
    } else {
        b.innerHTML = `<div class="label-row"><label>Width (b) [m]:</label></div><div class="input-group"><input type="range" id="slide-b" min="0.1" max="1.0" step="0.01" value="0.4" oninput="syncInputs('b',true)"><input type="number" id="num-b" value="0.4" min="0.01" max="1.0" step="0.01" oninput="syncInputs('b',false)" onchange="validateInput('b')"></div><div class="label-row"><label>Height (h) [m]:</label></div><div class="input-group"><input type="range" id="slide-h" min="0.1" max="1.0" step="0.01" value="0.4" oninput="syncInputs('h',true)"><input type="number" id="num-h" value="0.4" min="0.01" max="1.0" step="0.01" oninput="syncInputs('h',false)" onchange="validateInput('h')"></div>`;
    }
    updateGeometry();
}

function updateGeometry() {
    const t = document.getElementById('profile-type').value;
    let I = 0;
    if (t === 'circle') {
        const el = document.getElementById('num-r');
        const r = el ? parseFloat(el.value) : 0.25;
        I = Math.PI * Math.pow(r, 4) / 4;
    } else {
        const elB = document.getElementById('num-b');
        const elH = document.getElementById('num-h');
        const b = elB ? parseFloat(elB.value) : 0.4;
        const h = elH ? parseFloat(elH.value) : 0.4;
        I = b * Math.pow(h, 3) / 12;
    }
    document.getElementById('val-Ic').innerText = I.toFixed(6);
}

function getModelPayload() {
    const dofs = parseInt(document.getElementById('dof-select').value);
    const E = parseFloat(document.getElementById('num-E').value);
    const M = parseFloat(document.getElementById('num-M').value);

    // Recalculate I to be safe
    const t = document.getElementById('profile-type').value;
    let I = 0;
    if (t === 'circle') {
        const r = parseFloat(document.getElementById('num-r').value);
        I = Math.PI * Math.pow(r, 4) / 4;
    } else {
        const b = parseFloat(document.getElementById('num-b').value);
        const h = parseFloat(document.getElementById('num-h').value);
        I = b * Math.pow(h, 3) / 12;
    }

    const arr = (v) => Array(dofs).fill().map(() => Array(2).fill(v));
    return {
        "Hc": arr(3.0), "Ec": arr(E), "Ic": arr(I), "Lb": arr(6.0),
        "depth": 6.0, "floor_load": M, "base_condition": 1,
        "damping_ratios": getDampingValues()
    };
}

// --- SERVER COMM ---
async function calculateSystem() {
    try {
        const res = await fetch(`${API_URL}/shear-building/modal`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(getModelPayload())
        });
        const data = await res.json();

        systemPeriods = data.frequencies.map(w => 2 * Math.PI / w);
        initTabsAndCharts(systemPeriods); // Build tabs

        let h = `<table class="modes-table"><tr><th>Mode</th><th>Freq</th><th>T</th></tr>`;
        data.frequencies.forEach((w, i) => h += `<tr><td>${i + 1}</td><td>${(w / 6.28).toFixed(2)}Hz</td><td style="color:#38bdf8">${(6.28 / w).toFixed(3)}s</td></tr>`);
        h += `</table><span class="mat-label">Mass [M]:</span>`;
        data.M_matrix.forEach(r => h += `<div class="mat-row">[ ${r.map(n => n.toFixed(0)).join(", ")} ]</div>`);
        h += `<span class="mat-label">Stiffness [K]:</span>`;
        data.K_matrix.forEach(r => h += `<div class="mat-row">[ ${r.map(n => n.toExponential(1)).join(", ")} ]</div>`);
        document.getElementById("results-area").innerHTML = h;
    } catch (e) {
        console.error(e);
    }
}

function drawFrame(disps) {
    const c = document.getElementById("vizCanvas");
    const ctx = c.getContext("2d");
    const r = c.parentElement.getBoundingClientRect();
    c.width = r.width;
    c.height = r.height;

    const w = c.width, h = c.height, f = disps.length;
    const dMax = Math.max(maxAbsDisp, 0.001);
    const sX = (w * 0.3) / dMax;
    const fH = (h * 0.8) / f;

    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, w, h);
    ctx.lineWidth = 3;
    ctx.lineCap = "round";

    const cx = w / 2, gy = h - 20;

    ctx.strokeStyle = "#444";
    ctx.beginPath();
    ctx.moveTo(cx - 100, gy);
    ctx.lineTo(cx + 100, gy);
    ctx.stroke();

    for (let i = 0; i < f; i++) {
        const yB = gy - i * fH, yT = gy - (i + 1) * fH;
        const xB = (i === 0) ? 0 : disps[i - 1] * sX;
        const xTop = disps[i] * sX;

        ctx.strokeStyle = "#38bdf8";
        ctx.beginPath(); ctx.moveTo(cx - 50 + xB, yB); ctx.lineTo(cx - 50 + xTop, yT); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(cx + 50 + xB, yB); ctx.lineTo(cx + 50 + xTop, yT); ctx.stroke();

        ctx.strokeStyle = "#fff";
        ctx.beginPath(); ctx.moveTo(cx - 50 + xTop, yT); ctx.lineTo(cx + 50 + xTop, yT); ctx.stroke();

        ctx.fillStyle = "#ef4444";
        ctx.beginPath(); ctx.arc(cx + xTop, yT, 6, 0, 6.28); ctx.fill();
    }
}