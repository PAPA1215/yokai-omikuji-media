#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""妖怪のお告げ: 「あなたの守護妖怪」の表の画像(1600x900 を2枚)を作る。

誕生月と守護妖怪の割り当ては data/shugo.json に決めてある(変えない)。
1枚目に1〜6月、2枚目に7〜12月が入る。

使い方(リポジトリの一番上のフォルダで実行する):
    python3 tools/make_shugo.py spec.json

1. 固定の表(性格の一言つき)
{"out": "out/shugo"}

2. 金曜の「週末のお告げ」(一言を週ごとに差し替える)
{
  "out": "out/2026-11-13",
  "title": "週末のお告げ",
  "sub": "11月14日・15日",
  "lines": {"1": "誘いには乗って吉", "2": "...", ... "12": "..."}
}
- lines は 1〜12 の月ごとの一言。全角16字以内がめやす(長いと字が小さくなる)。
- 出力は <out>/shugo_1.jpg と <out>/shugo_2.jpg。

3. 英語版の表("lang": "en"。月の名前・ローマ字の妖怪名・英語の説明と一言になる)
{"out": "out/shugo-en", "lang": "en"}
"""
import json
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_tiktok import GOLD, PAPER, VERMILION, font  # noqa: E402

CW, CH = 1600, 900
BG = (8, 16, 24)
CELL = (14, 26, 36)
EDGE = (60, 80, 90)
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ROOT = os.path.dirname(HERE)


def tw(s, f, sp=0):
    return sum(f.getlength(c) + sp for c in s) - (sp if s else 0)


def put(d, x, y, s, f, fill, sp=0):
    for c in s:
        d.text((x, y), c, font=f, fill=fill)
        x += f.getlength(c) + sp


def thumb(row, w, h):
    """顔のアップ(_2)があればそれを、なければ本体の絵を、横長に切り出す。"""
    path = None
    for suf in ("_2", ""):
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            q = os.path.join(ROOT, "art", f"{row['file']}{suf}{ext}")
            if os.path.exists(q):
                path = q
                break
        if path:
            break
    if not path:
        return Image.new("RGB", (w, h), CELL)
    im = Image.open(path).convert("RGB")
    s = w / im.width
    im = im.resize((w, max(h, round(im.height * s))), Image.LANCZOS)
    y = int((im.height - h) * float(row.get("focus", 0.17)))
    return im.crop((0, y, w, y + h))


def sheet(rows, out, title, sub, page, brand, en=False):
    img = Image.new("RGB", (CW, CH), BG)
    d = ImageDraw.Draw(img)
    f_t, f_s = font("black", 54), font("bold", 30)
    put(d, 60, 26, title, f_t, PAPER, 4)
    put(d, 60 + tw(title, f_t, 4) + 30, 46, sub, f_s, GOLD, 4)
    put(d, CW - 60 - tw(page, f_s, 4), 46, page, f_s, GOLD, 4)
    d.rectangle((60, 104, 180, 110), fill=VERMILION)
    top, gap = 132, 16
    cw = (CW - 120 - gap * 2) // 3
    chh = (CH - top - 40 - gap) // 2
    th = chh - 132
    f_m, f_n = font("black", 40), font("black", 46)
    for i, row in enumerate(rows):
        cx = 60 + (i % 3) * (cw + gap)
        cy = top + (i // 3) * (chh + gap)
        img.paste(thumb(row, cw, th), (cx, cy))
        d.rectangle((cx, cy + th, cx + cw, cy + chh), fill=CELL)
        d.rectangle((cx, cy, cx + cw, cy + chh), outline=EDGE, width=2)
        if en:                                   # 英語: 月・ローマ字の名前 / 短い説明 / 一言 の3段
            ms = MONTHS_EN[row["month"] - 1]
            fm = font("black", 34)
            put(d, cx + 22, cy + th + 10, ms, fm, GOLD, 1)
            nx = cx + 22 + tw(ms, fm, 1) + 16
            size = 42
            fn = font("black", size)
            while tw(row["name_en"], fn, 1) > cx + cw - 22 - nx and size > 26:
                size -= 2
                fn = font("black", size)
            put(d, nx, cy + th + 4 + (42 - size) * 0.6, row["name_en"], fn, PAPER, 1)
            put(d, cx + 22, cy + th + 60, row.get("gloss_en", ""), font("bold", 23), GOLD, 1)
            line = str(row.get("line", ""))
            size = 24
            fl = font("semi", size)
            while tw(line, fl, 0) > cw - 44 and size > 18:
                size -= 1
                fl = font("semi", size)
            put(d, cx + 22, cy + th + 90, line, fl, PAPER, 0)
            continue
        ms = f"{row['month']}月"
        put(d, cx + 22, cy + th + 14, ms, f_m, GOLD, 2)
        put(d, cx + 22 + tw(ms, f_m, 2) + 18, cy + th + 10, row["name"], f_n, PAPER, 3)
        line = str(row.get("line", ""))
        size = 30 if len(line) <= 14 else 27
        fl = font("semi", size)
        while tw(line, fl, 1) > cw - 44 and size > 20:
            size -= 1
            fl = font("semi", size)
        put(d, cx + 22, cy + th + 80, line, fl, PAPER, 1)
    if brand:
        f_b = font("bold", 24)
        put(d, CW - 60 - tw(brand, f_b, 4), CH - 34, brand, f_b, GOLD, 4)
    img.save(out, quality=90)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    if not spec.get("out"):
        sys.exit("spec に out がありません。")
    rows = json.load(open(os.path.join(ROOT, "data", "shugo.json"), encoding="utf-8"))
    en = spec.get("lang") == "en"
    if en:
        rows = [dict(r, line=r.get("line_en", "")) for r in rows]
    lines = spec.get("lines") or {}
    if lines:
        missing = [r["month"] for r in rows if not str(lines.get(str(r["month"]), "")).strip()]
        if missing:
            sys.exit(f"lines に {missing} 月の一言がありません。1〜12 をすべて書いてください。")
        rows = [dict(r, line=str(lines[str(r["month"])]).strip()) for r in rows]
    os.makedirs(spec["out"], exist_ok=True)
    title = spec.get("title", "Your guardian yokai" if en else "あなたの守護妖怪")
    sub = spec.get("sub", "by birth month" if en else "誕生月でわかります")
    brand = spec.get("brand", "Yokai Oracle" if en else "妖怪のお告げ")
    p1, p2 = os.path.join(spec["out"], "shugo_1.jpg"), os.path.join(spec["out"], "shugo_2.jpg")
    sheet(rows[:6], p1, title, sub, "January – June" if en else "1月〜6月", brand, en)
    sheet(rows[6:], p2, title, sub, "July – December" if en else "7月〜12月", brand, en)
    print("ok:", p1, p2)


if __name__ == "__main__":
    main()
