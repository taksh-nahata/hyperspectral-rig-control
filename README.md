# Hyperspectral Rig Control UI

A web-based control interface for synchronizing a Nanotec linear slider (via CANopen) with dual hyperspectral imagers (Basler Pika-L and Allied Vision Pika IR).

## Setup Instructions

1. Ensure the Nanotec slider and CAN-USB adapter are connected, and the cameras are powered on.
2. Clone or download this repository to the lab computer.
3. Install the required hardware and server libraries:
   ```bash
   pip install -r requirements.txt
4. Start the FastAPI server:
   ```bash
   uvicorn main:app --reload
5. Open a web browser on the control computer and navigate to:
[http://127.0.0.1:8000/dashboard](//127.0.0.1:8000/dashboard)
