<p align="center">
  <img src="handset/web/logo.svg" width="120" alt="Pane logo - iPhone screen mirroring for Windows">
</p>

<h1 align="center">Pane — Mirror and Control Your iPhone from a Windows PC</h1>

<p align="center">
  <b>Free, open-source iPhone screen mirroring and remote control for Windows 10 &amp; 11.</b><br>
  See your iPhone screen live on your PC, tap and swipe with the mouse, and type with your computer keyboard —<br>
  over a USB cable <i>or</i> wirelessly over Wi-Fi. No jailbreak, no Mac, no subscription.
</p>

<p align="center">
  <a href="../../releases/latest"><b>⬇ Download Pane.exe for Windows</b></a>
  ·
  <a href="#features">Features</a>
  ·
  <a href="#quick-start">Quick start</a>
  ·
  <a href="#faq">FAQ</a>
</p>

---

**Pane** is like [scrcpy](https://github.com/Genymobile/scrcpy), but for **iPhone on Windows**. It streams the iPhone display to your desktop in real time and sends your mouse clicks, swipes and key presses back to the phone, so you can use iOS apps, reply to messages, play games, record demos or present your phone screen from your laptop or PC.

It is an alternative to paid tools such as ApowerMirror, LonelyScreen, Reflector, AirServer, iMyFone MirrorTo and Phone Link for iPhone — but free, private (everything stays on your own computer and network), and with full touch control instead of view-only AirPlay.

## Features

- 📱 **Live iPhone screen mirroring on Windows**: low-latency HEVC (H.265) video decoded in hardware.
- 🖱️ **Control the iPhone with your mouse**: tap, long-press, drag and swipe directly on the mirrored screen.
- ⌨️ **Type on your iPhone with the PC keyboard**: real keystrokes, including Ctrl+C / Ctrl+V / Ctrl+A / Ctrl+Z mapped to ⌘ shortcuts.
- 📶 **Wireless mirroring over Wi-Fi**: pair once over USB, then go cable-free on the same network.
- 🔌 **USB cable mode**: the most stable, lowest-latency connection.
- 🏠 **Hardware buttons & gestures**: Home, App Switcher, Lock/Power, Siri, Volume up/down, Mute, Notification Center, Control Center, back/forward swipes.
- 🖥️ **Realistic iPhone frame** with fit-to-window, zoom, rotate and **full-screen touch mode**.
- 🔁 **One-click restart** if the stream ever freezes.
- 🪟 **Single portable `Pane.exe`**: no Python, no installer, no account.
- 🔒 **Private by design**: no cloud, no telemetry; it only talks to your iPhone.

## Quick start

1. **Download** `Pane.exe` from the [latest release](../../releases/latest).
2. Install Apple's USB driver by installing **[Apple Devices](https://apps.microsoft.com/detail/9np83lwlpz9k)** (or iTunes) from the Microsoft Store.
3. Plug the iPhone into the PC, unlock it and tap **Trust This Computer**.
4. Turn on **Developer Mode** on the iPhone: *Settings → Privacy & Security → Developer Mode → On* (the iPhone restarts).
   If you don't see the option, connect to Pane once and it will appear.
5. Run **Pane.exe** and click **Start mirroring**.

### Go wireless (Wi-Fi)

1. While the iPhone is connected by cable, switch Pane to **Wi-Fi** and click **Set up Wi-Fi** (one-time pairing).
2. Unplug the cable. Keep the PC and iPhone on the **same Wi-Fi network** and the iPhone unlocked.
3. Click **Start mirroring**.

> Tip: if the iPhone isn't found over Wi-Fi, set the Windows network profile to **Private** and make sure the router doesn't isolate wireless clients.

## Controls

| Action on PC | Result on iPhone |
| --- | --- |
| Left click / drag | Tap / swipe |
| Swipe up from the bottom edge | Go Home (pause before releasing for the App Switcher) |
| Right click | Home |
| Keyboard | Types into the focused text field |
| Ctrl + C / V / X / A / Z | Copy / Paste / Cut / Select all / Undo |
| Side buttons on the frame | Lock, Volume up/down, Mute |

## Requirements

- Windows 10 or Windows 11 (64-bit)
- Google Chrome or Microsoft Edge (used as the app window)
- iPhone or iPad running **iOS / iPadOS 27 or newer** with Developer Mode enabled. This is the minimum for a picture. iOS 26 and older can connect, but Apple does not send video frames, so the screen stays black.
- Apple Devices app or iTunes (for the USB driver)

## Run from source

```powershell
git clone https://github.com/teyboxv1/pane-iphone-mirror-windows.git
cd pane-iphone-mirror-windows
pip install -r requirements.txt
python -m handset.server      # then open http://127.0.0.1:8765
```

### Build the Windows EXE

```powershell
pip install pyinstaller pillow
powershell -ExecutionPolicy Bypass -File packaging\build.ps1   # -> dist\Pane.exe
```

## How it works

Pane uses [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) to open a secure RemoteXPC / RSD tunnel to the iPhone (over USB, or over Wi-Fi via Bonjour remote pairing), starts the iOS screen-capture service on **iOS 27 or newer**, and streams the HEVC video to a local web UI that decodes it with WebCodecs. Touches, buttons and keystrokes are sent back as HID events. Everything runs locally on `127.0.0.1`.

```
iPhone ──USB / Wi-Fi tunnel──▶ Pane server (Python) ──localhost──▶ App window (WebCodecs + HID input)
```

## FAQ

**Can I mirror my iPhone to Windows for free?**
Yes. Pane is free and open source (GPL-3.0).

**Can I control my iPhone from my PC, not just view it?**
Yes. Unlike AirPlay receivers, Pane sends real touch, button and keyboard input to the iPhone.

**Does it work without a cable?**
Yes. After a one-time USB pairing, Pane mirrors and controls the iPhone over Wi-Fi on the same network.

**Do I need to jailbreak my iPhone?**
No. Pane uses Apple's built-in developer services. You only need Developer Mode turned on.

**Do I need a Mac or Xcode?**
No. Everything runs on Windows.

**Why does it need Developer Mode?**
iOS only exposes screen streaming and input injection through its developer services, which require Developer Mode. You can turn it off again at any time.

**Why is the screen black on iOS 26 or older?**
The minimum for live video is **iOS 27**. On older versions Pane may still connect and send touch or keyboard input, but the phone does not send picture frames. That is an iOS limitation. Update the iPhone to iOS 27 or newer for a picture.

**Windows SmartScreen warns about Pane.exe — is it safe?**
The executable isn't code-signed yet, so Windows shows a warning for new downloads. Click *More info → Run anyway*, or build it yourself from source.

**Is my data sent anywhere?**
No. The video and input stay between your iPhone and your PC.

## Keywords

iPhone screen mirroring Windows · mirror iPhone to PC · control iPhone from PC · iPhone remote control Windows 11 · iOS screen mirror Windows · scrcpy for iPhone · scrcpy iOS alternative · iPhone to laptop screen share · use iPhone on computer · type on iPhone with PC keyboard · wireless iPhone mirroring Wi-Fi · USB iPhone mirror · free ApowerMirror alternative · open source iPhone mirroring · no jailbreak

## License

Pane is licensed under the [GNU General Public License v3.0](LICENSE).
Not affiliated with or endorsed by Apple Inc. iPhone, iOS and AirPlay are trademarks of Apple Inc.
