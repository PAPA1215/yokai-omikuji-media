#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""妖怪おみくじ: TikTok用のスライド4枚と縦長動画(MP4)を作る。

使い方:
    python3 tools/make_tiktok.py spec.json

spec.json の例:
{
  "art": "art/bakegitsune.png",
  "out": "out/2026-11-13",
  "date_label": "11月13日（金）",
  "name": "化け狐",
  "kana": "ばけぎつね",
  "hook": "年を重ねた狐は、\n人を化かす。",
  "lore": "長く生きた狐は尾が増え、\n人に化ける術を覚えるといいます。",
  "omen": "いつもと違う自分が吉。",
  "act": "油揚げを食べる"
}

絵と名前の画像(art と同じフォルダに置けば自動で見つける。spec に art2 / art3 / title_image で指定もできる):
- art/<名前>.png        主役の絵(必須)。縦長 9:16、文字なし
- art/<名前>_2.png      2枚目の絵(任意)。途中の場面で切り替える
- art/<名前>_3.png      3枚目の絵(任意)
- art/<名前>_title.png  妖怪名の筆文字(任意)。真っ黒な背景に文字だけ。なければ明朝体で名前を書く

書き方:
- ふりがなは {漢字|よみ} と書く(hook / lore / omen / act で使える)。大人でも読みにくい語だけに付ける。
- 改行は \n。1行は全角14字以内がめやす(長い行は字を少し小さくして収める)。
- "motion": false で霧と光の粒の動きを止める。"audio": false で音を消す。"video": false で動画を作らない。
- 音は tools/bgm.flac (BGM「月の笛」。tools/make_bgm.py で作ったオリジナル曲)を流す。
  bgm.flac がなければ、以前の風の音になる。
- 英語版は "lang": "en" を足す。見出しが英語になり、単語の途中で折り返さない。"kana" にローマ字の名前、
  "sub" に名前の下の一言(例: "the shapeshifting fox")を書ける。名前の筆文字は日本語のまま使う。

出力(out フォルダ): slide1.jpg〜slide4.jpg, tiktok.mp4
文字は TikTok の画面部品(上の検索窓・タブ、右のボタン、下の説明文・通知)に重ならない範囲に置く。
"""
import json
import math
import os
import random
import re
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
LEFT, RIGHT = 90, 900          # 文字を置く左右の範囲(右はTikTokのボタンを避ける)
TEXT_BOTTOM = 1440             # 文字の下端(下は説明文・通知に隠れる)
HEADER_Y = 284                 # 見出しの上端(上は検索窓・タブに隠れる)
PAPER = (236, 230, 211)
GOLD = (232, 194, 106)
VERMILION = (207, 61, 48)
DURS = [3.0, 3.0, 4.5, 5.0]    # 4場面の長さ(秒)
FPS = 30
HERE = os.path.dirname(os.path.abspath(__file__))
NAME_FONT = os.path.join(HERE, "fonts", "name.ttf")
BGM = os.path.join(HERE, "bgm.flac")         # BGM「月の笛」(2026-11-12 から使用)
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
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")


# ---------- 文字 ----------

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
            if tok[0] == "c" and tok[1] == " ":
                lines.append(cur); cur, cur_w = [], 0.0   # 行末の空白は捨てる
                continue
            spaces = [i for i, t in enumerate(cur) if t[0] == "c" and t[1] == " "]
            if tok[0] == "c" and tok[1].isascii() and spaces:     # 英単語の途中では切らず、直前の空白で折る
                i = spaces[-1]
                lines.append(cur[:i])
                cur = cur[i + 1:] + [tok]
                cur_w = sum(tok_w(t, fnt, rfnt, sp) for t in cur)
                continue
            carry = []
            while cur and cur[-1][0] == "c" and cur[-1][1] in NO_LINE_END:
                carry.insert(0, cur.pop())
            lines.append(cur)
            cur = carry + [tok]
            cur_w = sum(tok_w(t, fnt, rfnt, sp) for t in cur)
        if cur:
            lines.append(cur)
        # 折り返しで最後の行が1〜2字だけ残ったら、前の行から字を回して釣り合わせる
        if len(lines) >= 2 and len(para) > len(lines[-1]) and len(lines[-1]) <= 2:
            prev, last = lines[-2], lines[-1]
            while len(last) < 4 and len(prev) > 6:
                last.insert(0, prev.pop())
                if len(last) >= 4 and not (last[0][0] == "c" and last[0][1] in NO_LINE_START):
                    break
    return lines or [[]]


# ---------- 絵 ----------

def cover(img, focus_y=0.42):
    """絵を 1080x1920 いっぱいに切り抜く。focus_y は上下どこを中心に残すか(0=上, 1=下)。"""
    img = img.convert("RGB")
    s = max(W / img.width, H / img.height)
    nw, nh = round(img.width * s), round(img.height * s)
    img = img.resize((nw, nh), Image.LANCZOS)
    x = (nw - W) // 2
    y = int(max(0, min(nh - H, nh * focus_y - H * focus_y)))
    return img.crop((x, y, x + W, y + H))


def sibling(art_path, suffix):
    """art/kappa.png に対して art/kappa_2.png や art/kappa_title.png を探す。"""
    stem, _ = os.path.splitext(art_path)
    for ext in IMG_EXT:
        p = f"{stem}{suffix}{ext}"
        if os.path.exists(p):
            return p
    return None


def title_rgba(path):
    """黒地に描かれた文字の画像を、黒を透明にした画像にして、文字の範囲だけ切り出す。"""
    im = Image.open(path).convert("RGB")
    r, g, b = im.split()
    lum = Image.merge("RGB", (r, g, b)).convert("L")
    mx = Image.eval(lum, lambda v: 0 if v < 26 else min(255, int((v - 26) * 255 / 150)))
    box = mx.point(lambda v: 255 if v > 60 else 0).getbbox()
    if not box:
        return None
    pad = 12
    box = (max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad))
    # 暗くなっている縁の色を持ち上げて、にごりを防ぐ
    bright = Image.eval(im, lambda v: min(255, int(v * 1.12) + 6))
    out = bright.convert("RGBA")
    out.putalpha(mx)
    return out.crop(box)


def gradient_layer(text_top=1000):
    """上と下を暗くして文字を読みやすくする層。下の暗がりは文字ブロックの上端に合わせる。"""
    start = max(440, text_top - 330)
    full = text_top - 10
    g = Image.new("L", (1, H), 0)
    px = g.load()
    for y in range(H):
        a = 0.0
        if y < 520:
            a = max(a, 0.6 * (1 - y / 520))
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

    def paste(self, im, xy):
        x, y = int(xy[0]), int(xy[1])
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sh.putalpha(im.getchannel("A").point(lambda v: int(v * 0.9)))
        self.shadow.alpha_composite(sh, (x, y + 6))
        self.text.alpha_composite(im, (x, y))

    def bar(self, x, y, w, h, fill):
        ImageDraw.Draw(self.text).rectangle((x, y, x + w, y + h), fill=fill + (255,))

    def done(self):
        out = Image.alpha_composite(self.img, self.shadow.filter(ImageFilter.GaussianBlur(9)))
        return Image.alpha_composite(out, self.text)


LABELS = {
    "ja": {"header": "今日の守護妖怪", "lore": "伝承", "omen": "お告げ", "act": "開運の所作"},
    "en": {"header": "YOKAI OF THE DAY", "lore": "LORE", "omen": "TODAY'S OMEN", "act": "LUCKY ACT"},
}


def labels(spec):
    return LABELS.get(spec.get("lang", "ja"), LABELS["ja"])


def header(c, spec):
    en = spec.get("lang") == "en"
    c.put((LEFT, HEADER_Y), labels(spec)["header"], font("bold", 40 if en else 42), GOLD, spacing=6 if en else 8)
    if spec.get("date_label"):
        c.put((LEFT, HEADER_Y + 64), spec["date_label"], font("semi", 34), PAPER, spacing=2)


def fit_size(items, kind, weight, sizes, sp):
    """その種類の文が、書いた改行どおりに収まる一番大きい字の大きさを返す。"""
    texts = [s for k, s in items if k == kind]
    for size in sizes:
        fnt, rfnt = font(weight, size), font("bold", round(size * 0.5))
        if all(len(wrap(s, fnt, rfnt, RIGHT - LEFT, sp)) == len(str(s).split("\n")) for s in texts):
            return size
    return sizes[-1]


def layout(items, spec, bottom=TEXT_BOTTOM):
    """items: (種類, 中身) を下端そろえで積む。種類は label / body / big / name / kana / gap / bar。
    戻り値は (行のリスト, ブロックの上端y)。行は dict。"""
    en = spec.get("lang") == "en"
    styles = {
        "label": (font("bold", 40 if en else 44), GOLD, 1.55, 6 if en else 10),
        # 日本語はふりがなの分、行間を広めに
        "body": (font("semi", fit_size(items, "body", "semi", (52, 48, 44) if en else (58, 54, 50), 1)),
                 PAPER, 1.5 if en else 1.78, 1),
        "big": (font("black", fit_size(items, "big", "black", (92, 84, 76, 68, 60), 2)), PAPER, 1.4 if en else 1.5, 2),
        "kana": (font("bold", 46 if en else 50), GOLD, 1.5, 10 if en else 14),
        "sub": (font("semi", 44), PAPER, 1.5, 2),
    }
    rows = []
    for kind, s in items:
        if kind in ("gap", "bar"):
            rows.append({"kind": kind, "h": int(s) if kind == "gap" else 60})
            continue
        if kind == "name":
            timg = title_rgba(spec["_title"]) if spec.get("_title") else None
            if timg is not None:                 # 筆文字の画像があれば、それを使う
                k = min((RIGHT - LEFT) / timg.width, 330 / timg.height)
                timg = timg.resize((max(1, round(timg.width * k)), max(1, round(timg.height * k))), Image.LANCZOS)
                rows.append({"kind": "image", "h": timg.height + 16, "img": timg})
                continue
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
        elif r["kind"] == "image":
            c.paste(r["img"], (LEFT - 8, y + 8))
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
    header(c, spec)
    draw_rows(c, rows, top)
    return c.done()


def overlays(spec):
    lb = labels(spec)
    name_items = ([("kana", spec["kana"])] if spec.get("kana") else []) + [("name", spec["name"])]
    if spec.get("sub"):
        name_items.append(("sub", spec["sub"]))
    name_items.append(("bar", ""))
    return [
        slide(spec, [("big", spec["hook"])]),
        slide(spec, name_items),
        slide(spec, [("label", lb["lore"]), ("body", spec["lore"])]),
        slide(spec, [("label", lb["omen"]), ("body", spec["omen"]), ("gap", 40),
                     ("label", lb["act"]), ("body", spec["act"])]),
    ]


# ---------- 動画 ----------

def scene_plan(n_arts):
    """4場面それぞれに、どの絵(0始まり)を使うか。"""
    return {1: [0, 0, 0, 0], 2: [0, 0, 1, 0], 3: [0, 0, 1, 2]}[min(3, n_arts)]


def segments(plan):
    """同じ絵が続く場面をまとめて (絵の番号, 開始秒, 長さ) にする。"""
    segs, t = [], 0.0
    for i, a in enumerate(plan):
        if segs and segs[-1][0] == a:
            segs[-1][2] += DURS[i]
        else:
            segs.append([a, t, DURS[i]])
        t += DURS[i]
    return segs


def write_light_layer(path, total, seed):
    """霧と光の粒が動く層(黒地)を、小さめの動画として書き出す。あとで絵に明るく重ねる。"""
    import numpy as np
    lw, lh = 540, 960
    n = int(total * FPS)
    rng = np.random.default_rng(seed)

    def noise(w, h, cell):
        a = rng.random((h // cell + 2, w // cell + 2)).astype(np.float32)
        im = Image.fromarray((a * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        return np.asarray(im).astype(np.float32) / 255

    tw = lw + int(0.9 * n) + 8
    far = np.clip((noise(tw, lh, 90) * 0.65 + noise(tw, lh, 34) * 0.35 - 0.42) * 2.2, 0, 1)
    near = np.clip((noise(tw, lh, 150) * 0.7 + noise(tw, lh, 50) * 0.3 - 0.45) * 2.4, 0, 1)
    yy = np.linspace(0, 1, lh, dtype=np.float32)[:, None]
    band_far = np.clip((yy - 0.25) / 0.5, 0, 1) * 0.22          # 霧は画面の下ほど濃く
    band_near = np.clip((yy - 0.42) / 0.45, 0, 1) * 0.30
    mist_col = np.array([190, 222, 226], np.float32)

    k = 19
    ax = np.arange(k, dtype=np.float32) - k // 2
    g = np.exp(-(ax[:, None] ** 2 + ax[None, :] ** 2) / (2 * 3.4 ** 2))
    blob = g / g.max()
    parts = []
    for i in range(38):
        warm = i % 2 == 0
        parts.append(dict(
            x=rng.uniform(20, lw - 20), y=rng.uniform(lh * 0.25, lh * 0.95), vy=rng.uniform(7, 20),
            amp=rng.uniform(5, 14), per=rng.uniform(3, 6), ph=rng.uniform(0, 6.28),
            t0=rng.uniform(-3, total - 2), life=rng.uniform(4, 8), size=rng.uniform(0.75, 1.5),
            col=np.array([255, 224, 150] if warm else [170, 232, 255], np.float32)))

    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{lw}x{lh}",
         "-r", str(FPS), "-i", "pipe:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
         "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)
    for f in range(n):
        t = f / FPS
        o1, o2 = int(0.35 * f), int(0.9 * f)
        m = far[:, o1:o1 + lw] * band_far + near[:, o2:o2 + lw] * band_near
        frame = m[..., None] * mist_col
        for p in parts:
            age = t - p["t0"]
            if age < 0 or age > p["life"]:
                continue
            fade = min(1.0, age / 1.2, (p["life"] - age) / 1.2)
            tw_ = 0.75 + 0.25 * math.sin(t * 2.2 + p["ph"])
            cx = int(p["x"] + p["amp"] * math.sin(2 * math.pi * age / p["per"] + p["ph"]))
            cy = int(p["y"] - p["vy"] * age)
            x0, y0 = cx - k // 2, cy - k // 2
            if x0 < 0 or y0 < 0 or x0 + k > lw or y0 + k > lh:
                continue
            frame[y0:y0 + k, x0:x0 + k] += blob[..., None] * p["col"] * (fade * tw_ * p["size"])
        proc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("光の層の書き出しに失敗")


def make_video(bg_paths, plan, ov_paths, out_path, audio=True, motion=True, seed=1, focus_y=0.42):
    total = sum(DURS)
    xf = 0.7                                   # 絵が切り替わるときの重なり(秒)
    segs = segments(plan)
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    f = []
    # 背景: 絵ごとに、ゆっくり寄る/引く動きをつけ、切り替わりはなめらかにつなぐ
    for i, (a, st, d) in enumerate(segs):
        dur = d + (xf if i < len(segs) - 1 else 0)
        nfr = int(math.ceil(dur * FPS))
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", bg_paths[a]]
        z = f"1+0.07*on/{nfr}" if i % 2 == 0 else f"1.08-0.07*on/{nfr}"
        f.append(f"[{i}:v]scale={W*2}:{H*2}:flags=lanczos,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':"
                 f"y='ih*{focus_y}-(ih/zoom*{focus_y})':d=1:s={W}x{H}:fps={FPS},format=yuv420p,setsar=1[s{i}]")
    last = "s0"
    for i in range(1, len(segs)):
        f.append(f"[{last}][s{i}]xfade=transition=fade:duration={xf}:offset={segs[i][1] - 0.0:.3f}[x{i}]")
        last = f"x{i}"
    idx = len(segs)
    if motion:
        light = out_path + ".light.mp4"
        write_light_layer(light, total, seed)
        cmd += ["-i", light]
        f.append(f"[{idx}:v]scale={W}:{H}:flags=bilinear,format=gbrp[lt]")
        f.append(f"[{last}]format=gbrp[bgp]")
        f.append("[bgp][lt]blend=all_mode=screen:shortest=1,format=yuv420p[lit]")
        last = "lit"
        idx += 1
    # 文字: 場面ごとにふわっと出して消す
    fade = 0.4
    t = 0.0
    for j, d in enumerate(DURS):
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{total}", "-i", ov_paths[j]]
        a, b = t, t + d
        fx = f"[{idx}:v]format=rgba,fade=t=in:st={a:.2f}:d={fade}:alpha=1"
        if j < len(DURS) - 1:
            fx += f",fade=t=out:st={b - fade:.2f}:d={fade}:alpha=1"
        f.append(fx + f"[o{j}]")
        f.append(f"[{last}][o{j}]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})'[v{j}]")
        last = f"v{j}"
        idx += 1
        t = b
    f.append(f"[{last}]format=yuv420p[vout]")
    maps = ["-map", "[vout]"]
    if audio and os.path.exists(BGM):
        # BGM: 動画の長さに合わせて切り(短ければくり返し)、最後はゆっくり消す
        cmd += ["-stream_loop", "-1", "-i", BGM]
        f.append(f"[{idx}:a]atrim=0:{total},asetpts=N/SR/TB,"
                 f"afade=t=out:st={total - 1.5:.2f}:d=1.5[aout]")
        maps += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
    elif audio:
        cmd += ["-f", "lavfi", "-t", f"{total}", "-i", "anoisesrc=color=brown:amplitude=0.9:seed=11:sample_rate=44100"]
        f.append(f"[{idx}:a]highpass=f=90,lowpass=f=420,tremolo=f=0.12:d=0.55,volume=0.5,"
                 f"afade=t=in:st=0:d=1.2,afade=t=out:st={total - 1.5:.2f}:d=1.5[aout]")
        maps += ["-map", "[aout]", "-c:a", "aac", "-b:a", "128k"]
    cmd += ["-filter_complex", ";".join(f)] + maps + [
        "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-r", str(FPS),
        "-t", f"{total}", "-movflags", "+faststart", out_path]
    try:
        subprocess.run(cmd, check=True)
    finally:
        if motion and os.path.exists(out_path + ".light.mp4"):
            os.remove(out_path + ".light.mp4")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    for k in ("art", "out", "name", "hook", "lore", "omen", "act"):
        if not spec.get(k):
            sys.exit(f"spec に {k} がありません。")
    os.makedirs(spec["out"], exist_ok=True)
    arts = [spec["art"]]
    for key, suf in (("art2", "_2"), ("art3", "_3")):
        p = spec.get(key) or sibling(spec["art"], suf)
        if p and os.path.exists(p):
            arts.append(p)
    spec["_title"] = spec.get("title_image") or sibling(spec["art"], "_title")
    fy = float(spec.get("focus_y", 0.42))
    bgs, bg_paths = [], []
    for i, p in enumerate(arts):
        bg = cover(Image.open(p), fy)
        bp = os.path.join(spec["out"], f"_bg{i}.jpg")
        bg.save(bp, quality=95)
        bgs.append(bg); bg_paths.append(bp)
    plan = scene_plan(len(arts))
    ov_paths = []
    for i, ov in enumerate(overlays(spec), start=1):
        p = os.path.join(spec["out"], f"_ov{i}.png")
        ov.save(p)
        ov_paths.append(p)
        Image.alpha_composite(bgs[plan[i - 1]].convert("RGBA"), ov).convert("RGB").save(
            os.path.join(spec["out"], f"slide{i}.jpg"), quality=90)
    if spec.get("video", True):
        seed = sum(ord(ch) for ch in str(spec.get("date_label", "")) + spec["name"])
        make_video(bg_paths, plan, ov_paths, os.path.join(spec["out"], "tiktok.mp4"),
                   audio=bool(spec.get("audio", True)), motion=bool(spec.get("motion", True)),
                   seed=seed, focus_y=fy)
    for p in bg_paths + ov_paths:
        os.remove(p)
    print("ok:", spec["out"], "| 絵", len(arts), "枚 | 名前の画像", "あり" if spec["_title"] else "なし")


if __name__ == "__main__":
    main()
