#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""妖怪おみくじ: TikTok用のスライド4枚と縦長動画(MP4)を作る。

使い方:
    python3 tools/make_tiktok.py spec.json

spec.json の例:
{
  "art": "art/nekomata.png",
  "out": "out/2026-11-12",
  "date_label": "11月12日（木）",
  "name": "猫又",
  "kana": "ねこまた",
  "hook": "長く生きた猫は、\n妖怪になる。",
  "lore": "年を経た猫の尾が二つに分かれ、化けるようになったもの。",
  "omen": "積み重ねてきたものが力になる日。",
  "act": "古い写真を見返す",
  "focus_y": 0.42,
  "audio": true
}

出力(out フォルダ): slide1.jpg〜slide4.jpg, tiktok.mp4
文字は TikTok の画面部品(上のタブ、右のボタン、下の説明文)に重ならない範囲に置く。
"""
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
LEFT, RIGHT = 90, 930          # 文字を置く左右の範囲(右はTikTokのボタンを避ける)
TEXT_BOTTOM = 1500             # 文字の下端(下は説明文に隠れる)
PAPER = (236, 230, 211)
GOLD = (232, 194, 106)
VERMILION = (207, 61, 48)
FONT_DIRS = ["/usr/share/fonts/opentype/noto", "/usr/share/fonts/truetype/noto",
             "/usr/share/fonts/noto-cjk", "/System/Library/Fonts"]
FONT_FILES = {
    "black": ["NotoSerifCJK-Black.ttc", "NotoSerifCJK-Bold.ttc", "NotoSerifCJKjp-Black.otf"],
    "bold": ["NotoSerifCJK-Bold.ttc", "NotoSerifCJK-SemiBold.ttc", "NotoSerifCJKjp-Bold.otf"],
    "semi": ["NotoSerifCJK-SemiBold.ttc", "NotoSerifCJK-Bold.ttc", "NotoSerifCJK-Medium.ttc"],
}
NO_LINE_START = set("、。，．・：；！？!?)）」』】〕》〉ー～…‥ゃゅょっぁぃぅぇぉャュョッァィゥェォ々")
NO_LINE_END = set("(（「『【〔《〈")


def font(weight, size):
    for d in FONT_DIRS:
        for f in FONT_FILES[weight]:
            p = os.path.join(d, f)
            if os.path.exists(p):
                return ImageFont.truetype(p, size, index=0)  # index 0 = 日本語の字形
    try:
        p = subprocess.run(["fc-match", "-f", "%{file}", "Noto Serif CJK JP:bold"],
                           capture_output=True, text=True, timeout=10).stdout.strip()
        if p and os.path.exists(p):
            return ImageFont.truetype(p, size, index=0)
    except Exception:
        pass
    sys.exit("日本語の明朝体フォント(Noto Serif CJK)が見つかりません。")


def text_w(fnt, s, spacing=0):
    if not s:
        return 0
    return fnt.getlength(s) + spacing * (len(s) - 1)


def wrap(text, fnt, max_w, spacing=0):
    """日本語の折り返し。明示的な改行を尊重し、行頭・行末の禁則を守る。"""
    lines = []
    for para in str(text).split("\n"):
        cur = ""
        for ch in para:
            if text_w(fnt, cur + ch, spacing) <= max_w:
                cur += ch
                continue
            if ch in NO_LINE_START and cur:
                cur += ch              # 句読点などは前の行にぶら下げる
                continue
            carry = ""
            while cur and cur[-1] in NO_LINE_END:
                carry = cur[-1] + carry
                cur = cur[:-1]
            lines.append(cur)
            cur = carry + ch
        lines.append(cur)
    return [ln for ln in lines if ln != ""] or [""]


def cover(img, focus_y=0.42):
    """絵を 1080x1920 いっぱいに切り抜く。focus_y は上下どこを中心に残すか(0=上, 1=下)。"""
    img = img.convert("RGB")
    s = max(W / img.width, H / img.height)
    nw, nh = round(img.width * s), round(img.height * s)
    img = img.resize((nw, nh), Image.LANCZOS)
    x = (nw - W) // 2
    y = int(max(0, min(nh - H, nh * focus_y - H * focus_y)))
    return img.crop((x, y, x + W, y + H))


def gradient_layer(text_top=1000):
    """上と下を暗くして文字を読みやすくする層。下の暗がりは文字ブロックの上端に合わせる。"""
    start = max(480, text_top - 280)
    full = text_top + 40
    g = Image.new("L", (1, H), 0)
    px = g.load()
    for y in range(H):
        a = 0.0
        if y < 420:
            a = max(a, 0.55 * (1 - y / 420))
        if y > start:
            a = max(a, min(0.86, 0.86 * (y - start) / max(1, full - start)))
        px[0, y] = int(255 * a)
    alpha = g.resize((W, H))
    layer = Image.new("RGBA", (W, H), (4, 10, 16, 255))
    layer.putalpha(alpha)
    return layer


class Canvas:
    def __init__(self, text_top=1000):
        self.img = gradient_layer(text_top)
        self.shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.text = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def put(self, xy, s, fnt, fill, spacing=0):
        x, y = xy
        ds, dt = ImageDraw.Draw(self.shadow), ImageDraw.Draw(self.text)
        if spacing:
            for ch in s:
                ds.text((x, y + 4), ch, font=fnt, fill=(0, 0, 0, 230))
                dt.text((x, y), ch, font=fnt, fill=fill + (255,))
                x += fnt.getlength(ch) + spacing
        else:
            ds.text((x, y + 4), s, font=fnt, fill=(0, 0, 0, 230))
            dt.text((x, y), s, font=fnt, fill=fill + (255,))

    def bar(self, x, y, w, h, fill):
        ImageDraw.Draw(self.text).rectangle((x, y, x + w, y + h), fill=fill + (255,))

    def done(self):
        out = Image.alpha_composite(self.img, self.shadow.filter(ImageFilter.GaussianBlur(9)))
        return Image.alpha_composite(out, self.text)


def header(c, date_label):
    c.put((LEFT, 232), "今日の守護妖怪", font("bold", 42), GOLD, spacing=8)
    if date_label:
        c.put((LEFT, 296), date_label, font("semi", 34), PAPER, spacing=2)


def layout(items, bottom=TEXT_BOTTOM):
    """items: (種類, 文字列) を下端そろえで積む。種類は label / body / big / name / kana / gap / bar。
    戻り値は (行のリスト, ブロックの上端y)。"""
    styles = {
        "label": (font("bold", 44), GOLD, 1.55, 10),
        "body": (font("semi", 58), PAPER, 1.5, 1),
        "big": (font("black", 92), PAPER, 1.36, 2),
        "name": (font("black", 230), PAPER, 1.1, 6),
        "kana": (font("bold", 50), GOLD, 1.5, 14),
    }
    rows = []
    for kind, s in items:
        if kind == "gap":
            rows.append(("gap", int(s), None, None, 0))
            continue
        if kind == "bar":
            rows.append(("bar", 56, None, None, 0))
            continue
        fnt, fill, lh, sp = styles[kind]
        size = fnt.size
        if kind == "name":                       # 長い名前は入る大きさまで縮める
            while text_w(fnt, s, sp) > RIGHT - LEFT and size > 90:
                size -= 10
                fnt = font("black", size)
        for ln in wrap(s, fnt, RIGHT - LEFT, sp):
            rows.append((ln, int(size * lh), fnt, fill, sp))
    top = bottom - sum(r[1] for r in rows)
    return rows, top


def draw_rows(c, rows, top):
    y = top
    for s, hgt, fnt, fill, sp in rows:
        if s == "bar":
            c.bar(LEFT + 6, y + 22, 120, 8, VERMILION)
        elif s != "gap":
            _, t, _, b = fnt.getbbox("国")       # 字の実際の上下位置
            c.put((LEFT, y + (hgt - (b - t)) / 2 - t), s, fnt, fill, sp)
        y += hgt


def slide(spec, items):
    rows, top = layout(items)
    c = Canvas(top)
    header(c, spec.get("date_label", ""))
    draw_rows(c, rows, top)
    return c.done()


def overlays(spec):
    name_items = ([("kana", spec["kana"])] if spec.get("kana") else []) + [("name", spec["name"]), ("bar", "")]
    return [
        slide(spec, [("big", spec["hook"])]),
        slide(spec, name_items),
        slide(spec, [("label", "伝承"), ("body", spec["lore"])]),
        slide(spec, [("label", "お告げ"), ("body", spec["omen"]), ("gap", 40),
                     ("label", "開運の所作"), ("body", spec["act"])]),
    ]


def make_video(bg_path, ov_paths, out_path, audio=True):
    durs = [3.0, 3.0, 4.5, 5.0]
    fade = 0.4
    total = sum(durs)
    n = int(total * 30)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-t", f"{total}", "-i", bg_path]
    for p in ov_paths:
        cmd += ["-loop", "1", "-framerate", "30", "-t", f"{total}", "-i", p]
    if audio:
        cmd += ["-f", "lavfi", "-t", f"{total}", "-i", "anoisesrc=color=brown:amplitude=0.9:seed=11:sample_rate=44100"]
    f = [f"[0:v]scale={W*2}:{H*2}:flags=lanczos,zoompan=z='1+0.07*on/{n}':x='iw/2-(iw/zoom/2)':y='ih*0.42-(ih/zoom*0.42)':d=1:s={W}x{H}:fps=30[bg0]"]
    t = 0.0
    last = "bg0"
    for i, d in enumerate(durs, start=1):
        a, b = t, t + d
        fx = f"[{i}:v]format=rgba,fade=t=in:st={a:.2f}:d={fade}:alpha=1"
        if i < len(durs):
            fx += f",fade=t=out:st={b - fade:.2f}:d={fade}:alpha=1"
        f.append(fx + f"[o{i}]")
        f.append(f"[{last}][o{i}]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})'[v{i}]")
        last = f"v{i}"
        t = b
    f.append(f"[{last}]format=yuv420p[vout]")
    maps = ["-map", "[vout]"]
    if audio:
        ai = len(ov_paths) + 1
        f.append(f"[{ai}:a]highpass=f=90,lowpass=f=420,tremolo=f=0.12:d=0.55,volume=0.5,"
                 f"afade=t=in:st=0:d=1.2,afade=t=out:st={total - 1.5:.2f}:d=1.5[aout]")
        maps += ["-map", "[aout]", "-c:a", "aac", "-b:a", "128k"]
    cmd += ["-filter_complex", ";".join(f)] + maps + [
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "30",
        "-t", f"{total}", "-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    for k in ("art", "out", "name", "hook", "lore", "omen", "act"):
        if not spec.get(k):
            sys.exit(f"spec に {k} がありません。")
    os.makedirs(spec["out"], exist_ok=True)
    bg = cover(Image.open(spec["art"]), float(spec.get("focus_y", 0.42)))
    bg_path = os.path.join(spec["out"], "_bg.jpg")
    bg.save(bg_path, quality=95)
    ov_paths = []
    for i, ov in enumerate(overlays(spec), start=1):
        p = os.path.join(spec["out"], f"_ov{i}.png")
        ov.save(p)
        ov_paths.append(p)
        Image.alpha_composite(bg.convert("RGBA"), ov).convert("RGB").save(
            os.path.join(spec["out"], f"slide{i}.jpg"), quality=90)
    make_video(bg_path, ov_paths, os.path.join(spec["out"], "tiktok.mp4"), bool(spec.get("audio", True)))
    for p in [bg_path] + ov_paths:
        os.remove(p)
    print("ok:", spec["out"])


if __name__ == "__main__":
    main()
