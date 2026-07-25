/**
 * DYNAMI-LEARN | PROFESSIONAL EDITION
 * Main Logic Script
 */

// --- 1. SERVER CONNECTION SETUP ---
const isLocal = window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost";

const API_URL = isLocal ? "http://127.0.0.1:8000" : window.location.origin;
const WS_URL  = isLocal
    ? "ws://127.0.0.1:8000/ws/simulate"
    : `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws/simulate`;

console.log(`Running in ${isLocal ? "LOCAL" : "PRODUCTION"} mode. Connected to: ${API_URL}`);

// Fixed structural geometry values — not wired into the physics (Lb/depth don't affect K or M
// in the current codebase), kept as named constants to document intent and avoid magic numbers.
const FIXED_BEAM_SPAN_M      = 6.0;  // Lb  — center-to-center bay width [m]
const FIXED_BUILDING_DEPTH_M = 6.0;  // depth — out-of-plane dimension [m]

// --- 2. GLOBAL VARIABLES ---
let ws = null;
let isRunning = false;
let isPaused = false;
let systemPeriods = [];
let maxAbsDisp = 0.00001;
let activeCharts = [];
let exactFreqFromSet = null;
let isAutoScroll = true;
let lastState = { t:0, all_x:null, all_v:null };
let resultsDirty = true;

// --- 3. CANVAS / CHART PALETTE HELPER ---
function getCanvasPalette() {
    const attr = document.documentElement.getAttribute('data-theme');
    const isDark = attr === 'dark'
        || (attr === null && !window.matchMedia('(prefers-color-scheme: light)').matches);
    return isDark
        ? { bg: '#0A0F0A', grid: '#212B23', text: '#ECEBE3', textMuted: '#8FA091',
            accent: '#86B893', accentFill: 'rgba(134,184,147,0.15)',
            danger: '#C1666B', success: '#6FAE7C', gold: '#C9A227' }
        : { bg: '#E4E9DF', grid: '#E1E6DA', text: '#1B231D', textMuted: '#57685A',
            accent: '#2F6B4A', accentFill: 'rgba(47,107,74,0.12)',
            danger: '#A14A44', success: '#3F8557', gold: '#8A6A16' };
}

// --- 4. CHART PLUGINS ---
const quakePlugin = {
    id: 'quakeLine',
    afterDraw: (chart) => {
        const typeEl = document.getElementById("force-type");
        if (!typeEl) return;

        const type = typeEl.value;
        // מצייר קו סיום רק במצב Pulse
        if (type === 'pulse') {
            const durationEl = document.getElementById("num-dur");
            if(!durationEl) return;

            const duration = parseFloat(durationEl.value);
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
                ctx.strokeStyle = getCanvasPalette().success;
                ctx.setLineDash([5, 5]);
                ctx.stroke();
                ctx.fillStyle = getCanvasPalette().success;
                ctx.textAlign = 'left';
                ctx.fillText('Force End', xPixel + 5, yAxis.top + 10);
                ctx.restore();
            }
        }
    }
};
Chart.register(quakePlugin);

// --- 4. INITIALIZATION ---
window.onload = function() {
    console.log("Initializing Application...");

    // Apply saved theme before first render
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) document.documentElement.setAttribute('data-theme', savedTheme);

    // הגדרת ברירת מחדל
    const dofSelect = document.getElementById('dof-select');
    if(dofSelect) dofSelect.value = "2";

    // בניית הממשק הדינמי (קריטי שזה ירוץ ראשון)
    onDofChange();

    // סינכרון אלמנטים גלובליים
    syncInputs('F', true);
    syncInputs('dur', true);

    // עדכון גיאומטריה
    updateProfileType();

    // אתחול מצב הכפתורים (רעידת אדמה vs כוח)
    toggleDuration();

    // חישוב ראשוני
    setTimeout(() => {
        calculateSystem();
    }, 500);
};

// --- 5. DYNAMIC PROPERTIES LOGIC (NON-UNIFORM FLOORS) ---
function renderPropertiesInputs() {
    const dofs = parseInt(document.getElementById('dof-select').value);
    const container = document.getElementById('dynamic-properties');
    if (!container) return;
    container.innerHTML = '';

    // --- Mass Section (UPDATED) ---
    const massTitle = document.createElement('div');
    massTitle.className = 'label-row';
    // שינינו את הכותרת ל-Mass [ton]
    massTitle.innerHTML = `<label>Floor Mass (M) [ton]: <button class="info-btn" onclick="showTooltip('mass', event)">i</button></label>`;
    container.appendChild(massTitle);

    for (let i = 0; i < dofs; i++) {
        const floorNum = i + 1;
        const val = 50; // ברירת מחדל בטונות
        const row = document.createElement('div');
        row.style.marginBottom = "4px";
        row.innerHTML = `
            <div style="display:flex; align-items:center; gap:5px; font-size:0.8rem; color:var(--text-muted);">
                <span style="width:20px;">F${floorNum}:</span>
                <div class="input-group" style="flex:1">
                    <input type="range" id="slide-M-${i}" min="10" max="200" value="${val}" oninput="syncProp('M', ${i}, true)">
                    <input type="number" id="num-M-${i}" value="${val}" min="1" max="500" oninput="syncProp('M', ${i}, false)" onchange="validateProp('M', ${i})">
                </div>
            </div>
        `;
        container.appendChild(row);
    }

    // --- Stiffness Section ---
    const stiffTitle = document.createElement('div');
    stiffTitle.className = 'label-row';
    stiffTitle.style.marginTop = "10px";
    stiffTitle.innerHTML = `<label>Young's Modulus (E) [GPa]: <button class="info-btn" onclick="showTooltip('E', event)">i</button></label>`;
    container.appendChild(stiffTitle);

    for (let i = 0; i < dofs; i++) {
        const floorNum = i + 1;
        const val = 30;
        const row = document.createElement('div');
        row.style.marginBottom = "4px";
        row.innerHTML = `
            <div style="display:flex; align-items:center; gap:5px; font-size:0.8rem; color:var(--text-muted);">
                <span style="width:20px;">F${floorNum}:</span>
                <div class="input-group" style="flex:1">
                    <input type="range" id="slide-E-${i}" min="10" max="50" value="${val}" oninput="syncProp('E', ${i}, true)">
                    <input type="number" id="num-E-${i}" value="${val}" min="1" max="50" oninput="syncProp('E', ${i}, false)" onchange="validateProp('E', ${i})">
                </div>
            </div>
        `;
        container.appendChild(row);
    }

    // --- Story Height Section ---
    const hcTitle = document.createElement('div');
    hcTitle.className = 'label-row';
    hcTitle.style.marginTop = "10px";
    hcTitle.innerHTML = `<label>Story Height (Hc) [m]: <button class="info-btn" onclick="showTooltip('geometry', event)">i</button></label>`;
    container.appendChild(hcTitle);

    for (let i = 0; i < dofs; i++) {
        const floorNum = i + 1;
        const val = 3.0;
        const row = document.createElement('div');
        row.style.marginBottom = "4px";
        row.innerHTML = `
            <div style="display:flex; align-items:center; gap:5px; font-size:0.8rem; color:var(--text-muted);">
                <span style="width:20px;">F${floorNum}:</span>
                <div class="input-group" style="flex:1">
                    <input type="range" id="slide-Hc-${i}" min="2" max="6" step="0.1" value="${val}" oninput="syncProp('Hc', ${i}, true)">
                    <input type="number" id="num-Hc-${i}" value="${val}" min="1" max="20" step="0.1" oninput="syncProp('Hc', ${i}, false)" onchange="validateProp('Hc', ${i})">
                </div>
            </div>
        `;
        container.appendChild(row);
    }
}

function syncProp(type, idx, fromSlide) {
    const s = document.getElementById(`slide-${type}-${idx}`);
    const n = document.getElementById(`num-${type}-${idx}`);
    if(!s || !n) return;

    if (fromSlide) n.value = s.value;
    else s.value = n.value;

    invalidateResults();
    //calculateSystem();
}

function validateProp(type, idx) {
    const n = document.getElementById(`num-${type}-${idx}`);
    const s = document.getElementById(`slide-${type}-${idx}`);
    if(!s || !n) return;

    let v = parseFloat(n.value);
    if(isNaN(v)) v = parseFloat(s.min);
    n.value = v;
    s.value = v;
    invalidateResults();
    //calculateSystem();
}

function getModelPayload() {
    const dofsEl = document.getElementById('dof-select');
    if(!dofsEl) return null;
    const dofs = parseInt(dofsEl.value);

    let Ec_arr = [];
    let floor_mass_arr = []; // שינוי שם המשתנה

    for(let i=0; i<dofs; i++) {
        const elE = document.getElementById(`num-E-${i}`);
        const elM = document.getElementById(`num-M-${i}`);

        if (!elE || !elM) return null;

        Ec_arr.push(parseFloat(elE.value));
        floor_mass_arr.push(parseFloat(elM.value)); // איסוף מסה בטונות
    }

    // גיאומטריה
    const t = document.getElementById('profile-type').value;
    let I_val = 0;
    if (t === 'circle') {
        const el = document.getElementById('num-r');
        I_val = el ? Math.PI * Math.pow(parseFloat(el.value), 4) / 4 : 0.003;
    } else {
        const elB = document.getElementById('num-b');
        const elH = document.getElementById('num-h');
        const b = elB ? parseFloat(elB.value) : 0.4;
        const h = elH ? parseFloat(elH.value) : 0.4;
        I_val = b * Math.pow(h, 3) / 12;
    }

    const Hc_arr = Array.from({length: dofs}, (_, i) => parseFloat(document.getElementById(`num-Hc-${i}`)?.value ?? 3.0));
    const Lb_arr = Array.from({length: dofs}, () => [FIXED_BEAM_SPAN_M, FIXED_BEAM_SPAN_M]);
    const Ic_arr = Array(dofs).fill(I_val);

    return {
        "Hc": Hc_arr,
        "Ec": Ec_arr,
        "Ic": Ic_arr,
        "Lb": Lb_arr,
        "depth": FIXED_BUILDING_DEPTH_M,
        "floor_mass": floor_mass_arr, // <-- שליחת מפתח חדש
        "base_condition": 1,
        "damping_ratios": getDampingValues()
    };
}

// --- 6. STANDARD UI HANDLERS ---

function onDofChange() {
    resetSimulation();

    const cSelect = document.getElementById('dof-select');
    if(!cSelect) return;
    const c = parseInt(cSelect.value);

    // 1. יצירת כפתורי ריסון
    const d = document.getElementById('damping-container');
    if (d) {
        d.innerHTML = '';
        for (let i = 1; i <= c; i++) {
            d.innerHTML += `<div class="label-row"><label style="width:30px">ζ${i}:</label><div class="input-group" style="flex:1"><input type="range" id="slide-z${i}" min="0" max="1" step="0.01" value="0.02" oninput="syncZeta(${i},true)"><input type="number" id="num-z${i}" value="0.02" min="0" max="1" step="0.01" oninput="syncZeta(${i},false)"></div></div>`;
        }
    }

    // 2. יצירת שדות המסה והקשיחות הדינמיים
    renderPropertiesInputs();

    drawFrame(new Array(c).fill(0));
    invalidateResults();
    //calculateSystem();
}

function syncInputs(id, fS) {
    const s = document.getElementById('slide-' + id);
    const n = document.getElementById('num-' + id);

    if (!s || !n) return;

    if (fS) n.value = s.value; else s.value = n.value;

    // עדכון גיאומטריה (ויזואלי בלבד כרגע)
    if (['r', 'b', 'h'].includes(id)) {
        updateGeometry();
        invalidateResults();
    }
    // עדכון טקסט תדר
    if(id==='F') {
        const isQuake = document.getElementById('force-type').value === 'earthquake';
        if (!isQuake) {
             const valW = document.getElementById('val-w');
             if(valW) valW.innerText=`(ω=${(parseFloat(n.value)*2*Math.PI).toFixed(3)})`;
        }
    }

    // שינוי: מחקנו את השורה שקוראת ל-calculateSystem
}

function validateInput(id) {
    const n = document.getElementById('num-' + id);
    const s = document.getElementById('slide-' + id);
    if (!n || !s) return;

    let v = parseFloat(n.value);
    if (isNaN(v)) v = parseFloat(n.min);
    n.value = v; s.value = v;
    if (['r', 'b', 'h'].includes(id)) updateGeometry();
}

window.syncZeta = function(i, s) {
    const sl = document.getElementById(`slide-z${i}`), nm = document.getElementById(`num-z${i}`);
    if (s) nm.value = sl.value; else sl.value = nm.value;
}

function getDampingValues() {
    const cSelect = document.getElementById('dof-select');
    if (!cSelect) return [0.02];

    const c = parseInt(cSelect.value);
    let a = [];
    for (let i = 1; i <= c; i++) {
        const el = document.getElementById(`num-z${i}`);
        if(el) a.push(parseFloat(el.value));
        else a.push(0.02);
    }
    return a;
}

// לוגיקה לטיפול בסוג הכוח (כולל רעידת אדמה)
function toggleDuration() {
    const forceTypeEl = document.getElementById('force-type');
    if(!forceTypeEl) return;
    const type = forceTypeEl.value;

    const durBox = document.getElementById('dur-box');
    const freqLabelContainer = document.getElementById('val-w') ? document.getElementById('val-w').parentElement.parentElement : null;
    const presetsDiv = document.getElementById('mode-presets');

    const forceInputGroup = document.getElementById('num-F').parentElement;
    const forceLabelRow = forceInputGroup.previousElementSibling;
    const forceLabel = forceLabelRow ? forceLabelRow.querySelector('label') : null;

    if (type === 'earthquake') {
        if(durBox) {
            durBox.style.display = 'block';
            document.getElementById('slide-dur').value = 30;
            document.getElementById('num-dur').value = 30;
        }
        if(freqLabelContainer) freqLabelContainer.style.display = 'none';
        if(presetsDiv) presetsDiv.style.display = 'none';
        if(forceLabel) forceLabel.innerText = "Scale Factor (x Gravity):";

        document.getElementById('slide-F').max = 5;
        document.getElementById('slide-F').value = 1;
        document.getElementById('num-F').value = 1;

    } else {
        if(durBox) {
            durBox.style.display = (type === 'pulse') ? 'block' : 'none';
        }
        if(freqLabelContainer) freqLabelContainer.style.display = 'flex';
        if(presetsDiv) presetsDiv.style.display = 'flex';
        if(forceLabel) forceLabel.innerText = "Force Amp (kN):";

        document.getElementById('slide-F').max = 10;
    }
}

function updateProfileType() {
    const tEl = document.getElementById('profile-type');
    if(!tEl) return;
    const t = tEl.value;
    const b = document.getElementById('geo-inputs');
    if (!b) return;

    if (t === 'circle') {
        b.innerHTML = `<div class="label-row"><label>Radius (r) [m]:</label></div><div class="input-group"><input type="range" id="slide-r" min="0.1" max="0.6" step="0.01" value="0.25" oninput="syncInputs('r',true)"><input type="number" id="num-r" value="0.25" min="0.01" max="0.6" step="0.01" oninput="syncInputs('r',false)" onchange="validateInput('r')"></div>`;
    } else {
        b.innerHTML = `<div class="label-row"><label>Width (b) [m]:</label></div><div class="input-group"><input type="range" id="slide-b" min="0.1" max="1.0" step="0.01" value="0.4" oninput="syncInputs('b',true)"><input type="number" id="num-b" value="0.4" min="0.01" max="1.0" step="0.01" oninput="syncInputs('b',false)" onchange="validateInput('b')"></div><div class="label-row"><label>Height (h) [m]:</label></div><div class="input-group"><input type="range" id="slide-h" min="0.1" max="1.0" step="0.01" value="0.4" oninput="syncInputs('h',true)"><input type="number" id="num-h" value="0.4" min="0.01" max="1.0" step="0.01" oninput="syncInputs('h',false)" onchange="validateInput('h')"></div>`;
    }

    updateGeometry();
    invalidateResults();
}

function updateGeometry() {
    const tEl = document.getElementById('profile-type');
    if(!tEl) return;
    const t = tEl.value;

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
    const valIc = document.getElementById('val-Ic');
    if(valIc) valIc.innerText = I.toFixed(6);
}

// --- 7. GRAPHS & TABS LOGIC ---
function initTabsAndCharts(periods) {
    const header = document.getElementById('tabs-header');
    const body = document.getElementById('tabs-body');

    header.innerHTML = '';
    body.innerHTML = '';
    activeCharts.forEach(c => c.chart.destroy());
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
        const pal = getCanvasPalette();
        const newChart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: [
                    { label: 'Disp', data: [], borderColor: pal.accent, backgroundColor: pal.accentFill, fill: true, borderWidth: 2, pointRadius: 0, hidden: !document.getElementById('chk-x').checked },
                    { label: 'Vel',  data: [], borderColor: pal.success, borderWidth: 2, pointRadius: 0, hidden: !document.getElementById('chk-v').checked },
                    { label: 'Acc',  data: [], borderColor: pal.gold,    borderWidth: 2, pointRadius: 0, hidden: !document.getElementById('chk-a').checked }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false, animation: false,
                scales: {
                    x: {
                        type: 'linear', min: 0, max: 20, grid: { color: pal.grid },
                        title: { display: true, text: `Normalized Time (t / T${modeNum})`, color: pal.textMuted },
                        customPeriod: T
                    },
                    y: { grid: { color: pal.grid }, ticks: { color: pal.textMuted, callback: (v) => Number(v).toExponential(1) } }
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

function updateGraphVisibility() {
    activeCharts.forEach(obj => {
        const c = obj.chart;
        c.setDatasetVisibility(0, document.getElementById('chk-x').checked);
        c.setDatasetVisibility(1, document.getElementById('chk-v').checked);
        c.setDatasetVisibility(2, document.getElementById('chk-a').checked);
        c.update();
    });
}

// --- 8. WEBSOCKET & SIMULATION CONTROL ---
async function toggleSimulation() {
    const btn = document.getElementById("btn-sim");
    const speedSel = document.getElementById("sim-speed");

    if (isRunning) {
        if (ws) ws.close();
        isRunning = false;
        isPaused = true;

        btn.innerText = "Resume";
        btn.className = "action-btn start-btn paused";
        document.body.classList.remove("sim-running");
        if(speedSel) speedSel.disabled = false;

    } else {
        // Auto-calculate whenever results are stale
        if (resultsDirty) {
            const calcBtn = document.querySelector('.calc-btn');
            // Visually activate the Calculate Matrices button
            if (calcBtn) {
                calcBtn.style.background = 'var(--gold)';
                calcBtn.style.color = 'var(--bg)';
                calcBtn.innerText = 'Calculating...';
            }
            btn.innerText = "Calculating...";
            btn.disabled = true;

            await calculateSystem();

            // Restore calc button
            if (calcBtn) {
                calcBtn.style.background = '';
                calcBtn.style.color = '';
                calcBtn.innerText = 'Calculate Matrices';
            }
            btn.disabled = false;
        }
        if(speedSel) speedSel.disabled = true;
        startWebSocket();
    }
}

function resetSimulation() {
    if (ws) ws.close();
    isRunning = false;
    isPaused = false;

    const btn = document.getElementById("btn-sim");
    const speedSel = document.getElementById("sim-speed");

    if(btn) {
        btn.innerText = "Start";
        btn.className = "action-btn start-btn";
    }
    document.body.classList.remove("sim-running");
    if(speedSel) speedSel.disabled = false;

    lastState = { t: 0, all_x: null, all_v: null };
    isAutoScroll = true;

    const timeSlide = document.getElementById('time-slider');
    if(timeSlide) timeSlide.value = 0;

    activeCharts.forEach(obj => {
        obj.chart.data.datasets.forEach(ds => ds.data = []);
        obj.chart.options.scales.x.min = 0;
        obj.chart.options.scales.x.max = 20;
        obj.chart.update();
    });

    const cSelect = document.getElementById('dof-select');
    if(cSelect) {
        const dofs = parseInt(cSelect.value);
        drawFrame(new Array(dofs).fill(0));
    }
}

function startWebSocket() {
    if (ws) ws.close();

    const payload = getModelPayload();
    if (!payload) {
        alert("Initializing... please wait a moment.");
        return;
    }

    const startT = isPaused ? lastState.t : 0;
    const initialConds = isPaused ? { x0: lastState.all_x, v0: lastState.all_v } : {};

    const forceType = document.getElementById("force-type").value;
    const numFVal = parseFloat(document.getElementById("num-F").value);
    const isEarthquake = forceType === "earthquake";

    const speedSel = document.getElementById("sim-speed");
    const simSpeed = speedSel ? parseFloat(speedSel.value) : 1.0;

    const wsPayload = {
        model_req: payload,
        sim_req: {
            t0: startT,
            dt: 0.02,
            speed: simSpeed,
            force_function: {
                type: forceType,
                amp: isEarthquake ? numFVal : 1000,
                freq: isEarthquake ? 0 : numFVal * 2 * Math.PI,
                duration: parseFloat(document.getElementById("num-dur").value)
            },
            damping_ratios: getDampingValues(),
            initial_conditions: initialConds
        }
    };

    ws = new WebSocket(WS_URL);
    const btn = document.getElementById("btn-sim");
    btn.innerText = "Connecting...";

    ws.onopen = () => {
        ws.send(JSON.stringify(wsPayload));
        isRunning = true;

        btn.innerText = "Stop";
        btn.className = "action-btn start-btn running";
        document.body.classList.add("sim-running");

        if(!isPaused) {
            activeCharts.forEach(obj => {
                obj.chart.data.datasets.forEach(ds => ds.data = []);
                obj.chart.update();
            });
            maxAbsDisp = 0.00001;
        }
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'DATA') {

            lastState.t = msg.t;
            lastState.all_x = msg.all_x;
            lastState.all_v = msg.all_v;

            if (msg.all_x) {
                const frameMax = Math.max(...msg.all_x.map(Math.abs));
                if (frameMax > maxAbsDisp) maxAbsDisp = frameMax;
            }

            const slider = document.getElementById('time-slider');
            if(slider) {
                slider.max = msg.t;
                if(isAutoScroll) slider.value = msg.t;
            }

            activeCharts.forEach((obj, i) => {
                const chart = obj.chart;
                const T = obj.period;
                const normT = msg.t / T;

                const floorX = msg.all_x ? msg.all_x[i] : msg.x;
                const floorV = msg.all_v ? msg.all_v[i] : msg.v;
                const floorA = msg.all_a ? msg.all_a[i] : (i === activeCharts.length - 1 ? msg.a : null);

                chart.data.datasets[0].data.push({ x: normT, y: floorX });
                chart.data.datasets[1].data.push({ x: normT, y: floorV });
                if (floorA !== null) chart.data.datasets[2].data.push({ x: normT, y: floorA });

                if (isAutoScroll) {
                    const win = 20;
                    const ax = chart.options.scales.x;
                    if (normT > win) { ax.min = normT - win; ax.max = normT; }
                    else { ax.min = 0; ax.max = win; }
                    chart.update('none');
                }
            });

            drawFrame(msg.all_x);
        }
        else if (msg.type === 'ERROR') {
            alert("Sim Error: " + msg.message);
            toggleSimulation();
        }
    };
    ws.onclose = () => {
        // Only act when the server closed the socket unexpectedly (simulation ended
        // or network dropped). User-triggered stops (toggleSimulation / resetSimulation)
        // set isRunning=false before the socket closes, so we skip those here.
        if (!isRunning) return;

        // Reset to a clean "stopped" state — not "paused", because the server
        // has already ended the session and there is nothing to resume.
        isRunning = false;
        isPaused  = false;

        const btn      = document.getElementById("btn-sim");
        const speedSel = document.getElementById("sim-speed");
        if (btn) {
            btn.innerText = "Start";
            btn.className = "action-btn start-btn";
        }
        document.body.classList.remove("sim-running");
        if (speedSel) speedSel.disabled = false;
    };
}

// --- 9. SERVER CALCULATION ---
async function calculateSystem() {
    try {
        const payload = getModelPayload();
        if (!payload) return;

        console.log("Fetching matrices...");
        const res = await fetch(`${API_URL}/shear-building/modal`, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload) });
        if(!res.ok) throw new Error("Server error");
        const data = await res.json();

        // ... (קוד הגרפים נשאר אותו דבר) ...
        const newPeriods = data.frequencies.map(w => 2*Math.PI/w);
        if(newPeriods.length !== systemPeriods.length) {
            systemPeriods = newPeriods;
            initTabsAndCharts(systemPeriods);
        } else {
            systemPeriods = newPeriods;
            const btns = document.querySelectorAll('.tab-btn');
            btns.forEach((b, i) => { if(systemPeriods[i]) b.innerText = `Mode ${i+1} (T=${systemPeriods[i].toFixed(3)}s)`; });
            activeCharts.forEach((obj, i) => {
                obj.period = systemPeriods[i];
                obj.chart.options.scales.x.title.text = `Normalized Time (t / T${i+1})`;
                obj.chart.options.scales.x.customPeriod = systemPeriods[i];
                obj.chart.update('none');
            });
        }

        // עדכון כפתורים
        const presetsDiv = document.getElementById('mode-presets');
        if(presetsDiv) {
            presetsDiv.innerHTML = '';
            data.frequencies.forEach((w, i) => {
                const freqHz = w / (2 * Math.PI);
                const btn = document.createElement('button');
                btn.className = 'action-btn mode-preset-btn';
                btn.innerText = `Set M${i+1} (${freqHz.toFixed(2)})`;
                btn.onclick = () => setFreqFromMode(freqHz, w);
                presetsDiv.appendChild(btn);
            });
        }

        // === At-a-glance summary tiles — one per mode ===
        let stats = '<div class="stat-row">';
        data.frequencies.forEach((w, i) => {
            const fHz = (w / (2 * Math.PI)).toFixed(2);
            const Ti  = (2 * Math.PI / w).toFixed(3);
            const zi  = (getDampingValues()[i] ?? getDampingValues()[0] ?? 0).toFixed(3);
            const isPrimary = i === 0;
            stats += `<div class="stat-tile${isPrimary ? ' primary' : ''}">
                <div class="k">${isPrimary ? 'Mode 1 &middot; Fundamental' : `Mode ${i + 1}`}</div>
                <div class="v">${Ti} s</div>
                <div class="sub">${fHz} Hz &middot; &zeta;=${zi}</div>
            </div>`;
        });
        stats += '</div>';

        // === יצירת טבלת התוצאות + הצגת העומס המחושב ===
        let h=`<table class="modes-table"><tr><th>Mode</th><th>Freq</th><th>T</th><th>Action</th></tr>`;
        data.frequencies.forEach((w,i)=> {
            const freqHz = w / (2 * Math.PI);
            h+=`<tr>
                    <td>${i+1}</td>
                    <td>${freqHz.toFixed(3)} Hz</td>
                    <td style="color:var(--accent)">${(2*Math.PI/w).toFixed(3)}s</td>
                    <td><button class="action-btn" style="font-size:0.7rem; padding:1px 4px; height:auto; min-height:0;" onclick="setFreqFromMode(${freqHz}, ${w})">Set</button></td>
                </tr>`;
        });

        // 1. הצגת מטריצת המסה (שעכשיו היא בטונות/ק"ג)
        // נקבל את המסה בק"ג מהשרת, נמיר לטונות לתצוגה נוחה
        h+=`<span class="mat-label">Mass Matrix [M] (ton):</span>`;
        data.M_matrix.forEach(r=>h+=`<div class="mat-row">[ ${r.map(n=>(n/1000).toFixed(2)).join(", ")} ]</div>`);

        // 2. חישוב והצגת העומס האקוויולנטי (q)
        // q = (M * g) / Area
        // נניח רוחב בניין 12 מטר (2 מפתחים של 6) ועומק 6 מטר -> שטח 72 מ"ר
        const area = 12.0 * 6.0;
        const g = 9.807;

        // הקוד החדש (הסרנו את style="color:...", הצבע הכחול יילקח מה-CSS הראשי)
        h+=`<span class="mat-label" style="margin-top:10px;">Calculated Load (q = Mg/A) [kN/m²]:</span>`;
        // לוקחים את האלכסון של מטריצת המסה
        const masses = data.M_matrix.map((r, i) => r[i]);
        // חישוב עומס (q = Mg/A) והמרה ל-kN
        const loads = masses.map(m => (m * g / area) / 1000.0);

        // השורה הזו תהיה עכשיו כחולה אוטומטית בגלל הקלאס .mat-row
        h+=`<div class="mat-row">[ ${loads.map(l => l.toFixed(2)).join(", ")} ]</div>`;

        h+=`<span class="mat-label">Stiffness [K] (kN/m):</span>`;
        data.K_matrix.forEach(r=>h+=`<div class="mat-row">[ ${r.map(n=>(n/1000).toLocaleString('en-US', {maximumFractionDigits:0})).join(", ")} ]</div>`);

        const resArea = document.getElementById("results-area");
        if(resArea) resArea.innerHTML = stats + h;

        resultsDirty = false;

    } catch(e){ console.error(e); }
}

// --- 10. VISUALIZER DRAWING ---
function drawFrame(disps) {
    const c = document.getElementById("vizCanvas");
    if(!c) return;
    const ctx = c.getContext("2d");
    const r = c.parentElement.getBoundingClientRect();
    c.width = r.width;
    c.height = r.height;

    const pal = getCanvasPalette();
    const w = c.width, h = c.height, f = disps.length;
    const dMax = Math.max(maxAbsDisp, 0.001);
    const sX = (w * 0.3) / dMax;
    const fH = (h * 0.8) / f;

    // Background
    ctx.fillStyle = pal.bg;
    ctx.fillRect(0, 0, w, h);

    // Blueprint grid
    ctx.lineWidth = 0.5;
    ctx.strokeStyle = pal.grid;
    ctx.beginPath();
    const gridStep = 40;
    for (let gx = 0; gx < w; gx += gridStep) { ctx.moveTo(gx, 0); ctx.lineTo(gx, h); }
    for (let gy_line = 0; gy_line < h; gy_line += gridStep) { ctx.moveTo(0, gy_line); ctx.lineTo(w, gy_line); }
    ctx.stroke();

    ctx.lineCap = "round";

    const cx = w / 2, gy = h - 20;
    const groundWidth = w * 0.7;
    const buildWidth  = Math.min(w * 0.32, 260);

    // Ground baseline
    ctx.lineWidth = 2;
    ctx.strokeStyle = pal.grid;
    ctx.beginPath();
    ctx.moveTo(cx - groundWidth/2, gy);
    ctx.lineTo(cx + groundWidth/2, gy);
    ctx.stroke();

    for (let i = 0; i < f; i++) {
        const yB = gy - i * fH, yT = gy - (i + 1) * fH;
        const xB = (i === 0) ? 0 : disps[i - 1] * sX;
        const xTop = disps[i] * sX;
        const halfW = buildWidth/2;

        ctx.lineWidth = 3;
        ctx.strokeStyle = pal.accent;
        ctx.beginPath(); ctx.moveTo(cx - halfW + xB, yB); ctx.lineTo(cx - halfW + xTop, yT); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(cx + halfW + xB, yB); ctx.lineTo(cx + halfW + xTop, yT); ctx.stroke();

        ctx.strokeStyle = pal.text;
        ctx.beginPath(); ctx.moveTo(cx - halfW + xTop, yT); ctx.lineTo(cx + halfW + xTop, yT); ctx.stroke();

        ctx.fillStyle = pal.danger;
        ctx.beginPath(); ctx.arc(cx + xTop, yT, 6, 0, 6.28); ctx.fill();

        ctx.fillStyle = pal.text;
        ctx.font = "bold 14px 'IBM Plex Mono', Consolas";
        ctx.textAlign = "center";
        ctx.fillText(`M${i+1}`, cx + xTop, yT - 15);
    }
}

// --- 11. SCROLL HANDLER ---
window.onTimeScroll = function() {
    const slider = document.getElementById('time-slider');
    if(!slider) return;
    const val = parseFloat(slider.value);
    const max = parseFloat(slider.max);

    if (val >= max - 0.5) {
        isAutoScroll = true;
    } else {
        isAutoScroll = false;
    }

    activeCharts.forEach(obj => {
        const chart = obj.chart;
        const T = obj.period;
        const normVal = val / T;
        const win = 20;

        if (normVal > win) {
            chart.options.scales.x.min = normVal - win;
            chart.options.scales.x.max = normVal;
        } else {
            chart.options.scales.x.min = 0;
            chart.options.scales.x.max = win;
        }
        chart.update('none');
    });
};

// --- 12. HELPERS & TOOLTIPS ---

let currentFontSize = 14;
function changeFontSize(delta) {
    currentFontSize = Math.min(22, Math.max(10, currentFontSize + delta));
    document.documentElement.style.fontSize = currentFontSize + 'px';
}
function resetFontSize() {
    currentFontSize = 14;
    document.documentElement.style.fontSize = '14px';
}

function toggleTheme() {
    const el = document.documentElement;
    const attr = el.getAttribute('data-theme');
    const isDark = attr === 'dark'
        || (attr === null && !window.matchMedia('(prefers-color-scheme: light)').matches);
    const next = isDark ? 'light' : 'dark';
    el.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);

    // Update all live Chart.js instances
    const pal = getCanvasPalette();
    activeCharts.forEach(obj => {
        const ch = obj.chart;
        ch.data.datasets[0].borderColor     = pal.accent;
        ch.data.datasets[0].backgroundColor = pal.accentFill;
        ch.data.datasets[1].borderColor     = pal.success;
        ch.data.datasets[2].borderColor     = pal.gold;
        ch.options.scales.x.grid.color      = pal.grid;
        ch.options.scales.x.title.color     = pal.textMuted;
        ch.options.scales.y.grid.color      = pal.grid;
        ch.options.scales.y.ticks.color     = pal.textMuted;
        ch.update('none');
    });

    // Redraw building canvas with new palette
    const dofs = parseInt(document.getElementById('dof-select').value) || 2;
    drawFrame(lastState.all_x || new Array(dofs).fill(0));
}

function toggleFullScreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
    } else {
        document.exitFullscreen().catch(() => {});
    }
}


window.setFreqFromMode = function(freqHz, rawOmega) {
    const numInput = document.getElementById('num-F');
    const rangeInput = document.getElementById('slide-F');
    if(!numInput || !rangeInput) return;

    exactFreqFromSet = rawOmega;
    numInput.value = freqHz.toFixed(4);
    rangeInput.value = freqHz;
    const valW = document.getElementById('val-w');
    if(valW) valW.innerText = `(ω=${rawOmega.toFixed(4)})`;
}

const tooltipsData = {
    "stories": { title: "Stories (DOF)", text: "• SDOF (1): Single equation.\n• MDOF (2-3): Multiple coupled equations." },
    "E": { title: "Young's Modulus (E)", text: "• Material stiffness (Stress/Strain).\n• Higher E = Stiffer building." },
    "mass": { title: "Floor Mass (M)", text: "• Direct mass per floor [ton].\n• Each floor is configured independently." },
    "damping": { title: "Damping (ζ)", text: "• Energy loss coefficient.\n• 0.02 is standard for concrete." },
    "freq": { title: "Forcing Freq (ω)", text: "• External oscillation rate.\n• Matching natural freq = Resonance!" },
    "geometry": { title: "Story Height (Hc)", text: "• Column clear height per floor [m].\n• Directly controls lateral story stiffness: K ∝ EI/H³.\n• Taller stories → lower stiffness → lower natural frequencies." }
};
function invalidateResults() {
    resultsDirty = true;
    const resArea = document.getElementById("results-area");
    if (!resArea) return;

    // 1. בדיקה אם ההודעה כבר קיימת (כדי לא להוסיף אותה 100 פעמים)
    if (document.getElementById("dirty-msg")) return;

    // 2. הוספת אפקט שקיפות לתוכן הישן (כדי לסמן שהוא לא מעודכן)
    // אנחנו עוטפים את התוכן הקיים ב-span או פשוט משנים את הצבע של הטקסט הקיים
    const existingContent = Array.from(resArea.children);
    existingContent.forEach(child => {
        child.style.opacity = "0.5"; // מעמעם את התוצאות הישנות
        child.style.filter = "grayscale(1)"; // הופך לאפור
    });

    // 3. יצירת אלמנט ההודעה החדש
    const msgDiv = document.createElement("div");
    msgDiv.id = "dirty-msg"; // מזהה ייחודי
    msgDiv.style.marginTop = "15px";
    msgDiv.style.padding = "10px";
    msgDiv.style.textAlign = "center";
    msgDiv.style.color = "var(--gold)";
    msgDiv.style.border = "1px dashed var(--gold)";
    msgDiv.style.borderRadius = "4px";
    msgDiv.style.backgroundColor = "rgba(201, 162, 39, 0.08)";
    msgDiv.innerHTML = `
        ⚠ <b>Parameters changed</b><br>
        Results above are outdated.<br>
        Press <b style="color:var(--accent)">CALCULATE MATRICES</b> to update.
    `;

    // 4. הוספה לסוף הרשימה
    resArea.appendChild(msgDiv);

    // גלילה למטה כדי שיראו את ההודעה
    resArea.scrollTop = resArea.scrollHeight;
}
window.showTooltip = function(key, event) {
    closeAllTooltips();
    event.stopPropagation();
    const div = document.createElement('div');
    div.className = 'info-tooltip';
    const content = tooltipsData[key] || { title: "Info", text: "..." };
    div.innerHTML = `<div class="tooltip-header"><span>${content.title}</span><button class="tooltip-close" onclick="closeAllTooltips()">✕</button></div><div class="tooltip-content">${content.text}</div>`;

    const btnRect = event.target.getBoundingClientRect();
    let top = window.scrollY + btnRect.top;
    let left = window.scrollX + btnRect.left + 20;
    if (top > window.innerHeight - 150) top -= 120;

    div.style.top = top + 'px';
    div.style.left = left + 'px';
    document.body.appendChild(div);
}

window.closeAllTooltips = function() {
    document.querySelectorAll('.info-tooltip').forEach(el => el.remove());
}
document.addEventListener('click', (e) => {
    if (!e.target.closest('.info-tooltip') && !e.target.classList.contains('info-btn')) window.closeAllTooltips();
});