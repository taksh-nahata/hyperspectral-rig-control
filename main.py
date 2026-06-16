from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
import time
import threading

# ----------------- HARDWARE IMPORTS & MOCKING -----------------
try:
    from pypylon import pylon
    HAS_BASLER = True
except ImportError:
    HAS_BASLER = False

try:
    import vmbpy
    HAS_ALLIED = True
except ImportError:
    HAS_ALLIED = False

try:
    import canopen
    HAS_CAN = True
except ImportError:
    HAS_CAN = False

app = FastAPI()

# ----------------- GLOBAL HARDWARE STATE -----------------
slider_network = None
slider_node = None
MOTOR_ID = None

# ----------------- HARDWARE CONTROL FUNCTIONS -----------------

def init_slider_network():
    """Scans the CAN bus, auto-detects the motor, and boots it up."""
    global slider_network, slider_node, MOTOR_ID
    
    if not HAS_CAN:
        return True 
        
    if slider_node is not None:
        return True 

    print("[HARDWARE] Scanning CAN network for Nanotec motor...")
    try:
        slider_network = canopen.Network()
        slider_network.connect(bustype='pcan', channel='PCAN_USBBUS1', bitrate=1000000)
        
        slider_network.scanner.search()
        time.sleep(1) 
        
        if not slider_network.scanner.nodes:
            print("[ERROR] No CAN nodes found. Check wiring.")
            return False
            
        MOTOR_ID = slider_network.scanner.nodes[0]
        print(f"[SUCCESS] Motor locked in at Node ID: {MOTOR_ID}")
        
        slider_node = slider_network.add_node(MOTOR_ID)
        slider_node.nmt.state = 'OPERATIONAL'
        
        print("[System] Running motor safety boot sequence...")
        slider_node.sdo[0x6040].raw = 0x06 
        time.sleep(0.1)
        slider_node.sdo[0x6040].raw = 0x07 
        time.sleep(0.1)
        slider_node.sdo[0x6040].raw = 0x0F 
        print("[SUCCESS] Motor bridge enabled and ready for commands.")
        return True
        
    except Exception as e:
        print(f"Slider Init Error: {e}")
        return False

def control_nanotec_slider(speed: int):
    """Sends velocity commands to the auto-detected motor."""
    if not HAS_CAN:
        print(f"[MOCK] Slider: Target velocity set to {speed}...")
        return

    if not init_slider_network():
        print("[ERROR] Cannot move. Slider network failed to initialize.")
        return

    try:
        slider_node.sdo[0x6060].raw = 3
        slider_node.sdo[0x60FF].raw = speed
        print(f"[HARDWARE] Slider velocity driven to {speed}.")
    except Exception as e:
        print(f"CAN Motor Error: {e}")

def trigger_pika_l():
    """Controls the Basler-based VNIR camera"""
    if not HAS_BASLER:
        print("[MOCK] Pika L: Capturing dummy VNIR data...")
        time.sleep(2)
        return
        
    try:
        camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        camera.Open()
        camera.Width.SetValue(900)
        camera.Height.SetValue(600)
        camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        print("[HARDWARE] Pika L VNIR recording...")
    except Exception as e:
        print(f"Pika L Error: {e}")

def trigger_pika_ir():
    """Controls the Allied Vision-based SWIR camera"""
    if not HAS_ALLIED:
        print("[MOCK] Pika IR: Capturing dummy SWIR data...")
        time.sleep(2)
        return
        
    try:
        with vmbpy.VmbSystem.get_instance() as vmb:
            cameras = vmb.get_all_cameras()
            if not cameras:
                print("No Pika IR found.")
                return
            with cameras[0] as cam:
                cam.Width.set(320)
                cam.Height.set(168)
                print("[HARDWARE] Pika IR SWIR recording...")
    except Exception as e:
        print(f"Pika IR Error: {e}")

def run_synced_scan():
    """Fires all hardware concurrently"""
    print("--- INITIATING SYNCED SCAN ---")
    
    init_slider_network()
    
    t_l = threading.Thread(target=trigger_pika_l)
    t_ir = threading.Thread(target=trigger_pika_ir)
    
    t_l.start()
    t_ir.start()
    
    control_nanotec_slider(speed=15)
    
    t_l.join()
    t_ir.join()
    
    control_nanotec_slider(speed=0)
    print("--- SCAN COMPLETE ---")

# ----------------- API ENDPOINTS -----------------

@app.get("/api/slider/move")
def move_slider(speed: int = 10):
    control_nanotec_slider(speed)
    return {"status": "success", "message": f"Slider moving at {speed} units/sec"}

@app.get("/api/slider/stop")
def stop_slider():
    control_nanotec_slider(0)
    return {"status": "success", "message": "Slider halted."}

@app.get("/api/camera/capture")
def start_capture(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_synced_scan)
    return {"status": "success", "message": "Scan sequence initiated. Cameras are recording."}

# ----------------- VISUAL USER INTERFACE -----------------

@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    # Notice the 'r' before the quotes. This forces Python to treat the UI code cleanly.
    html_content = r"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Hyperspectral Rig Control</title>
        <style>
            :root {
                color-scheme: dark;
                --bg: #07111f;
                --panel: rgba(12, 22, 39, 0.88);
                --panel-border: rgba(148, 163, 184, 0.14);
                --text: #e5eefb;
                --muted: #8fa3bf;
                --accent: #49d6ff;
                --accent-strong: #1ea7ff;
                --good: #20c997;
                --shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
            }

            * { box-sizing: border-box; }

            body {
                margin: 0;
                min-height: 100vh;
                color: var(--text);
                font-family: "Trebuchet MS", "Segoe UI", sans-serif;
                background: linear-gradient(135deg, #05101d 0%, #07111f 42%, #0c172a 100%);
            }

            .shell {
                width: min(1200px, calc(100% - 32px));
                margin: 0 auto;
                padding: 32px 0 40px;
            }

            .hero {
                display: grid;
                grid-template-columns: 1.5fr 0.9fr;
                gap: 20px;
                margin-bottom: 20px;
            }

            .hero-card, .panel, .log {
                background: var(--panel);
                border: 1px solid var(--panel-border);
                border-radius: 24px;
                box-shadow: var(--shadow);
                padding: 28px;
            }

            h1 {
                margin: 0 0 16px;
                font-size: clamp(2rem, 4vw, 3.75rem);
                letter-spacing: -0.04em;
            }

            .status-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 12px;
            }

            .stat {
                padding: 18px;
                border-radius: 18px;
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.06);
            }

            .stat-label {
                display: block;
                color: var(--muted);
                font-size: 0.84rem;
                margin-bottom: 10px;
                text-transform: uppercase;
                letter-spacing: 0.08em;
            }

            .stat-value {
                display: block;
                font-size: 1.15rem;
                font-weight: 700;
            }

            .content {
                display: grid;
                grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr);
                gap: 20px;
            }

            .section {
                padding: 18px;
                border-radius: 18px;
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.06);
                margin-bottom: 14px;
            }

            .section h3 { margin: 0 0 14px; font-size: 1.03rem; }

            .button-row {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 12px;
            }

            button {
                width: 100%;
                min-height: 52px;
                padding: 14px 16px;
                border: 0;
                border-radius: 16px;
                color: white;
                font: inherit;
                font-weight: 700;
                cursor: pointer;
                transition: transform 160ms ease;
            }

            button:hover { transform: translateY(-1px); }
            button:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }

            .btn-start { background: linear-gradient(135deg, #12d38a, #089e67); }
            .btn-action { background: linear-gradient(135deg, #1ea7ff, #3068ff); }
            .btn-stop { background: linear-gradient(135deg, #ff6b7a, #cc2f57); }

            #status-box {
                min-height: 280px;
                padding: 18px;
                border-radius: 18px;
                background: rgba(3, 11, 20, 0.82);
                border: 1px solid rgba(73, 214, 255, 0.18);
                color: #c7f0ff;
                font-family: monospace;
                white-space: pre-wrap;
            }

            @media (max-width: 920px) {
                .hero, .content { grid-template-columns: 1fr; }
                .status-grid { grid-template-columns: 1fr; }
            }
        </style>
    </head>
    <body>
        <div class="shell">
            <div class="hero">
                <section class="hero-card">
                    <h1>Hyperspectral Rig Core</h1>
                    <p style="color: var(--muted)">Run synced captures, move the slider rail, and monitor command feedback.</p>
                </section>
                <section class="hero-card">
                    <div class="status-grid">
                        <div class="stat"><span class="stat-label">Scan Mode</span><span class="stat-value">Synced</span></div>
                        <div class="stat"><span class="stat-label">Motion</span><span class="stat-value">Auto-Discovery</span></div>
                        <div class="stat"><span class="stat-label">Safety</span><span class="stat-value">Active</span></div>
                    </div>
                </section>
            </div>

            <div class="content">
                <section class="panel">
                    <div class="section">
                        <h3>System Operations</h3>
                        <div class="button-row">
                            <button class="btn-start" data-url="/api/camera/capture" data-label="Start synced scan">Start Synced Scan</button>
                            <button class="btn-action" data-url="/api/slider/move?speed=15" data-label="Move slider forward">Move Slider Forward</button>
                        </div>
                    </div>
                    <div class="section">
                        <h3>Manual Override</h3>
                        <div class="button-row">
                            <button class="btn-action" data-url="/api/slider/move?speed=8" data-label="Creep forward">Creep Forward</button>
                            <button class="btn-stop" data-url="/api/slider/stop" data-label="Emergency stop">Emergency Stop</button>
                        </div>
                    </div>
                </section>

                <aside class="log">
                    <h3>Live Output</h3>
                    <div id="status-box">System ready. Awaiting commands...</div>
                </aside>
            </div>
        </div>

        <script>
            function updateStatus(text) {
                const box = document.getElementById('status-box');
                box.innerText = text + "\n\n" + box.innerText;
            }

            async function runCommand(button) {
                const url = button.dataset.url;
                const label = button.dataset.label;
                const allButtons = document.querySelectorAll('button');
                
                allButtons.forEach(btn => btn.disabled = true);
                updateStatus("> Sending command: " + label + "...");
                
                try {
                    const response = await fetch(url);
                    const data = await response.json();
                    
                    const now = new Date();
                    const timeString = now.getHours().toString().padStart(2, '0') + ':' + 
                                     now.getMinutes().toString().padStart(2, '0') + ':' + 
                                     now.getSeconds().toString().padStart(2, '0');
                                     
                    updateStatus("[" + timeString + "] " + data.status.toUpperCase() + " - " + data.message);
                } catch (error) {
                    updateStatus("[ERROR] Connection failed. Check backend.");
                } finally {
                    allButtons.forEach(btn => btn.disabled = false);
                }
            }

            document.querySelectorAll('button[data-url]').forEach(btn => {
                btn.addEventListener('click', () => runCommand(btn));
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)