# Code Review Study: setup for remote participants

Thank you for taking part. You will review six code changes made by AI coding agents:
three on your laptop and three in your Meta Quest headset.
Everything runs on your own laptop. Nothing is sent over the internet.

**Please don't open the source code or the files in `runtime/` before or during the
study.** Reading them can change how you review the trials and would affect the results.

You need:

- A laptop with Python 3.10 or newer (Windows, macOS or Linux)
- A Meta Quest (2, 3, 3S or Pro) on the **same Wi-Fi network** as the laptop
- Your participant ID from the researcher (for example `p03`)

## 1. Install (once, about 3 minutes)

Unzip the folder, open a terminal in it, and run:

**Windows (PowerShell)**

```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell refuses to run the activate script, run
`Set-ExecutionPolicy -Scope Process Bypass` first, then try again.

**macOS / Linux**

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Start the headset server (terminal 1)

In the same folder, with the virtual environment active:

```
python -m src.backend.main serve --https
```

It prints an address like `https://192.168.1.23:8000`. Leave this terminal open.
If your firewall asks, allow Python on **private** networks.

## 3. Start the laptop app (terminal 2)

Open a second terminal in the same folder, activate the virtual environment again
(step 1, second line), then run:

```
streamlit run src/frontend/app_2d.py
```

Your browser opens http://localhost:8501. Type your participant ID in the sidebar,
but **don't press Begin yet**.

## 4. Connect the headset

1. Put on the Quest and open the **Browser** app.
2. Type the address from step 2 (including `https://` and `:8000`).
3. It warns "Your connection is not private". Choose **Advanced**, then **Proceed**.
   This is expected: the certificate was made by your own laptop.
4. Enter the **same participant ID** and press **Start VR session**.

## 5. Do the study

Go back to the laptop app and press **Begin**. It tells you when to use the laptop and
when to put on the headset; both screens move on by themselves. In VR, press the big
blue **Enter VR** button.

VR controls: trigger = click. Hold grip = grab and move a panel (thumbstick pushes it
away or pulls it closer). Left thumbstick = walk. Right thumbstick = scroll the panel you
point at, or turn. **Reset layout** puts the panels back.

## 6. Send your results

When the laptop app says **All trials complete**, email the researcher this file:

```
runtime/decisions.jsonl
```

If anything went wrong in the headset, please also attach `runtime/xr_debug.jsonl`.
Then you can close both terminals (Ctrl+C) and delete the folder.

## If something doesn't work

- **The headset can't load the page.** The laptop and headset must be on the same Wi-Fi.
  Some networks (campus, office, hotel) block devices from seeing each other. Use a phone
  hotspot for both, then restart step 2 (the address changes).
- **The headset loads the page but there is no Enter VR button.** Make sure the address
  starts with `https://`, not `http://`.
- **USB instead of Wi-Fi** (needs developer mode and adb): run step 2 without `--https`,
  then `adb reverse tcp:8000 tcp:8000`, and open `http://localhost:8000` in the headset.
- **I made a mistake or closed something.** Just start the commands again with the same ID.
  Your finished trials are saved and the study continues where you left off.

Anything else: email the researcher, and include a screenshot of the terminal if you can.
