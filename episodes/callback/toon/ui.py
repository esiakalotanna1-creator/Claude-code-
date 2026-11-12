"""Phone screens drawn in screen space: the call screen, the missed-calls list and the message thread.
Each draws a phone held close to the camera, filling most of the frame, over whatever is behind it."""
import math

import skia

from toon import H, W, argb, lin, paint, typeface

TF, TFB = typeface(False), typeface(True)


def _text(c, s, x, y, size, colr, bold=False, center=True, a=1.0):
    f = skia.Font(TFB if bold else TF, size)
    w = f.measureText(s)
    c.drawString(s, x - (w / 2 if center else 0), y, f, paint(colr, a=a))
    return w


def phone_frame(fr, cx=W / 2, cy=H * 0.52, w=640, tilt=-4.0):
    """The device; returns (canvas, screen rect) with the canvas transformed so the screen is upright."""
    c = fr.c
    c.save()
    c.translate(cx, cy)
    c.rotate(tilt)
    h = w * 2.05
    body = skia.RRect.MakeRectXY(skia.Rect(-w / 2, -h / 2, w / 2, h / 2), w * 0.12, w * 0.12)
    c.drawRRect(body, paint("#000000", a=0.5, blur=30))
    c.drawRRect(body, paint("#15171d"))
    scr = skia.Rect(-w / 2 + 18, -h / 2 + 18, w / 2 - 18, h / 2 - 18)
    c.clipRRect(skia.RRect.MakeRectXY(scr, w * 0.1, w * 0.1), True)
    return c, scr


def call_screen(fr, name, sub, t=0.0, incoming=False, initial=None):
    c, s = phone_frame(fr)
    c.drawRect(s, paint(shader=lin((0, s.top()), (0, s.bottom()), [argb("#2b3a5c"), argb("#1a2238"), argb("#0e1322")], [0, 0.5, 1])))
    cx = s.centerX()
    r = 120 + 6 * math.sin(t * 3.0) if incoming else 120
    if incoming:
        for k in range(3):                                   # rings pulsing out of the avatar
            u = (t * 0.8 + k / 3) % 1.0
            c.drawCircle(cx, s.top() + 430, r + 160 * u, paint("#9fc4ff", a=0.35 * (1 - u), stroke=4))
    c.drawCircle(cx, s.top() + 430, r, paint("#c98b5a"))
    _text(c, initial or name[:1], cx, s.top() + 470, 120, "#fff6ea", bold=True)
    _text(c, name, cx, s.top() + 680, 84, "#ffffff", bold=True)
    _text(c, sub, cx, s.top() + 760, 40, "#c9d4ea")
    if incoming:
        for dx, col in ((-170, "#e5484d"), (170, "#30c46c")):
            c.drawCircle(cx + dx, s.bottom() - 220, 74, paint(col))
    else:
        c.drawCircle(cx, s.bottom() - 220, 74, paint("#e5484d"))
    c.restore()


def missed_calls(fr, n, number, time_s, scroll=0.0):
    c, s = phone_frame(fr)
    c.drawRect(s, paint("#f4f4f6"))
    _text(c, "Recents", s.left() + 50, s.top() + 150, 64, "#111111", bold=True, center=False)
    y = s.top() + 250 - scroll
    for i in range(n):
        if y > s.top() + 180:
            _text(c, number, s.left() + 50, y + 50, 42, "#d23b3b", bold=True, center=False)
            _text(c, "missed call", s.left() + 50, y + 92, 30, "#8a8a92", center=False)
            _text(c, time_s, s.right() - 200, y + 70, 32, "#8a8a92", center=False)
            c.drawLine(s.left() + 50, y + 120, s.right(), y + 120, paint("#dddde3", stroke=2))
        y += 130
    c.restore()


def thread(fr, title, msgs, typing=0.0, t=0.0):
    """msgs = [(text, mine)]; typing > 0 shows the other side's dots."""
    c, s = phone_frame(fr)
    c.drawRect(s, paint("#f4f4f6"))
    c.drawRect(skia.Rect(s.left(), s.top(), s.right(), s.top() + 200), paint("#e9e9ee"))
    _text(c, title, s.centerX(), s.top() + 150, 44, "#111111", bold=True)
    y = s.top() + 260
    f = skia.Font(TF, 38)
    for text, mine in msgs:
        words, lines, cur = text.split(), [], ""
        for wd in words:
            if f.measureText(cur + " " + wd) > s.width() * 0.62 and cur:
                lines.append(cur)
                cur = wd
            else:
                cur = (cur + " " + wd).strip()
        lines.append(cur)
        bw = max(f.measureText(L) for L in lines) + 60
        bh = 52 * len(lines) + 34
        x0 = s.right() - 40 - bw if mine else s.left() + 40
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0, y, x0 + bw, y + bh), 34, 34), paint("#2f7cf6" if mine else "#e1e1e6"))
        for i, L in enumerate(lines):
            _text(c, L, x0 + 30, y + 58 + 52 * i, 38, "#ffffff" if mine else "#111111", center=False)
        y += bh + 24
    if typing > 0:
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(s.left() + 40, y, s.left() + 200, y + 80), 34, 34), paint("#e1e1e6", a=typing))
        for k in range(3):
            a = 0.35 + 0.65 * max(0.0, math.sin(t * 6 - k * 0.8))
            c.drawCircle(s.left() + 85 + k * 35, y + 40, 11, paint("#8a8a92", a=a * typing))
    c.restore()


def lock_screen(fr, clock, date, notif=None, t=0.0, buzz=0.0):
    """Lock screen: big clock, the date, and optionally one notification card (sender, text) sliding in."""
    dx = 10 * math.sin(t * 60) * buzz
    c, s = phone_frame(fr, cx=W / 2 + dx)
    c.drawRect(s, paint(shader=lin((0, s.top()), (0, s.bottom()), [argb("#3a2f5c"), argb("#1c2240"), argb("#0d1124")], [0, 0.6, 1])))
    _text(c, date, s.centerX(), s.top() + 230, 40, "#dfe6ff")
    _text(c, clock, s.centerX(), s.top() + 420, 190, "#ffffff", bold=True)
    if notif:
        who, text, u = notif
        y = s.top() + 560 + 60 * (1 - u)
        card = skia.RRect.MakeRectXY(skia.Rect(s.left() + 30, y, s.right() - 30, y + 190), 40, 40)
        c.drawRRect(card, paint("#ffffff", a=0.88 * u))
        _text(c, who, s.left() + 80, y + 70, 40, "#111111", bold=True, center=False, a=u)
        _text(c, "now", s.right() - 140, y + 70, 30, "#6a6a72", center=False, a=u)
        _text(c, text, s.left() + 80, y + 140, 40, "#222222", center=False, a=u)
    c.restore()


def recording(fr, t, secs):
    """Voicemail greeting recorder: a red dot, a live waveform, the timer."""
    c, s = phone_frame(fr)
    c.drawRect(s, paint("#101318"))
    _text(c, "Voicemail greeting", s.centerX(), s.top() + 170, 44, "#ffffff", bold=True)
    _text(c, "recording  0:%02d" % int(secs), s.centerX(), s.top() + 240, 36, "#ff6b6b")
    for i in range(40):
        x = s.left() + 50 + i * (s.width() - 100) / 40
        a = 0.2 + 0.8 * abs(math.sin(t * 7 + i * 0.7) * math.sin(t * 2.3 + i * 0.31))
        c.drawRect(skia.Rect(x, s.centerY() - 180 * a, x + 9, s.centerY() + 180 * a), paint("#ff6b6b", a=0.85))
    c.drawCircle(s.centerX(), s.bottom() - 220, 74, paint("#ffffff"))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(s.centerX() - 30, s.bottom() - 250, s.centerX() + 30, s.bottom() - 190), 8, 8), paint("#e5484d"))
    c.restore()
