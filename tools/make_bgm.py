#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""妖怪のお告げ: 動画のBGMを作る(すべてこの道具で作ったオリジナル曲。外部の音源は使っていない)。

使い方:
    python3 tools/make_bgm.py <出力フォルダ>

4曲の候補を作る(15.5秒、WAV)。いま動画で使っているのは 3「月の笛」(尺八風の笛・遠い太鼓・風)。
動画に使うときは、音量をそろえて tools/bgm.flac に置く:
    ffmpeg -i bgm3_tsuki_no_fue.wav -af "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100" -c:a flac -sample_fmt s16 tools/bgm.flac
"""
import sys

import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt
from scipy.io import wavfile

SR = 44100
DUR = 15.5
TAIL = 6.0
N = int((DUR + TAIL) * SR)

def mf(m): return 440.0 * 2 ** ((m - 69) / 12)
def _f(x, fc, kind, order=2):
    return sosfilt(butter(order, fc, kind, fs=SR, output='sos'), x)
def lp(x, fc, o=2): return _f(x, fc, 'low', o)
def hp(x, fc, o=2): return _f(x, fc, 'high', o)
def bp(x, lo, hi, o=2): return _f(x, [lo, hi], 'band', o)
def tt(d): return np.arange(int(d * SR)) / SR
def norm(x):
    p = np.max(np.abs(x)); return x / p if p > 0 else x
def ramp_in(x, s=0.003):
    k = max(1, int(s * SR)); x[:k] *= np.linspace(0, 1, k); return x
def env_ar(n, att, rel):
    e = np.ones(n); a = int(att * SR); r = int(rel * SR)
    if a: e[:a] = np.sin(np.linspace(0, np.pi / 2, a)) ** 2
    if r: e[-r:] *= np.cos(np.linspace(0, np.pi / 2, r)) ** 2
    return e
def smooth_rand(n, step, rng, lo=0.0, hi=1.0):
    pts = rng.uniform(lo, hi, int(n / (step * SR)) + 3)
    xs = np.arange(len(pts)) * step * SR
    v = np.interp(np.arange(n), xs, pts)
    return lp(v, 1.5 / step, 1)

class Mix:
    def __init__(self):
        self.d = np.zeros((2, N)); self.w = np.zeros((2, N))
    def add(self, sig, start, gain=1.0, pan=0.0, send=0.4):
        i = int(start * SR); n = min(len(sig), N - i)
        if n <= 0: return
        th = (pan + 1) * np.pi / 4
        for c, g in enumerate((np.cos(th), np.sin(th))):
            self.d[c, i:i + n] += sig[:n] * gain * g * (1 - send)
            self.w[c, i:i + n] += sig[:n] * gain * g * send

def ir(decay, seed, bright):
    r = np.random.default_rng(seed); n = int(decay * 1.1 * SR); t = np.arange(n) / SR
    x = lp(r.standard_normal(n) * np.exp(-t * 6.9 / decay), bright)
    x[:int(0.01 * SR)] *= np.linspace(0, 1, int(0.01 * SR))
    return x / np.sqrt(np.sum(x ** 2))

def render(mix, decay, bright, out, wetgain=1.0, predelay=0.035):
    pd = int(predelay * SR)
    L = mix.d[0] + wetgain * np.concatenate([np.zeros(pd), fftconvolve(mix.w[0], ir(decay, 11, bright))])[:N]
    R = mix.d[1] + wetgain * np.concatenate([np.zeros(pd), fftconvolve(mix.w[1], ir(decay, 12, bright))])[:N]
    y = np.stack([L, R])[:, :int(DUR * SR)]
    y -= np.mean(y, axis=1, keepdims=True)
    y = hp(y, 35, 2)
    n = y.shape[1]; e = np.ones(n)
    a = int(0.8 * SR); r = int(2.2 * SR)
    e[:a] = np.linspace(0, 1, a) ** 2; e[-r:] *= np.linspace(1, 0, r) ** 1.5
    y *= e
    y = y / np.max(np.abs(y)) * 0.98
    y = np.tanh(1.3 * y) / np.tanh(1.3)
    y = y / np.max(np.abs(y)) * 0.89
    wavfile.write(out, SR, (y.T * 32767).astype(np.int16))

# ---------- instruments ----------
def koto(m, dur=3.6, bend=0.0, bend_at=0.35, seed=0, bright=1.0):
    r = np.random.default_rng(seed); t = tt(dur); f = mf(m)
    fc = f * (1 + 0.004 * np.exp(-t * 30))
    if bend:
        k = np.clip((t - bend_at) / 0.25, 0, 1); fc = fc * 2 ** (bend / 12 * k * k * (3 - 2 * k))
    ph = 2 * np.pi * np.cumsum(fc) / SR
    s = np.zeros_like(t)
    for k in range(1, 16):
        inh = k * (1 + 0.0003 * k * k)
        if f * inh > 14000: break
        a = (1 / k ** 1.15) * (abs(np.sin(np.pi * k * 0.21)) + 0.08) * (0.7 + 0.3 * r.random())
        a *= bright ** (k - 1)
        s += a * np.sin(ph * inh + r.uniform(0, 6.28)) * np.exp(-t * (1.0 + 0.85 * k))
    nz = bp(r.standard_normal(len(t)), min(f * 2, 6000), min(f * 8, 15000)) * np.exp(-t * 120) * 0.25
    return ramp_in(norm(s + nz), 0.002)

def fmbell(m, dur=4.5, ratio=3.5, I0=2.2, dec=1.3, seed=0):
    t = tt(dur); f = mf(m)
    I = I0 * np.exp(-t * 3.5) + 0.15
    s = np.sin(2 * np.pi * f * t + I * np.sin(2 * np.pi * f * ratio * t)) * np.exp(-t * dec)
    s += 0.25 * np.sin(2 * np.pi * f * 2.0 * t + 1.0) * np.exp(-t * dec * 2.2)
    return ramp_in(norm(s), 0.001)

def rin(m, dur=9.0, dec=0.38, seed=0):
    r = np.random.default_rng(seed); t = tt(dur); f = mf(m)
    s = np.zeros_like(t)
    for rr, a, dk in zip([1, 2.71, 5.15, 8.2], [1, 0.55, 0.28, 0.12], [1, 1.7, 2.9, 4.5]):
        b = r.uniform(0.6, 2.2)
        for fq in (f * rr, f * rr + b):
            s += a * np.sin(2 * np.pi * fq * t + r.uniform(0, 6.28)) * np.exp(-t * dec * dk)
    s += bp(r.standard_normal(len(t)), 2000, 9000) * np.exp(-t * 90) * 0.4
    return ramp_in(norm(s), 0.001)

def saw(f, t, ph): return 2 * ((f * t + ph) % 1.0) - 1
def pad(midis, dur, lo=500, hi=1400, lfo=0.06, att=3.0, rel=3.5, det=0.0035, seed=0):
    r = np.random.default_rng(seed); t = tt(dur); s = np.zeros_like(t)
    for m in midis:
        for d in (-det, 0, det):
            s += saw(mf(m) * (1 + d), t, r.random())
    a = lp(s, lo, 2); b = lp(s, hi, 2)
    x = 0.5 - 0.5 * np.cos(2 * np.pi * lfo * t + r.uniform(0, 1))
    return norm((a * (1 - x) + b * x) * env_ar(len(t), att, rel))

def organ(midis, dur, att=2.5, rel=3.0, seed=0):  # sho-like reed cluster
    r = np.random.default_rng(seed); t = tt(dur); s = np.zeros_like(t)
    for m in midis:
        f = mf(m) * (1 + r.uniform(-0.002, 0.002))
        for k, a in [(1, 1), (2, 0.45), (3, 0.3), (4, 0.15), (5, 0.08)]:
            s += a * np.sin(2 * np.pi * f * k * t + r.uniform(0, 6.28))
    s *= 1 + 0.08 * np.sin(2 * np.pi * 0.21 * t)
    return norm(lp(s, 2500) * env_ar(len(t), att, rel))

def drone(m, dur, att=2.5, rel=3.0, seed=0):
    r = np.random.default_rng(seed); t = tt(dur); f = mf(m)
    s = np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * 2 * f * t + 0.3) + 0.3 * np.sin(2 * np.pi * 3 * f * t + 1.1) \
        + 0.15 * np.sin(2 * np.pi * 4 * f * t + 2.0)
    s *= 0.8 + 0.2 * smooth_rand(len(t), 1.5, r)
    return norm(s * env_ar(len(t), att, rel))

def wind(dur, seed=0, lo=180, hi=900):
    r = np.random.default_rng(seed); n = int(dur * SR)
    w = np.cumsum(r.standard_normal(n)); w = hp(w, 20, 1)
    w = bp(w, lo, hi, 2) * (0.35 + 0.65 * smooth_rand(n, 1.8, r))
    return norm(w)

def taiko(seed=0):
    r = np.random.default_rng(seed); t = tt(2.5)
    f = 52 + 70 * np.exp(-t * 18)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.0)
    s += 0.35 * np.sin(2 * np.pi * np.cumsum(f * 2.3) / SR) * np.exp(-t * 6)
    s += lp(r.standard_normal(len(t)), 400) * np.exp(-t * 30) * 0.6
    return ramp_in(norm(s), 0.001)

def shaku(m, dur, from_m=None, gl=0.35, vib=0.007, breath=0.22, seed=0):
    r = np.random.default_rng(seed); t = tt(dur); f = mf(m)
    fc = np.full(len(t), f)
    if from_m is not None:
        k = np.clip(t / gl, 0, 1); s_ = k * k * (3 - 2 * k); f0 = mf(from_m); fc = f0 * (f / f0) ** s_
    ve = np.clip((t - dur * 0.35) / (dur * 0.4 + 1e-3), 0, 1)
    fc = fc * (1 + vib * ve * np.sin(2 * np.pi * 5.0 * t))
    ph = 2 * np.pi * np.cumsum(fc) / SR
    tone = np.sin(ph) + 0.22 * np.sin(2 * ph + 0.4) + 0.08 * np.sin(3 * ph + 1.0)
    e = env_ar(len(t), min(0.16, dur * 0.3), min(0.4, dur * 0.4)) * (0.85 + 0.15 * np.clip(t / dur, 0, 1))
    nz = bp(r.standard_normal(len(t)), f * 0.9, min(f * 4, 12000)) * 0.7 + hp(r.standard_normal(len(t)), 3000, 4) * 0.04
    nz *= breath * (0.6 + 1.6 * np.exp(-t * 5))
    return norm((tone * 0.85 + lp(nz, min(f * 4, 9000), 2) * 1.3) * e)

def whistle(m1, m2, dur, seed=0):
    t = tt(dur); k = np.clip(t / dur, 0, 1); s_ = k * k * (3 - 2 * k)
    fc = mf(m1) * (mf(m2) / mf(m1)) ** s_ * (1 + 0.01 * np.sin(2 * np.pi * 4.3 * t))
    s = np.sin(2 * np.pi * np.cumsum(fc) / SR)
    return norm(s * env_ar(len(t), dur * 0.4, dur * 0.5))

def swell(dur, seed=0):
    r = np.random.default_rng(seed); t = tt(dur)
    s = hp(r.standard_normal(len(t)), 2500, 2) * (t / dur) ** 3
    s[-int(0.02 * SR):] *= np.linspace(1, 0, int(0.02 * SR))
    return norm(s)

# ---------- tracks ----------
# D in-scale (miyako-bushi): D Eb G A Bb
def t1(out):  # 霧の鳥居
    m = Mix()
    m.add(wind(DUR, 1), 0, 0.10, 0.0, 0.1)
    m.add(drone(38, DUR, seed=1), 0, 0.12, -0.1, 0.3)
    m.add(drone(45, DUR, seed=2), 0, 0.07, 0.1, 0.3)
    m.add(pad([50, 57, 63], DUR, 450, 1300, seed=3), 0, 0.06, -0.5, 0.6)
    m.add(pad([50, 57, 63], DUR, 450, 1300, seed=4), 0, 0.06, 0.5, 0.6)
    notes = [(0.8, 50, 0, -0.3), (0.8, 69, 0, 0.2), (1.3, 70, 0, 0.25), (1.8, 69, 0, 0.2), (2.6, 67, 0, 0.1),
             (4.8, 74, 0, 0.3), (5.2, 70, 0, 0.25), (5.6, 69, 0, 0.2), (6.4, 50, 0, -0.3), (6.4, 63, 0, 0.0),
             (8.4, 67, 0, 0.1), (8.8, 69, 0, 0.2), (9.4, 62, 1, 0.0),
             (11.2, 50, 0, -0.3), (11.2, 69, 0, 0.2), (11.6, 70, 0, 0.25), (12.3, 69, 0, 0.2), (12.3, 62, 0, -0.1)]
    for i, (st, n, b, p) in enumerate(notes):
        g = 0.28 if n > 55 else 0.22
        m.add(koto(n, 4.0, bend=b, seed=10 + i), st, g, p, 0.45)
    render(m, 4.5, 4500, out)

# D hirajoshi-ish: D E F A Bb
def t2(out):  # 狐火
    m = Mix(); r = np.random.default_rng(5)
    m.add(wind(DUR, 2, 300, 1400), 0, 0.05, 0, 0.2)
    m.add(pad([50, 57, 62], DUR, 400, 1100, lfo=0.05, seed=6), 0, 0.07, -0.4, 0.5)
    m.add(pad([50, 57, 62], DUR, 400, 1100, lfo=0.05, seed=7), 0, 0.07, 0.4, 0.5)
    hi = organ([69, 74, 76], DUR, att=4, rel=4, seed=8) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.3 * tt(DUR)))
    m.add(hi, 0, 0.035, 0.0, 0.8)
    m.add(rin(62, 9, seed=9), 0.4, 0.22, 0, 0.5)
    scale = [74, 76, 77, 81, 82, 86, 88, 89]
    seq = [(1.4, 81), (1.9, 77), (2.4, 76), (2.9, 74), (4.2, 82), (4.6, 81), (5.0, 77), (5.9, 76),
           (7.4, 86), (7.8, 82), (8.2, 81), (8.6, 77), (9.6, 76), (10.0, 77),
           (11.4, 81), (11.8, 82), (12.2, 86), (12.9, 81)]
    for i, (st, n) in enumerate(seq):
        m.add(fmbell(n, 4.5, ratio=3.5, I0=1.8, dec=1.4, seed=i), st + r.uniform(-0.04, 0.04), 0.16,
              r.uniform(-0.7, 0.7), 0.7)
    m.add(rin(57, 9, seed=10), 7.0, 0.16, 0.0, 0.5)
    m.add(swell(1.6, 1), 5.4, 0.04, -0.3, 0.6)
    m.add(swell(1.6, 2), 10.8, 0.04, 0.3, 0.6)
    render(m, 5.5, 6000, out)

def t3(out):  # 月の笛
    m = Mix()
    m.add(wind(DUR, 3), 0, 0.09, 0.0, 0.1)
    m.add(drone(38, DUR, seed=11), 0, 0.12, 0, 0.3)
    m.add(organ([62, 64, 69, 71], DUR, att=4, rel=4, seed=12), 0, 0.04, -0.3, 0.6)
    m.add(organ([62, 64, 69, 71], DUR, att=4, rel=4, seed=13), 0, 0.04, 0.3, 0.6)
    m.add(taiko(1), 0.25, 0.30, -0.1, 0.55)
    m.add(rin(62, 9, seed=14), 0.3, 0.14, 0.1, 0.5)
    m.add(taiko(2), 7.4, 0.22, -0.1, 0.6)
    m.add(taiko(3), 7.75, 0.14, -0.1, 0.6)
    ph = [(1.3, 69, 67, 2.3), (3.7, 70, None, 0.8), (4.45, 69, None, 2.0), (7.0, 74, 72, 1.7),
          (8.75, 75, None, 0.7), (9.45, 74, None, 1.1), (10.6, 70, None, 1.1), (11.75, 69, 70, 3.0)]
    for i, (st, n, fr, d) in enumerate(ph):
        m.add(shaku(n, d, from_m=fr, seed=20 + i), st, 0.22, 0.1, 0.45)
    render(m, 4.8, 5000, out)

def t4(out):  # 深い霧
    m = Mix()
    m.add(wind(DUR, 4, 150, 700), 0, 0.12, 0, 0.1)
    m.add(pad([38, 45, 51], DUR, 250, 900, lfo=0.045, seed=15), 0, 0.09, -0.5, 0.5)
    m.add(pad([38, 45, 51], DUR, 250, 900, lfo=0.045, seed=16), 0, 0.09, 0.5, 0.5)
    m.add(rin(62, 9, dec=0.32, seed=17), 0.5, 0.20, -0.1, 0.5)
    rv = rin(63, 2.2, dec=0.5, seed=18)[::-1].copy(); rv[-int(0.03 * SR):] *= np.linspace(1, 0, int(0.03 * SR))
    m.add(rv, 3.8, 0.08, 0.2, 0.6)
    m.add(rin(51, 9, dec=0.3, seed=19), 6.0, 0.22, 0.1, 0.5)
    m.add(whistle(81, 82, 3.2), 2.6, 0.045, 0.5, 0.9)
    m.add(whistle(82, 79, 3.4), 8.6, 0.04, -0.5, 0.9)
    rv2 = rin(58, 2.2, dec=0.5, seed=20)[::-1].copy(); rv2[-int(0.03 * SR):] *= np.linspace(1, 0, int(0.03 * SR))
    m.add(rv2, 8.8, 0.08, -0.2, 0.6)
    m.add(rin(57, 9, dec=0.3, seed=21), 11.0, 0.20, 0.0, 0.5)
    m.add(koto(38, 4.0, bend=1, bend_at=0.6, seed=22, bright=0.85), 1.2, 0.20, -0.2, 0.4)
    m.add(koto(39, 4.0, seed=23, bright=0.85), 8.0, 0.18, -0.2, 0.4)
    render(m, 6.0, 3500, out)

if __name__ == '__main__':
    d = sys.argv[1]
    for fn, name in [(t1, 'bgm1_kiri_no_torii'), (t2, 'bgm2_kitsunebi'), (t3, 'bgm3_tsuki_no_fue'), (t4, 'bgm4_fukai_kiri')]:
        fn(f'{d}/{name}.wav'); print('ok', name)
