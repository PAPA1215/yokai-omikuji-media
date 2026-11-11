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
  "lore": "{年|とし}を{経|へ}た猫の尾が二つに分かれ、\n化けるようになった妖怪。",
  "omen": "積み重ねてきたものが\n力になる日。",
  "act": "古い写真を見返す",
  "focus_y": 0.42,
  "audio": true
}

- ふりがなは {漢字|よみ} と書く(hook / lore / omen / act で使える)。
- 改行は \n。1行は全角14字以内がめやす(入らなければ自動で折り返す)。
- 妖怪の名前は tools/fonts の筆文字系フォントで描く(字がなければ明朝体に戻す)。

出力(out フォルダ): slide1.jpg〜slide4.jpg, tiktok.mp4
文字は TikTok の画面部品(上のタブ、右のボタン、下の説明文)に重ならない範囲に置く。
"""
import json
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
LEFT, RIGHT = 90, 930          # 文字を置く左右の範囲(右はTikTokのボタンを避ける)
TEXT_BOTTOM = 1500             # 文字の下端(下は説明文に隠れる)
PAPER = (236, 230, 211)
GOLD = (232, 194, 106)
VERMILION = (207, 61, 48)
HERE = os.path.dirname(os.path.abspath(__file__))
NAME_FONT = os.path.join(HERE, "fonts", "ReggaeOne-Regular.ttf")
FONT_DIRS = ["/usr/share/fonts/opentype/noto", "/usr/share/fonts/truetype/noto",
             "/usr/share/fonts/noto-cjk", "/System/Library/Fonts"]
FONT_FILES = {
    "black": ["NotoSerifCJK-Black.ttc", "NotoSerifCJK-Bold.ttc", "NotoSerifCJKjp-Black.otf"],
    "bold": ["NotoSerifCJK-Bold.ttc", "NotoSerifCJK-SemiBold.ttc", "NotoSerifCJKjp-Bold.otf"],
    "semi": ["NotoSerifCJK-SemiBold.ttc", "NotoSerifCJK-Bold.ttc", "NotoSerifCJK-Medium.ttc"],
}
NO_LINE_START = set("、。，．・：；！？!?)）」』】〕》〉ー～…‥ゃゅょっぁぃぅぇぉャュョッァィゥェォ々")
NO_LINE_END = set("(（「『【〔《〈")
RUBY_RE = re.compile(r"\{([^|{}]+)\|([^|{}]+)\}")


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


def has_glyphs(fnt, s):
    """フォントに字がそろっているか(ない字は豆腐の形になるので、それと比べる)。"""
    try:
        tofu = bytes(fnt.getmask("\U0010FFFF"))
        return all(bytes(fnt.getmask(ch)) != tofu for ch in s if not ch.isspace())
    except Exception:
        return False


def name_font(size, s, path=None):
    p = path or NAME_FONT
    if os.path.exists(p):
        f = ImageFont.truetype(p, size)
        if has_glyphs(f, s):
            return f
    return font("black", size)


def tokens(text):
    """文字列を ("c", 字) と ("r", 親文字, よみ) の並びにする。改行ごとに分ける。"""
    paras = []
    for para in str(text).split("\n"):
        out, pos = [], 0
        for m in RUBY_RE.finditer(para):
            out += [("c", ch) for ch in para[pos:m.start()]]
            out.append(("r", m.group(1), m.group(2)))
            pos = m.end()
        out += [("c", ch) for ch in para[pos:]]
        paras.append(out)
    return paras


def tok_w(tok, fnt, rfnt, sp):
    if tok[0] == "c":
        return fnt.getlength(tok[1]) + sp
    base = sum(fnt.getlength(ch) + sp for ch in tok[1])
    # ふりがなが親文字より長いときは、前後の字の上に半字分まではみ出してよい
    return max(base, rfnt.getlength(tok[2]) + 6 - fnt.size * 0.5)


def wrap(text, fnt, rfnt, max_w, sp=0):
    """日本語の折り返し。明示的な改行を尊重し、行頭・行末の禁則を守る。ふりがなの組は割らない。"""
    lines = []
    for para in tokens(text):
        cur, cur_w = [], 0.0
        for tok in para:
            w = tok_w(tok, fnt, rfnt, sp)
            if cur_w + w <= max_w or not cur:
                cur.append(tok); cur_w += w
                continue
            if tok[0] == "c" and tok[1] in NO_LINE_START:
                cur.append(tok); cur_w += w     # 句読点などは前の行にぶら下げる
                continue
            carry = []
            while cur and cur[-1][0] == "c" and cur[-1][1] in NO_LINE_END:
                carry.insert(0, cur.pop())
            lines.append(cur)
            cur = carry + [tok]
            cur_w = sum(tok_w(t, fnt, rfnt, sp) for t in cur)
        if cur:
            lines.append(cur)
    return lines or [[]]


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
        for ch in s:
            ds.text((x, y + 4), ch, font=fnt, fill=(0, 0, 0, 230))
            dt.text((x, y), ch, font=fnt, fill=fill + (255,))
            x += fnt.getlength(ch) + spacing
        return x

    def bar(self, x, y, w, h, fill):
        ImageDraw.Draw(self.text).rectangle((x, y, x + w, y + h), fill=fill + (255,))

    def done(self):
        out = Image.alpha_composite(self.img, self.shadow.filter(ImageFilter.GaussianBlur(9)))
        return Image.alpha_composite(out, self.text)


def header(c, date_label):
    c.put((LEFT, 232), "今日の守護妖怪", font("bold", 42), GOLD, spacing=8)
    if date_label:
        c.put((LEFT, 296), date_label, font("semi", 34), PAPER, spacing=2)


def layout(items, spec, bottom=TEXT_BOTTOM):
    """items: (種類, 文字列) を下端そろえで積む。種類は label / body / big / name / kana / gap / bar。
    戻り値は (行のリスト, ブロックの上端y)。行は dict。"""
    styles = {
        "label": (font("bold", 44), GOLD, 1.55, 10),
        "body": (font("semi", 58), PAPER, 1.78, 1),     # ふりがなの分、行間を広めに
        "big": (font("black", 92), PAPER, 1.5, 2),
        "kana": (font("bold", 50), GOLD, 1.5, 14),
    }
    rows = []
    for kind, s in items:
        if kind in ("gap", "bar"):
            rows.append({"kind": kind, "h": int(s) if kind == "gap" else 60})
            continue
        if kind == "name":
            size, sp = 240, 8
            fnt = name_font(size, s, spec.get("name_font"))
            while sum(fnt.getlength(ch) + sp for ch in s) > RIGHT - LEFT and size > 90:
                size -= 10
                fnt = name_font(size, s, spec.get("name_font"))
            rows.append({"kind": kind, "h": int(size * 1.16), "toks": [("c", ch) for ch in s],
                         "fnt": fnt, "rfnt": None, "fill": PAPER, "sp": sp, "ruby": False})
            continue
        fnt, fill, lh, sp = styles[kind]
        ruby_ok = kind in ("body", "big")
        rfnt = font("bold", round(fnt.size * 0.5)) if ruby_ok else None
        for ln in wrap(s, fnt, rfnt or fnt, RIGHT - LEFT, sp):
            rows.append({"kind": kind, "h": int(fnt.size * lh), "toks": ln, "fnt": fnt,
                         "rfnt": rfnt, "fill": fill, "sp": sp, "ruby": ruby_ok})
    top = bottom - sum(r["h"] for r in rows)
    return rows, top


def draw_rows(c, rows, top):
    y = top
    for r in rows:
        if r["kind"] == "bar":
            c.bar(LEFT + 6, y + 24, 120, 8, VERMILION)
        elif r["kind"] != "gap":
            fnt, sp = r["fnt"], r["sp"]
            _, t, _, b = fnt.getbbox("国")           # 字の実際の上下位置
            body_h = b - t
            if r["ruby"]:                            # 字は行の下寄せ、上にふりがなの余白
                gy = y + r["h"] - body_h - round(fnt.size * 0.14)
            else:
                gy = y + (r["h"] - body_h) / 2
            x = LEFT
            for tok in r["toks"]:
                if tok[0] == "c":
                    x = c.put((x, gy - t), tok[1], fnt, r["fill"], sp)
                    continue
                rf = r["rfnt"]
                w = tok_w(tok, fnt, rf, sp)
                base_w = sum(fnt.getlength(ch) + sp for ch in tok[1])
                c.put((x + (w - base_w) / 2, gy - t), tok[1], fnt, r["fill"], sp)
                _, rt, _, rb = rf.getbbox("あ")
                rw = rf.getlength(tok[2])
                c.put((x + (w - rw) / 2, gy - (rb - rt) - 8 - rt), tok[2], rf, GOLD, 0)
                x += w
        y += r["h"]


def slide(spec, items):
    rows, top = layout(items, spec)
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
    if spec.get("video", True):
        make_video(bg_path, ov_paths, os.path.join(spec["out"], "tiktok.mp4"), bool(spec.get("audio", True)))
    for p in [bg_path] + ov_paths:
        os.remove(p)
    print("ok:", spec["out"])


if __name__ == "__main__":
    main()
