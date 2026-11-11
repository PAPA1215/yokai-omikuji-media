#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""妖怪のお告げ: 「あなたの守護妖怪」を12か月ぶん順に見せる縦型動画(TikTok用)を作る。

使い方(リポジトリの一番上のフォルダで実行する):
    python3 tools/make_shugo_video.py out/shugo

誕生月と守護妖怪の割り当ては data/shugo.json。絵は art/<ファイル名>_2.png(なければ本体)、
名前は art/<ファイル名>_title.png の筆文字を使う。出力は <out>/tiktok.mp4(約29秒)。
"""
import json
import math
import os
import subprocess
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_tiktok as mt  # noqa: E402

ROOT = os.path.dirname(HERE)
W, H, FPS = mt.W, mt.H, mt.FPS
INTRO, MONTH, OUTRO = 2.6, 2.0, 2.8


def art_path(stem, sufs):
    for suf in sufs:
        for ext in mt.IMG_EXT:
            p = os.path.join(ROOT, "art", f"{stem}{suf}{ext}")
            if os.path.exists(p):
                return p
    return None


def head(c):
    c.put((mt.LEFT, mt.HEADER_Y), "あなたの守護妖怪", mt.font("bold", 42), mt.GOLD, spacing=8)
    c.put((mt.LEFT, mt.HEADER_Y + 64), "誕生月でわかります", mt.font("semi", 34), mt.PAPER, spacing=2)


def text_slide(big, body):
    rows, top = mt.layout([("big", big), ("gap", 34), ("body", body)], {})
    c = mt.Canvas(top)
    head(c)
    mt.draw_rows(c, rows, top)
    return c.done()


def month_slide(row):
    line = row["line"]
    if "\n" not in line and "、" in line:
        a, b = line.split("、", 1)
        line = a + "、\n" + b
    spec = {"_title": art_path(row["file"], ["_title"])}
    rows, top = mt.layout([("name", row["name"]), ("bar", ""), ("body", line)], spec)
    f_m = mt.font("black", 88)
    top_m = top - 124
    c = mt.Canvas(top_m)
    head(c)
    c.put((mt.LEFT, top_m), f"{row['month']}月生まれ", f_m, mt.GOLD, spacing=4)
    mt.draw_rows(c, rows, top)
    return c.done()


def build(segs, out_path, seed=12):
    """segs: [{"bg": 絵, "ov": 文字の画像, "dur": 秒}]。絵はゆっくり寄り引きし、なめらかに切り替える。"""
    total = sum(s["dur"] for s in segs)
    xf, fade = 0.45, 0.3
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    f, starts, t = [], [], 0.0
    for i, s in enumerate(segs):
        dur = s["dur"] + (xf if i < len(segs) - 1 else 0)
        nfr = int(math.ceil(dur * FPS))
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", s["bg"]]
        z = f"1+0.06*on/{nfr}" if i % 2 == 0 else f"1.07-0.06*on/{nfr}"
        f.append(f"[{i}:v]scale={W*2}:{H*2}:flags=lanczos,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':"
                 f"y='ih*0.42-(ih/zoom*0.42)':d=1:s={W}x{H}:fps={FPS},format=yuv420p,setsar=1[s{i}]")
        starts.append(t)
        t += s["dur"]
    last = "s0"
    for i in range(1, len(segs)):
        f.append(f"[{last}][s{i}]xfade=transition=fade:duration={xf}:offset={starts[i]:.3f}[x{i}]")
        last = f"x{i}"
    idx = len(segs)
    light = out_path + ".light.mp4"
    mt.write_light_layer(light, total, seed)
    cmd += ["-i", light]
    f.append(f"[{idx}:v]scale={W}:{H}:flags=bilinear,format=gbrp[lt]")
    f.append(f"[{last}]format=gbrp[bgp]")
    f.append("[bgp][lt]blend=all_mode=screen:shortest=1,format=yuv420p[lit]")
    last = "lit"
    idx += 1
    for j, s in enumerate(segs):
        a, b = starts[j] + (0.12 if j else 0), starts[j] + s["dur"]
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{total}", "-i", s["ov"]]
        fx = f"[{idx}:v]format=rgba,fade=t=in:st={a:.2f}:d={fade}:alpha=1"
        if j < len(segs) - 1:
            fx += f",fade=t=out:st={b - fade + 0.1:.2f}:d={fade}:alpha=1"
        f.append(fx + f"[o{j}]")
        f.append(f"[{last}][o{j}]overlay=0:0:enable='between(t,{a:.2f},{b + 0.1:.2f})'[v{j}]")
        last = f"v{j}"
        idx += 1
    f.append(f"[{last}]format=yuv420p[vout]")
    cmd += ["-f", "lavfi", "-t", f"{total}", "-i", "anoisesrc=color=brown:amplitude=0.9:seed=11:sample_rate=44100"]
    f.append(f"[{idx}:a]highpass=f=90,lowpass=f=420,tremolo=f=0.12:d=0.55,volume=0.5,"
             f"afade=t=in:st=0:d=1.2,afade=t=out:st={total - 1.5:.2f}:d=1.5[aout]")
    cmd += ["-filter_complex", ";".join(f), "-map", "[vout]", "-map", "[aout]", "-c:a", "aac", "-b:a", "128k",
            "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-r", str(FPS),
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
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    rows = json.load(open(os.path.join(ROOT, "data", "shugo.json"), encoding="utf-8"))
    tmp, segs = [], []

    def add(bg_file, overlay, dur, tag):
        bg = mt.cover(Image.open(bg_file), 0.42)
        bp, op = os.path.join(out, f"_bg_{tag}.jpg"), os.path.join(out, f"_ov_{tag}.png")
        bg.save(bp, quality=95)
        overlay.save(op)
        Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB").save(
            os.path.join(out, f"slide_{tag}.jpg"), quality=88)
        tmp.extend([bp, op])
        segs.append({"bg": bp, "ov": op, "dur": dur})

    first = art_path(rows[1]["file"], ["_3", ""])
    lastbg = art_path(rows[6]["file"], ["_3", ""])
    add(first, text_slide("あなたの\n守護妖怪は？", "誕生月で決まります。\n自分の月を探してください。"), INTRO, "00")
    for r in rows:
        add(art_path(r["file"], ["_2", ""]), month_slide(r), MONTH, f"{r['month']:02d}")
    add(lastbg, text_slide("あなたの月は、\nどの妖怪でしたか。", "毎朝7時に、\n今日の守護妖怪を届けます。"), OUTRO, "99")
    total = build(segs, os.path.join(out, "tiktok.mp4"))
    for p in tmp:
        os.remove(p)
    print("ok:", os.path.join(out, "tiktok.mp4"), f"| {total:.1f}秒 | {len(segs)} 場面")


if __name__ == "__main__":
    main()
