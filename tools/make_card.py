#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""妖怪のお告げ: Xの投稿に付ける横長の画像(1600x900)を作る。

使い方:
    python3 tools/make_card.py spec.json

1. 夜の投稿の札 ("style": "night")。背景の絵を暗くして、中央に文字を置く。
{
  "style": "night",
  "bg": "bg/bg_kotoba.png",
  "out": "out/2026-11-13/night.jpg",
  "label": "妖怪のことば",
  "title": "狐につままれる",
  "lines": "わけが分からず、\nぼんやりしてしまうこと。"
}
引く妖怪みくじは "table" に 10 行を入れる(左5行・右5行の2列に並ぶ)。
  "table": [["0", "中吉", "河童"], ["1", "大吉", "天狗"], ...]

2. 雑学の絵 ("style": "emaki")。絵巻風の絵はそのまま見せ、題の札と朱の印だけを添える。
{
  "style": "emaki",
  "bg": "art/umibozu_emaki.png",
  "out": "out/2026-11-13/lore.jpg",
  "label": "雑学",
  "title": "海坊主と船乗り徳蔵"
}

共通:
- 英語は "lang": "en" を足す(札は横書きになる)。
- label / title / lines はどれも省ける。改行は \n。
- "brand" で右下の小さな名前を変えられる(既定は 妖怪のお告げ / Yokai Oracle)。false で消す。
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_tiktok import GOLD, PAPER, VERMILION, font  # noqa: E402

CW, CH = 1600, 900
SUMI = (38, 32, 28)
SLIP = (247, 240, 222)
ROTATE = set("ー〜～—―…‥（）()「」『』【】〔〕《》〈〉")   # 縦書きで横倒しにする字
SMALL_KANA = set("ゃゅょっぁぃぅぇぉャュョッァィゥェォ")
PUNCT = set("、。，．")


def cover(img, w=CW, h=CH, focus_y=0.5):
    img = img.convert("RGB")
    s = max(w / img.width, h / img.height)
    nw, nh = round(img.width * s), round(img.height * s)
    img = img.resize((nw, nh), Image.LANCZOS)
    x = (nw - w) // 2
    y = int(max(0, min(nh - h, (nh - h) * focus_y)))
    return img.crop((x, y, x + w, y + h))


def text_w(s, fnt, sp=0):
    return sum(fnt.getlength(ch) + sp for ch in s) - (sp if s else 0)


def fit(lines, weight, sizes, max_w, sp=0):
    """すべての行が max_w に収まる一番大きい字の大きさのフォントを返す。"""
    for size in sizes:
        fnt = font(weight, size)
        if all(text_w(ln, fnt, sp) <= max_w for ln in lines):
            return fnt
    return font(weight, sizes[-1])


class Layer:
    """文字と、その下に敷く影を別々に描いて重ねる。"""

    def __init__(self, base):
        self.base = base.convert("RGBA")
        self.shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
        self.text = Image.new("RGBA", base.size, (0, 0, 0, 0))

    def put(self, x, y, s, fnt, fill, sp=0, shadow=True):
        ds, dt = ImageDraw.Draw(self.shadow), ImageDraw.Draw(self.text)
        for ch in s:
            if shadow:
                ds.text((x, y + 4), ch, font=fnt, fill=(0, 0, 0, 235))
            dt.text((x, y), ch, font=fnt, fill=tuple(fill) + (255,))
            x += fnt.getlength(ch) + sp
        return x

    def center(self, y, s, fnt, fill, sp=0):
        self.put((CW - text_w(s, fnt, sp)) / 2, y, s, fnt, fill, sp)

    def done(self):
        out = Image.alpha_composite(self.base, self.shadow.filter(ImageFilter.GaussianBlur(8)))
        return Image.alpha_composite(out, self.text).convert("RGB")


# ---------- 夜の札 ----------

def night_card(spec):
    en = spec.get("lang") == "en"
    bg = cover(Image.open(spec["bg"]), focus_y=float(spec.get("focus_y", 0.5)))
    # 全体を少し落とし、中央をさらに暗くして文字を読みやすくする
    dark = Image.new("RGB", (CW, CH), (4, 10, 16))
    bg = Image.blend(bg, dark, 0.38)
    mask = Image.new("L", (CW, CH), 0)
    ImageDraw.Draw(mask).ellipse((CW * 0.08, CH * 0.06, CW * 0.92, CH * 0.94), fill=150)
    mask = mask.filter(ImageFilter.GaussianBlur(120))
    bg = Image.composite(dark, bg, mask)
    L = Layer(bg)

    label = spec.get("label", "")
    title_lines = [s for s in str(spec.get("title", "")).split("\n") if s]
    body_lines = [s for s in str(spec.get("lines", "")).split("\n") if s]
    table = spec.get("table") or []
    max_w = 1280

    f_label = font("bold", 38 if en else 42)
    sp_label = 6 if en else 12
    f_title = fit(title_lines, "black", (112, 100, 88, 76, 64, 54), max_w, 4) if title_lines else None
    f_body = fit(body_lines, "semi", (50, 46, 42, 38), max_w, 2) if body_lines else None
    f_num, f_luck, f_name = font("black", 44), font("bold", 44), font("semi", 44)
    row_h, col_w = 74, 520

    blocks = []                                   # (高さ, 描く関数)
    if label:
        blocks.append((int(f_label.size * 1.5) + 44, "label"))
    for ln in title_lines:
        blocks.append((int(f_title.size * 1.32), ("title", ln)))
    if title_lines and (body_lines or table):
        blocks.append((26, "gap"))
    for ln in body_lines:
        blocks.append((int(f_body.size * 1.62), ("body", ln)))
    if table:
        if body_lines or title_lines:
            blocks.append((30, "gap"))
        rows = (len(table) + 1) // 2
        blocks.append((rows * row_h, "table"))

    total = sum(h for h, _ in blocks)
    y = (CH - total) / 2 - 6
    for h, what in blocks:
        if what == "label":
            L.center(y, label, f_label, GOLD, sp_label)
            bx = CW / 2 - 40
            by = y + f_label.size * 1.5 + 14
            ImageDraw.Draw(L.text).rectangle((bx, by, bx + 80, by + 6), fill=VERMILION + (255,))
        elif what == "table":
            rows = (len(table) + 1) // 2
            x0 = CW / 2 - col_w
            for i, row in enumerate(table):
                cx = x0 + (i // rows) * col_w + 70
                cy = y + (i % rows) * row_h + 8
                num, luck, name = (list(row) + ["", "", ""])[:3]
                L.put(cx, cy, str(num), f_num, GOLD)
                L.put(cx + 70, cy, str(luck), f_luck, PAPER, 2)
                L.put(cx + 70 + 130, cy, str(name), f_name, PAPER, 2)
        elif what != "gap":
            kind, ln = what
            if kind == "title":
                L.center(y, ln, f_title, PAPER, 4)
            else:
                L.center(y, ln, f_body, PAPER, 2)
        y += h

    brand = spec.get("brand", "Yokai Oracle" if en else "妖怪のお告げ")
    if brand:
        f_b = font("bold", 28)
        L.put(CW - 60 - text_w(brand, f_b, 4), CH - 70, brand, f_b, GOLD, 4)
    return L.done()


# ---------- 雑学の絵(絵巻風) ----------

def vertical_text(img, cx, top, s, fnt, fill, pitch):
    """縦書き。字を1つずつ上から置く。長音や括弧は横倒しにする。戻り値は下端のy。"""
    y = top
    size = fnt.size
    for ch in s:
        tile = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(tile)
        l, t, r, b = d.textbbox((0, 0), ch, font=fnt)
        d.text((size - (l + r) / 2, size - (t + b) / 2), ch, font=fnt, fill=tuple(fill) + (255,))
        if ch in ROTATE:
            tile = tile.rotate(-90, resample=Image.BICUBIC)
        dx, dy = 0, 0
        if ch in PUNCT:
            dx, dy = size * 0.32, -size * 0.3
        elif ch in SMALL_KANA:
            dx, dy = size * 0.08, -size * 0.06
        img.alpha_composite(tile, (int(cx - size + dx), int(y + pitch / 2 - size + dy)))
        y += pitch
    return y


def seal(img, x, y, text, size, vertical=True):
    """朱の四角い印。白抜きの字を入れる。"""
    f = font("black", int(size * (0.40 if vertical and len(text) > 1 else 0.36)))
    d = ImageDraw.Draw(img)
    if vertical:
        w, h = size, size
    else:
        w, h = int(text_w(text, f, 4) + size * 0.5), int(size * 0.62)
    d.rounded_rectangle((x, y, x + w, y + h), radius=6, fill=VERMILION + (245,))
    if vertical:
        pitch = (h - size * 0.14) / max(1, len(text))
        vertical_text(img, x + w / 2, y + size * 0.07, text, f, SLIP, pitch)
    else:
        l, t, r, b = d.textbbox((0, 0), text, font=f)
        tx = x + (w - text_w(text, f, 4)) / 2
        for ch in text:
            d.text((tx, y + (h - (b - t)) / 2 - t), ch, font=f, fill=SLIP + (255,))
            tx += f.getlength(ch) + 4
    return w, h


def emaki_card(spec):
    en = spec.get("lang") == "en"
    img = cover(Image.open(spec["bg"]), focus_y=float(spec.get("focus_y", 0.5))).convert("RGBA")
    title = str(spec.get("title", "")).replace("\n", "")
    label = spec.get("label", "LORE" if en else "雑学")
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    if en:                                       # 横書きの札を左下に
        f = fit([title], "bold", (50, 46, 42, 38, 34), 1180, 1) if title else font("bold", 42)
        h = 96
        sw, sh = seal(over, 60, CH - 60 - h + (h - 60) / 2, label, 96, vertical=False) if label else (0, 0)
        if title:
            x0 = 60 + (sw + 18 if label else 0)
            w = int(text_w(title, f, 1) + 64)
            d.rounded_rectangle((x0, CH - 60 - h, x0 + w, CH - 60), radius=4, fill=SLIP + (238,), outline=SUMI + (255,), width=3)
            l, t, r, b = d.textbbox((0, 0), "Hg", font=f)
            tx = x0 + 32
            for ch in title:
                d.text((tx, CH - 60 - h + (h - (b - t)) / 2 - t), ch, font=f, fill=SUMI + (255,))
                tx += f.getlength(ch) + 1
    else:                                        # 縦書きの題箋を右上に
        n = max(1, len(title))
        size = 66
        while size > 40 and n * (size + 8) + 70 > CH - 60 - 60 - (120 if label else 0):
            size -= 2
        f = font("bold", size)
        pitch = size + 8
        sw_ = size + 62
        sh_ = n * pitch + 70
        x1 = CW - 70
        x0 = x1 - sw_
        y0 = 56
        if title:
            d.rectangle((x0 + 6, y0 + 8, x1 + 6, y0 + sh_ + 8), fill=(0, 0, 0, 70))      # 札の影
            d.rectangle((x0, y0, x1, y0 + sh_), fill=SLIP + (242,), outline=SUMI + (255,), width=3)
            d.rectangle((x0 + 9, y0 + 9, x1 - 9, y0 + sh_ - 9), outline=SUMI + (120,), width=1)
            vertical_text(over, (x0 + x1) / 2, y0 + 35, title, f, SUMI, pitch)
        if label:
            ssz = 92
            seal(over, (x0 + x1) / 2 - ssz / 2 if title else x1 - ssz, (y0 + sh_ + 20) if title else y0, label, ssz)
    out = Image.alpha_composite(img, over)
    brand = spec.get("brand", "Yokai Oracle" if en else "妖怪のお告げ")
    if brand:
        f_b = font("bold", 26)
        d2 = ImageDraw.Draw(out)
        bw = text_w(brand, f_b, 3)
        bx = CW - 60 - bw if en else 60
        x = bx
        for ch in brand:
            d2.text((x, CH - 58), ch, font=f_b, fill=SUMI + (170,))
            x += f_b.getlength(ch) + 3
    return out.convert("RGB")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    for k in ("bg", "out"):
        if not spec.get(k):
            sys.exit(f"spec に {k} がありません。")
    if not os.path.exists(spec["bg"]):
        sys.exit(f"背景の絵が見つかりません: {spec['bg']}")
    style = spec.get("style", "night")
    img = emaki_card(spec) if style == "emaki" else night_card(spec)
    os.makedirs(os.path.dirname(spec["out"]) or ".", exist_ok=True)
    img.save(spec["out"], quality=90)
    print("ok:", spec["out"], "|", style, "|", f"{os.path.getsize(spec['out']) // 1024}KB")


if __name__ == "__main__":
    main()
