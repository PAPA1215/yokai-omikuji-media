#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""妖怪のお告げ: 夜の投稿(21:00)の TikTok 用の縦長動画を作る。

使い方(リポジトリの一番上のフォルダで実行する):
    python3 tools/make_night_tiktok.py out/2026-11-13/night_tiktok.json

設定ファイルの共通の項目:
    "type"        quiz / nitaku / kaidan / kotoba / shugo / sato / raishu (曜日の型)
    "out"         出力フォルダ(例 "out/2026-11-13")。動画は <out>/night.mp4 (昼の雑学は noon.mp4)
    "date_label"  見出しの下の日付(例 "11月13日（金）")

型ごとの項目(file は art/ の妖怪のファイル名。絵がなければ夜の背景だけで作る):
    quiz   月 妖怪クイズ    "file", "name", "kana"(任意), "hints": [ヒント3つ], "reveal": 答えの一言
    nitaku 火 究極の二択    "question", "a": {"file","name","line"}, "b": {"file","name","line"}
    kaidan 水 140字怪談     "title", "parts": [本文を2〜4つに分けたもの], "file"(任意)
    kotoba 木 妖怪のことば  "phrase", "kana"(任意), "meaning", "origin", "close"(任意), "file"(任意)
                            見出しは "meaning_label"(既定「意味」)、"origin_label"(既定「由来」)で変えられる
    shugo  金 週末のお告げ  "sub" (例 "11月14日・15日"), "lines": {"1": "...", ... "12": "..."}
                            1〜4月・5〜8月・9〜12月の3画面に分けた短い動画(約12秒。2026-11-18 から)。
                            1画面に4か月ぶん、顔の絵・月・妖怪の名前・一言を大きく並べる。見る人が止めて自分の月を探す。
                            一言は全角9字までなら1行、それより長いと読点や助詞のところで2行になる。
                            "screens": 2 で、1〜6月・7〜12月の2画面(約10秒。絵と字は少し小さい)にできる。
                            出だしの文は "hook"(大きい字)と "lead"(その下の一言)で変えられる。
                            "style": "pages" で、以前の1か月ずつ見せる長い動画(約34秒)に戻せる。
    sato   土 妖怪の里だより "title", "parts": [本文を2〜4つ], "file"(任意)
    raishu 日 来週の守護妖怪 "file", "name", "kana"(任意), "range" (例 "11月16日〜22日"), "lore", "omen"
    zatsugaku 昼の雑学(毎日) "file", "title", "parts": [本文を2〜3つ], "lead"(任意), "close"(任意)
                            art/<file>_emaki.png があれば、絵巻を右から左へたどる動画になる。出力は <out>/noon.mp4
                            題("title")は見る人への問いにし、答えを parts の最後に置く(2026-11-18 から)。

昼の雑学と週末のお告げは、最初のコマから文字を出す(ほかの型は 0.3 秒かけて出る)。

夜の絵: art/<file>_4.png と _5.png (朝の動画と違う画角・ポーズの夜の場面)があれば、
3〜4場面のうち2場面に優先して使う(朝と同じ絵ばかりにならないように)。なければ本体・_2・_3 で作る。
書き方は tools/make_tiktok.py と同じ(改行は \\n で自分で入れる。ふりがなは {漢字|よみ})。
1行は全角14字以内がめやす。長い行は字を少し小さくして収める。
確認用の画像を <out>/slide_night01.jpg … (昼は slide_noon01.jpg …) に書き出す(リポジトリには入らない)。
音は tools/bgm.flac (BGM「月の笛」)。
"""
import json
import math
import os
import subprocess
import sys

from PIL import Image, ImageEnhance, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_tiktok as mt  # noqa: E402

ROOT = os.path.dirname(HERE)
W, H, FPS = mt.W, mt.H, mt.FPS
# 型の名前、夜の背景、背景を縦に切り抜くときに残す横の位置(0=左, 1=右。鳥居や灯りのある側)
TYPES = {
    "quiz": ("妖怪クイズ", "bg_quiz", 0.92),
    "nitaku": ("究極の二択", "bg_nitaku", 0.93),
    "kaidan": ("140字怪談", "bg_kaidan", 0.90),
    "kotoba": ("妖怪のことば", "bg_kotoba", 0.96),
    "shugo": ("週末のお告げ", "bg_mikuji", 0.93),
    "sato": ("妖怪の里だより", "bg_sato", 0.92),
    "raishu": ("来週の守護妖怪", "bg_raishu", 0.86),
    "zatsugaku": ("妖怪雑学", "bg_kotoba", 0.96),   # 昼の雑学(出力は noon.mp4)
}
SHUGO = os.path.join(ROOT, "data", "shugo.json")
SHADE = (10, 0.42)                 # 正体を伏せる場面: 絵をぼかして暗くし、影だけ見せる


def path_in_root(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def art(stem, sufs=("",)):
    """art/<stem><suf>.png を探す。なければ None。"""
    if not stem:
        return None
    for suf in sufs:
        for ext in mt.IMG_EXT:
            p = os.path.join(ROOT, "art", f"{stem}{suf}{ext}")
            if os.path.exists(p):
                return p
    return None


def chars(s):
    return len(mt.RUBY_RE.sub(lambda m: m.group(1), str(s)).replace("\n", ""))


def read_time(*texts, base=2.2, per=7.5, lo=3.0, hi=8.0):
    """読み終えるまでの秒数(1秒に7〜8字がめやす)。"""
    n = sum(chars(t) for t in texts)
    return round(max(lo, min(hi, base + n / per)), 2)


class Night:
    def __init__(self, spec):
        self.spec = spec
        self.label, bg, self.bg_x = TYPES[spec["type"]]
        self.night_bg = os.path.join(ROOT, "bg", bg + ".png")
        self.scenes = []           # {"bg": Image, "ov": Image, "dur": 秒}
        self.pan = None            # 横長の絵巻を右から左へたどる動画にするときの絵
        self.out_name = "night"
        self.instant = False       # True なら、最初の場面の文字を最初のコマから出す

    # --- 背景 ---
    def bg(self, path=None, focus=0.42, shade=None):
        if path and os.path.exists(path):
            im = mt.cover(Image.open(path), focus)
        else:                      # 横長の夜の背景は、鳥居や灯りのある側を縦に切り抜く
            src = Image.open(self.night_bg).convert("RGB")
            k = max(W / src.width, H / src.height)
            src = src.resize((round(src.width * k), round(src.height * k)), Image.LANCZOS)
            x = int((src.width - W) * self.bg_x)
            im = src.crop((x, 0, x + W, H))
        if shade:                  # クイズのヒント: 絵を暗く、ぼかして影だけ見せる
            im = ImageEnhance.Brightness(im.filter(ImageFilter.GaussianBlur(shade[0]))).enhance(shade[1])
        return im

    # --- 文字 ---
    def overlay(self, items, title_img=None, top_text=None):
        spec = {"_title": title_img}
        rows, top = mt.layout(items, spec)
        c = mt.Canvas(top - (124 if top_text else 0))
        c.put((mt.LEFT, mt.HEADER_Y), self.label, mt.font("bold", 42), mt.GOLD, spacing=8)
        if self.spec.get("date_label"):
            c.put((mt.LEFT, mt.HEADER_Y + 64), self.spec["date_label"], mt.font("semi", 34), mt.PAPER, spacing=2)
        if top_text:
            c.put((mt.LEFT, top - 124), top_text, mt.font("black", 88), mt.GOLD, spacing=4)
        mt.draw_rows(c, rows, top)
        return c.done()

    def add(self, items, dur, bg_path=None, focus=0.42, shade=None, title_img=None, top_text=None):
        self.scenes.append({"bg": None if self.pan else self.bg(bg_path, focus, shade),
                            "ov": self.overlay(items, title_img, top_text), "dur": dur})

    def name_items(self, name, kana=None):
        return ([("kana", kana)] if kana else []) + [("name", name), ("bar", "")]


# ---------- 型ごとの組み立て ----------

def build_quiz(n, s):
    hints = s["hints"]
    f = s.get("file")
    a1, a2 = art(f, ("_4", "")), art(f, ("_5", "_2", ""))   # 夜の絵(_4・_5)があれば優先
    n.add([("big", "この妖怪は、\nだれ。"), ("gap", 30), ("body", f"ヒントは{len(hints)}つ。")], 3.0)
    kan = "一二三四五"
    for i, h in enumerate(hints):
        n.add([("label", f"ヒント{kan[i]}"), ("body", h)], read_time(h, base=2.4),
              bg_path=a1, shade=SHADE if a1 else None)
    n.add([("big", "答えは……")], 1.8, bg_path=a1, shade=(6, 0.5) if a1 else None)
    n.add(n.name_items(s["name"], s.get("kana")) + [("body", s["reveal"])], read_time(s["reveal"], base=3.0, lo=4.0),
          bg_path=a2 or a1, title_img=art(s.get("file"), ("_title",)))


def build_nitaku(n, s):
    a, b = s["a"], s["b"]
    n.add([("big", s["question"])], read_time(s["question"], base=2.4))
    for key, side in (("A", a), ("B", b)):
        n.add(n.name_items(side["name"], side.get("kana")) + [("body", side["line"])],
              read_time(side["line"], base=2.8, lo=3.6), bg_path=art(side.get("file"), ("_4", "_2", "")),
              title_img=art(side.get("file"), ("_title",)), top_text=key)
    n.add([("big", f"{a['name']}か、\n{b['name']}か。"), ("gap", 30),
           ("body", "あなたなら、どちらを選びますか。\nコメントで教えてください。")], 3.8)


def build_story(n, s, note, hide=False):
    """怪談・里だより: 題 → 本文を少しずつ。
    hide=True(怪談)は、最後の場面まで妖怪の絵を暗く沈めて見せ、最後に正体を見せる。"""
    f = s.get("file")
    if hide:                       # [伏せて見せる絵, …, 最後に正体を見せる絵]
        pics = [p for p in (art(f, ("_4", "_3", "")), art(f, ("_5", ""))) if p]
    else:
        pics = [p for p in (art(f, ("_4", "")), art(f, ("_5", "_2", "")), art(f, ("_3", ""))) if p]
    pics = list(dict.fromkeys(pics))
    n.add([("big", s["title"]), ("gap", 30), ("body", note)], 3.0)
    parts = s["parts"]
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        if not pics:
            n.add([("body", part)], read_time(part))
        elif hide:
            n.add([("body", part)], read_time(part, lo=3.4 if last else 3.0),
                  bg_path=pics[-1] if last else pics[0], shade=None if last else SHADE)
        else:
            n.add([("body", part)], read_time(part), bg_path=pics[i % len(pics)])


def build_kotoba(n, s):
    f = s.get("file")
    n4, n5 = art(f, ("_4",)), art(f, ("_5",))
    if n4 and n5:                  # 夜の絵があれば、4場面のうち2場面を夜の絵にする
        bgs = [n4, art(f, ("_2", "")), n5, art(f, ("_3", "_2", ""))]
    else:
        bgs = [art(f), art(f, ("_2", "")), art(f, ("_3", "_2", "")), art(f, ("_2", ""))]
    head = ([("kana", s["kana"])] if s.get("kana") else []) + [("big", s["phrase"]), ("bar", "")]
    n.add(head, 3.2, bg_path=bgs[0])
    n.add([("label", s.get("meaning_label", "意味")), ("body", s["meaning"])], read_time(s["meaning"]), bg_path=bgs[1])
    n.add([("label", s.get("origin_label", "由来")), ("body", s["origin"])], read_time(s["origin"]), bg_path=bgs[2])
    if s.get("close"):
        n.add([("body", s["close"])], read_time(s["close"], lo=3.4), bg_path=bgs[3])


def shugo_thumb(row, size):
    """守護妖怪の顔まわりを四角く切り出す(顔のアップ _2 があればそれを、なければ本体の絵を使う)。"""
    p = art(row["file"], ("_2", ""))
    if not p:
        return None
    im = Image.open(p).convert("RGB")
    side = round(im.width * 0.62)
    # 顔の高さは make_shugo.py の表の画像と同じ決め方("focus"。既定 0.17)
    cy = (im.height - im.width * 222 / 480) * float(row.get("focus", 0.17)) + im.width * 111 / 480
    x0 = (im.width - side) // 2
    y0 = int(max(0, min(im.height - side, cy - side / 2)))
    return im.crop((x0, y0, x0 + side, y0 + side)).resize((size, size), Image.LANCZOS)


def shugo_line(line, avail, sizes, wrap_size):
    """一言を大きい字で1行に収める。収まらなければ、読点(なければ助詞や言葉の切れ目)で2行に分ける。
    戻り値は (行のリスト, フォント)。"""
    def width(t, f):
        return sum(f.getlength(ch) + 1 for ch in t)
    for size in sizes:
        f = mt.font("semi", size)
        if width(line, f) <= avail:
            return [line], f

    def word_start(ch):                        # 漢字かカタカナ = 言葉の頭になりやすい字
        return "\u4e00" <= ch <= "\u9fff" or "\u30a1" <= ch <= "\u30fa"

    def fit(cuts, size):                       # その字の大きさで2行とも収まる、いちばん偏りの少ない切れ目
        f = mt.font("semi", size)
        ok = [i for i in cuts if max(width(line[:i], f), width(line[i:], f)) <= avail]
        return (min(ok, key=lambda i: max(i, len(line) - i)), f) if ok else None

    inner = [i for i in range(2, len(line) - 1) if line[i] not in mt.NO_LINE_START]
    comma = [i for i in range(1, len(line)) if line[i - 1] == "、"]
    groups = [                                 # 切れ目の候補。上のものほど自然
        [i for i in inner if line[i - 1] in "をへ" or line[i - 2:i] in ("から", "まで", "より")
         or (line[i - 1] in "にではが" and word_start(line[i]))],
        [i for i in inner if "\u3041" <= line[i - 1] <= "\u3096" and word_start(line[i])],
        [i for i in inner if line[i - 1] in "をにでへはがとも"],
        comma,
    ]
    found = None
    even = [i for i in comma if min(i, len(line) - i) >= 3]   # 「朝、」のように片方が短すぎる読点は後回し
    for size in range(wrap_size, wrap_size - 9, -2):       # 読点があれば、少し字を小さくしてでも読点で分ける
        found = found or fit(even, size)
    for size in range(wrap_size, 28, -2):
        for g in groups:
            found = found or fit(g, size)
    if not found:                              # どの候補でも収まらないときは、真ん中あたりで分けて字を小さくする
        cuts = [i for i in inner if line[i - 1] not in mt.NO_LINE_END] or [max(1, len(line) // 2)]
        cut = min(cuts, key=lambda i: max(i, len(line) - i))
        size = wrap_size
        while size > 30 and max(width(line[:cut], mt.font("semi", size)), width(line[cut:], mt.font("semi", size))) > avail:
            size -= 2
        found = (cut, mt.font("semi", size))
    cut, f = found
    return [line[:cut], line[cut:]], f


def shugo_list_overlay(s, rows, label):
    """週末のお告げ: 何か月ぶんかを1画面に並べた文字の層(顔の絵・月・妖怪の名前・一言)。
    1画面6か月(2画面の型)と、1画面4か月(3画面の型。絵も字もさらに大きい)に対応。
    label は見出しの横に出す「1〜6月」「7〜12月」など。"""
    top = mt.HEADER_Y
    list_top = top + 76
    row_h = (mt.TEXT_BOTTOM - list_top) // len(rows)       # 6行なら180、4行なら270
    big = len(rows) <= 4
    m_size, n_size = (66, 54) if big else (50, 42)
    sizes, wrap_size = ((60, 58, 56), 58) if big else ((48, 46, 44, 42), 46)
    gap_a, gap_b = (26, 16) if big else (22, 14)           # 名前と一言のあいだ、一言の行のあいだ
    c = mt.Canvas(top)
    veil = Image.new("L", (1, H), 0)           # 一覧のうしろを暗くして、字を読みやすくする
    px = veil.load()
    for y in range(H):
        a = 0.6 * (1 - y / 520) if y < 520 else 0.0
        a = max(a, min(0.84, 0.84 * (y - (top - 110)) / 90)) if y > top - 110 else a
        px[0, y] = int(255 * a)
    layer = Image.new("RGBA", (W, H), (4, 10, 16, 255))
    layer.putalpha(veil.resize((W, H)))
    c.img = layer

    def put(x, y, text, fnt, fill, sp):        # y は字の上端
        return c.put((x, y - fnt.getbbox("国")[1]), text, fnt, fill, spacing=sp)

    x = put(mt.LEFT, top, "週末のお告げ", mt.font("bold", 42), mt.GOLD, 8)
    put(x + 24, top, label, mt.font("black", 42), mt.PAPER, 2)
    f_s = mt.font("semi", 32)                  # 週末の日付は右端に
    put(mt.RIGHT - sum(f_s.getlength(ch) + 2 for ch in s["sub"]), top + 8, s["sub"], f_s, mt.PAPER, 2)
    th = row_h - (24 if big else 16)
    tx = mt.LEFT + th + (30 if big else 26)
    avail = mt.RIGHT - tx
    f_m, f_n = mt.font("black", m_size), mt.font("bold", n_size)
    name_x = tx + sum(f_m.getlength(ch) + 2 for ch in "12月") + 18
    for i, r in enumerate(rows):
        y = list_top + i * row_h
        pic = shugo_thumb(r, th - 4)
        if pic is not None:
            frame = Image.new("RGBA", (th, th), (96, 116, 124, 255))
            frame.paste(pic, (2, 2))
            c.paste(frame, (mt.LEFT, y + 8))
        line = mt.RUBY_RE.sub(lambda m: m.group(1), str(s["lines"][str(r["month"])])).replace("\n", "")
        parts, f_l = shugo_line(line, avail, sizes, wrap_size)
        block = m_size + gap_a + len(parts) * f_l.size + (len(parts) - 1) * gap_b
        by = y + 8 + (th - block) // 2             # 文字のかたまりを、絵の高さの真ん中に置く
        put(tx, by, f"{r['month']}月", f_m, mt.GOLD, 2)
        put(name_x, by + round((m_size - n_size) * 0.85), r["name"], f_n, mt.PAPER, 3)
        ly = by + m_size + gap_a
        for t in parts:
            put(tx, ly, t, f_l, mt.PAPER, 1)
            ly += f_l.size + gap_b
    return c.done()


def build_shugo(n, s):
    rows = json.load(open(SHUGO, encoding="utf-8"))
    if s.get("style") == "pages":
        return build_shugo_pages(n, s, rows)
    # 何画面かに分けた短い型(既定は 1〜4月・5〜8月・9〜12月 の3画面)。見る人が止めて、自分の月を探す
    n.instant = True
    n.add([("big", s.get("hook", "あなたの誕生月は、\nどこですか。")), ("gap", 30),
           ("body", s.get("lead", "止めて、自分の月を\n探してください。"))], 1.8)
    screens = 2 if s.get("screens") == 2 else 3
    per = -(-len(rows) // screens)
    for i in range(0, len(rows), per):
        part = rows[i:i + per]
        label = f"{part[0]['month']}〜{part[-1]['month']}月"
        n.scenes.append({"bg": n.bg(), "ov": shugo_list_overlay(s, part, label),
                         "dur": 4.2 if screens == 2 else 3.4})


def build_shugo_pages(n, s, rows):
    """以前の型: 1か月ずつ、絵と一言を見せる(約34秒)。"""
    n.add([("big", "この週末の\nお告げ"), ("gap", 30), ("body", f"{s['sub']}\n誕生月の守護妖怪から、ひとこと。")], 3.2)
    for r in rows:
        line = s["lines"][str(r["month"])]
        n.add([("name", r["name"]), ("bar", ""), ("body", line)], 2.3,
              bg_path=art(r["file"], ("_2", "")), focus=float(r.get("focus", 0.42)),
              title_img=art(r["file"], ("_title",)), top_text=f"{r['month']}月生まれ")
    n.add([("big", "あなたの月は、\nどの妖怪でしたか。"), ("gap", 30), ("body", "よい週末を。")], 3.0)


def build_raishu(n, s):
    f = s["file"]
    p1, p2, p3 = art(f, ("_4", "")), art(f, ("_2", "")), art(f, ("_5", "_3", ""))
    n.add([("big", "来週を見守る\n妖怪は。"), ("gap", 30), ("body", s["range"])], 3.0)
    n.add(n.name_items(s["name"], s.get("kana")), 2.8, bg_path=p1, title_img=art(s["file"], ("_title",)))
    n.add([("label", "伝承"), ("body", s["lore"])], read_time(s["lore"]), bg_path=p2 or p1)
    n.add([("label", "来週のお告げ"), ("body", s["omen"])], read_time(s["omen"], lo=3.6), bg_path=p3 or p2 or p1)


def build_zatsugaku(n, s):
    """昼の雑学: 絵巻風の絵(_emaki)があれば、右から左へゆっくりたどる。なければ縦の絵で作る。"""
    f = s.get("file")
    n.out_name = "noon"
    n.instant = True               # 題(見る人への問い)を最初のコマから出す
    n.pan = art(f, ("_emaki",))
    pics = [p for p in (art(f, ("_3", "")), art(f, ("_2", "")), art(f)) if p] or [None]
    n.add([("big", s["title"]), ("gap", 30), ("body", s.get("lead", "今日の守護妖怪の、豆知識です。"))], 3.4,
          bg_path=pics[0])
    for i, part in enumerate(s["parts"]):
        n.add([("body", part)], read_time(part, lo=3.4), bg_path=pics[(i + 1) % len(pics)])
    if s.get("close"):
        n.add([("body", s["close"])], read_time(s["close"], lo=3.2), bg_path=pics[0])


BUILDERS = {
    "quiz": build_quiz,
    "nitaku": build_nitaku,
    "kaidan": lambda n, s: build_story(n, s, "創作の、短い怪談です。", hide=True),
    "kotoba": build_kotoba,
    "shugo": build_shugo,
    "sato": lambda n, s: build_story(n, s, "霧の里の、小さな創作です。"),
    "raishu": build_raishu,
    "zatsugaku": build_zatsugaku,
}


# ---------- 動画 ----------

def pan_frame(pan_img, t, total):
    """絵巻を右から左へたどるときの、t 秒目の画面。"""
    x = int((pan_img.width - W) * (1 - t / total))
    return pan_img.crop((x, 0, x + W, H))


def make_video(scenes, paths, out_path, seed, pan=None, instant=False):
    total = sum(s["dur"] for s in scenes)
    xf, fade = 0.45, 0.3
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    f, starts, t = [], [], 0.0
    if pan:                        # 1枚の横長の絵を、右から左へ(絵巻を読む向き)ゆっくり動かす
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{total:.3f}", "-i", pan]
        f.append(f"[0:v]crop={W}:{H}:x='(in_w-{W})*(1-t/{total:.3f})':y=0,format=yuv420p,setsar=1[x0]")
        for s in scenes:
            starts.append(t)
            t += s["dur"]
        scenes_bg = []
    else:
        scenes_bg = scenes
    for i, (s, (bp, _)) in enumerate(zip(scenes_bg, paths)):
        dur = s["dur"] + (xf if i < len(scenes) - 1 else 0)
        nfr = int(math.ceil(dur * FPS))
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", bp]
        z = f"1+0.06*on/{nfr}" if i % 2 == 0 else f"1.07-0.06*on/{nfr}"
        f.append(f"[{i}:v]scale={W*2}:{H*2}:flags=lanczos,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':"
                 f"y='ih*0.42-(ih/zoom*0.42)':d=1:s={W}x{H}:fps={FPS},format=yuv420p,setsar=1[s{i}]")
        starts.append(t)
        t += s["dur"]
    if pan:
        last, idx = "x0", 1
    else:
        last = "s0"
        for i in range(1, len(scenes)):
            f.append(f"[{last}][s{i}]xfade=transition=fade:duration={xf}:offset={starts[i]:.3f}[x{i}]")
            last = f"x{i}"
        idx = len(scenes)
    light = out_path + ".light.mp4"
    mt.write_light_layer(light, total, seed)
    cmd += ["-i", light]
    f.append(f"[{idx}:v]scale={W}:{H}:flags=bilinear,format=gbrp[lt]")
    f.append(f"[{last}]format=gbrp[bgp]")
    f.append("[bgp][lt]blend=all_mode=screen:shortest=1,format=yuv420p[lit]")
    last, idx = "lit", idx + 1
    for j, s in enumerate(scenes):
        a, b = starts[j] + (0.12 if j else 0), starts[j] + s["dur"]
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{total}", "-i", paths[j][1]]
        fx = f"[{idx}:v]format=rgba"
        if j or not instant:       # instant のときは、最初の場面の文字を最初のコマから出す
            fx += f",fade=t=in:st={a:.2f}:d={fade}:alpha=1"
        if j < len(scenes) - 1:
            fx += f",fade=t=out:st={b - fade + 0.1:.2f}:d={fade}:alpha=1"
        f.append(fx + f"[o{j}]")
        f.append(f"[{last}][o{j}]overlay=0:0:enable='between(t,{a:.2f},{b + 0.1:.2f})'[v{j}]")
        last, idx = f"v{j}", idx + 1
    f.append(f"[{last}]format=yuv420p[vout]")
    maps = ["-map", "[vout]"]
    if os.path.exists(mt.BGM):
        cmd += ["-stream_loop", "-1", "-i", mt.BGM]
        f.append(f"[{idx}:a]atrim=0:{total},asetpts=N/SR/TB,afade=t=out:st={total - 1.5:.2f}:d=1.5[aout]")
        maps += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-filter_complex", ";".join(f)] + maps + [
        "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-r", str(FPS),
        "-t", f"{total}", "-movflags", "+faststart", out_path]
    try:
        subprocess.run(cmd, check=True)
    finally:
        if os.path.exists(light):
            os.remove(light)
    return total


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    if spec.get("type") not in TYPES:
        sys.exit("type は " + " / ".join(TYPES) + " のどれかにしてください。")
    if not spec.get("out"):
        sys.exit("spec に out がありません。")
    out = path_in_root(spec["out"])
    os.makedirs(out, exist_ok=True)
    n = Night(spec)
    try:
        BUILDERS[spec["type"]](n, spec)
    except KeyError as e:
        sys.exit(f"spec に {e} がありません。")
    paths, pan_path, pan_img = [], None, None
    total_dur = sum(s["dur"] for s in n.scenes)
    if n.pan:                      # 絵巻を縦の画面の高さに合わせて広げておく
        src = Image.open(n.pan).convert("RGB")
        pan_img = src.resize((max(W + 2, round(src.width * H / src.height)), H), Image.LANCZOS)
        pan_path = os.path.join(out, "_npan.jpg")
        pan_img.save(pan_path, quality=95)
    t = 0.0
    for i, s in enumerate(n.scenes, start=1):
        bp, op = os.path.join(out, f"_nbg{i:02d}.jpg"), os.path.join(out, f"_nov{i:02d}.png")
        bg = pan_frame(pan_img, t + s["dur"] / 2, total_dur) if pan_img else s["bg"]
        t += s["dur"]
        bg.save(bp, quality=95)
        s["ov"].save(op)
        Image.alpha_composite(bg.convert("RGBA"), s["ov"]).convert("RGB").save(
            os.path.join(out, f"slide_{n.out_name}{i:02d}.jpg"), quality=88)
        paths.append((bp, op))
    total = 0.0
    video = os.path.join(out, f"{n.out_name}.mp4")
    try:
        if spec.get("video", True):
            seed = sum(ord(ch) for ch in json.dumps(spec, ensure_ascii=False)) % 100000
            total = make_video(n.scenes, paths, video, seed, pan=pan_path, instant=n.instant)
    finally:
        for p in [x for pair in paths for x in pair] + ([pan_path] if pan_path else []):
            if os.path.exists(p):
                os.remove(p)
    print("ok:", os.path.join(spec["out"], f"{n.out_name}.mp4"), f"| {total:.1f}秒 | {len(n.scenes)} 場面 | "
          f"{spec['type']}" + (" | 絵巻" if pan_path else ""))


if __name__ == "__main__":
    main()
