#!/usr/bin/env python3
"""Render index.md (structured HTML blocks) into a standalone index.html demo page."""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "index.md"
OUT = ROOT / "index.html"

TITLE = "AVIO"
SUBTITLE = "Object-Level Addition and Removal for Audiovisual Scenes"
REPO_URL = "https://github.com/wx83/AVIO-Object-Level-Addition-and-Removal-for-Audiovisual-Scenes"

RE_H = re.compile(r'<h([123]) id="([^"]+)"><span class="num">([^<]*)</span>(.*?)</h\1>')
RE_DESC = re.compile(r'<p class="desc"[^>]*>(.*?)</p>')
RE_EX = re.compile(r'<div class="ex"><span class="tag">([^<]+)</span><p class="prompt">(.*?)</p><div class="row (c\d)">(.*?)</div>(?:<p class="why">(.*?)</p>)?</div>$')
RE_FIG = re.compile(r'<figure( class="[^"]*")?>(.*?)</figure>')
RE_MEDIA = re.compile(r'<(video|audio)([^>]*)src="([^"]+)"[^>]*>')
RE_CAP = re.compile(r'<figcaption><b>([^<]*)</b>(?:<br><span>([^<]*)</span>)?</figcaption>')
RE_PROMPT = re.compile(r'^(.*?)<q>(.*?)</q>$')


def parse(text):
    intro = None
    nodes = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = RE_H.match(line)
        if m:
            nodes.append({"kind": "h", "level": int(m[1]), "id": m[2], "num": m[3].strip(), "title": m[4].strip()})
            continue
        m = RE_DESC.match(line)
        if m:
            if not nodes:
                intro = m[1]
            else:
                nodes.append({"kind": "desc", "html": m[1]})
            continue
        m = RE_EX.match(line)
        if m:
            tag, prompt, cols, figs_html, why = m.groups()
            pm = RE_PROMPT.match(prompt)
            verb, obj = (pm[1].strip(), pm[2]) if pm else (prompt, "")
            figs = []
            for fm in RE_FIG.finditer(figs_html):
                body = fm[2]
                mm = RE_MEDIA.search(body)
                cm = RE_CAP.search(body)
                figs.append({
                    "kind": mm[1],
                    "src": mm[3],
                    "muted": " muted" in mm[2],
                    "label": cm[1],
                    "sub": cm[2] or "",
                })
            nodes.append({"kind": "ex", "tag": tag, "verb": verb, "obj": obj, "cols": int(cols[1]), "figs": figs, "why": why})
    return intro, nodes


NAV_LABEL = {"unimodal": "Unimodal baselines", "joint": "Joint baselines", "more": "More examples", "failures": "Failures"}
ROLE = {"Ours": "ours", "Reference": "ref", "Input": "input", "Original clip": "input", "Edited clip": "ref", "Object mask": "mask"}
TAG_KIND = {"R": "rm", "A": "add", "D": "data", "F": "fail"}


def render_fig(f, i):
    role = ROLE.get(f["label"], "base")
    sub = f'<span class="sub">{html.escape(f["sub"])}</span>' if f["sub"] else ""
    if f["kind"] == "audio":
        media = f'<audio controls preload="none" data-src="{f["src"]}"></audio>'
    else:
        muted = " muted" if f["muted"] else ""
        media = (f'<div class="vwrap"><video playsinline preload="none"{muted} data-src="{f["src"]}"></video>'
                 f'<button class="solo" type="button" title="Solo audio" aria-label="Solo audio"></button>'
                 f'{"<span class=badge>silent</span>" if f["muted"] else ""}</div>')
    return (f'<figure class="fig {role}{" au" if f["kind"] == "audio" else ""}" data-i="{i}">{media}'
            f'<figcaption><span class="lbl">{html.escape(f["label"])}</span>{sub}</figcaption></figure>')


def render_ex(n):
    kind = TAG_KIND.get(n["tag"][0], "base")
    wide = n["cols"] >= 5
    audio_only = all(f["kind"] == "audio" for f in n["figs"])
    figs = "".join(render_fig(f, i) for i, f in enumerate(n["figs"]))
    why = f'<blockquote class="why"><span class="who">Judge</span>{n["why"].replace("<b>Judge:</b> ", "", 1)}</blockquote>' if n["why"] else ""
    search = html.escape(f'{n["tag"]} {n["verb"]} {n["obj"]}'.lower(), quote=True)
    return (f'<article class="card {kind}{" wide" if wide else ""}{" audio" if audio_only else ""}" data-search="{search}">'
            f'<header class="card-h"><span class="tag">{n["tag"]}</span>'
            f'<h4 class="prompt"><span class="verb">{n["verb"]}</span> <q>{n["obj"]}</q></h4>'
            f'<div class="ctl"><button type="button" class="playall" aria-label="Play all clips together">'
            f'<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><path d="M4 2.5v11l9-5.5z" fill="currentColor"/></svg><span>Play all</span></button></div></header>'
            f'<div class="grid c{n["cols"]}">{figs}</div>{why}</article>')


def render(intro, nodes):
    body = []
    toc = []
    open_cards = False

    def close_cards():
        nonlocal open_cards
        if open_cards:
            body.append("</div>")
            open_cards = False

    section_depth = 0
    for n in nodes:
        if n["kind"] == "h":
            close_cards()
            lvl = n["level"]
            while section_depth >= lvl:
                body.append("</section>")
                section_depth -= 1
            body.append(f'<section id="{n["id"]}" class="sec l{lvl}">'
                        f'<h{lvl + 1} class="sh"><span class="num">{n["num"]}</span>{n["title"]}</h{lvl + 1}>')
            section_depth = lvl
            toc.append(n)
        elif n["kind"] == "desc":
            body.append(f'<p class="desc">{n["html"]}</p>')
        elif n["kind"] == "ex":
            if not open_cards:
                body.append('<div class="cards">')
                open_cards = True
            body.append(render_ex(n))
    close_cards()
    while section_depth > 0:
        body.append("</section>")
        section_depth -= 1

    toc_html = []
    for n in toc:
        toc_html.append(f'<li class="l{n["level"]}"><a href="#{n["id"]}"><span class="num">{n["num"]}</span>{n["title"]}</a></li>')

    n_ex = sum(1 for n in nodes if n["kind"] == "ex")
    n_clip = sum(len(n["figs"]) for n in nodes if n["kind"] == "ex")
    top_secs = [n for n in toc if n["level"] == 1]
    nav = "".join(f'<a href="#{n["id"]}">{NAV_LABEL.get(n["id"], n["title"])}</a>' for n in top_secs)

    return TEMPLATE.replace("{{TOC}}", "\n".join(toc_html)).replace("{{BODY}}", "\n".join(body)) \
        .replace("{{INTRO}}", intro or "").replace("{{NAV}}", nav) \
        .replace("{{N_EX}}", str(n_ex)).replace("{{N_CLIP}}", str(n_clip)) \
        .replace("{{TITLE}}", TITLE).replace("{{SUBTITLE}}", SUBTITLE).replace("{{REPO}}", REPO_URL)


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}} — {{SUBTITLE}}</title>
<meta name="description" content="Demo page: joint audio-visual object addition and removal. Dataset samples, best results, baseline comparisons, more examples and failure cases.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#f6f7fb;--bg2:#ffffff;--bg3:#eef1f7;--line:#dfe4ee;--line2:#c9d1e0;
  --fg:#111827;--fg2:#4b5563;--fg3:#8b94a7;
  --accent:#3b5bdb;--accent2:#5c7cfa;--accent-soft:#e8edff;
  --rm:#d9480f;--rm-soft:#fff0e6;--add:#0b7285;--add-soft:#e3fafc;--data:#5f3dc4;--data-soft:#f1ecff;--fail:#a61e4d;--fail-soft:#ffe9f0;
  --ours:#3b5bdb;--ref:#2b8a3e;
  --shadow:0 1px 2px rgba(16,24,40,.06),0 8px 24px -12px rgba(16,24,40,.18);
  --r:14px;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0c0f16;--bg2:#141925;--bg3:#1b2131;--line:#252d40;--line2:#344057;
  --fg:#eef1f7;--fg2:#aab3c5;--fg3:#6f7a90;
  --accent:#8da2ff;--accent2:#a5b4ff;--accent-soft:#1b2447;
  --rm:#ff9c6e;--rm-soft:#3a1f12;--add:#66d9e8;--add-soft:#0f2e36;--data:#b197fc;--data-soft:#261b4a;--fail:#ff8fb8;--fail-soft:#3d1428;
  --ours:#8da2ff;--ref:#69db7c;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px -14px rgba(0,0,0,.7);
}}
:root[data-theme="dark"]{
  --bg:#0c0f16;--bg2:#141925;--bg3:#1b2131;--line:#252d40;--line2:#344057;
  --fg:#eef1f7;--fg2:#aab3c5;--fg3:#6f7a90;
  --accent:#8da2ff;--accent2:#a5b4ff;--accent-soft:#1b2447;
  --rm:#ff9c6e;--rm-soft:#3a1f12;--add:#66d9e8;--add-soft:#0f2e36;--data:#b197fc;--data-soft:#261b4a;--fail:#ff8fb8;--fail-soft:#3d1428;
  --ours:#8da2ff;--ref:#69db7c;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px -14px rgba(0,0,0,.7);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:72px}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 Inter,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
q{quotes:"“" "”";font-style:italic}
button{font:inherit;color:inherit}

/* top bar */
.top{position:sticky;top:0;z-index:50;background:color-mix(in srgb,var(--bg2) 82%,transparent);backdrop-filter:saturate(1.4) blur(12px);-webkit-backdrop-filter:saturate(1.4) blur(12px);border-bottom:1px solid var(--line)}
.top .in{max-width:1400px;margin:0 auto;padding:0 20px;height:56px;display:flex;align-items:center;gap:14px}
.brand{font-weight:800;letter-spacing:-.02em;font-size:17px;color:var(--fg);display:flex;align-items:center;gap:8px}
.brand i{width:10px;height:10px;border-radius:3px;background:linear-gradient(135deg,var(--rm),var(--add));display:inline-block}
.topnav{display:flex;gap:2px;margin-left:8px;overflow:auto;scrollbar-width:none}
.topnav::-webkit-scrollbar{display:none}
.topnav a{padding:6px 10px;border-radius:8px;color:var(--fg2);font-weight:500;font-size:13.5px;white-space:nowrap}
.topnav a:hover,.topnav a.on{background:var(--bg3);color:var(--fg);text-decoration:none}
.sp{flex:1}
.search{position:relative}
.search input{width:220px;max-width:38vw;height:34px;border:1px solid var(--line2);background:var(--bg2);color:var(--fg);border-radius:9px;padding:0 30px 0 32px;font:inherit;font-size:13.5px;outline:none}
.search input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.search svg{position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--fg3)}
.search .n{position:absolute;right:9px;top:50%;transform:translateY(-50%);font:600 11px JetBrains Mono,monospace;color:var(--fg3)}
.ib{height:34px;min-width:34px;padding:0 10px;border:1px solid var(--line2);background:var(--bg2);border-radius:9px;cursor:pointer;display:inline-flex;align-items:center;gap:6px;color:var(--fg2);font-size:13px;font-weight:500}
.ib:hover{background:var(--bg3);color:var(--fg)}

/* hero */
.hero{position:relative;overflow:hidden;border-bottom:1px solid var(--line);background:var(--bg2)}
.hero::before{content:"";position:absolute;inset:-40% -10% auto;height:120%;background:
  radial-gradient(600px 300px at 15% 20%,color-mix(in srgb,var(--rm) 22%,transparent),transparent 70%),
  radial-gradient(600px 300px at 85% 10%,color-mix(in srgb,var(--add) 22%,transparent),transparent 70%),
  radial-gradient(500px 260px at 55% 90%,color-mix(in srgb,var(--data) 16%,transparent),transparent 70%);pointer-events:none}
.hero .in{position:relative;max-width:1400px;margin:0 auto;padding:56px 20px 40px}
.kicker{font:600 12px JetBrains Mono,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
h1.title{margin:10px 0 6px;font-size:clamp(30px,4.6vw,52px);line-height:1.05;letter-spacing:-.035em;font-weight:800}
h1.title span{background:linear-gradient(90deg,var(--rm),var(--add));-webkit-background-clip:text;background-clip:text;color:transparent}
.lead{max-width:820px;color:var(--fg2);font-size:16.5px;margin:14px 0 0}
.lead b{color:var(--fg)}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin:26px 0 0}
.stat{background:color-mix(in srgb,var(--bg2) 70%,transparent);border:1px solid var(--line);border-radius:12px;padding:10px 14px;min-width:120px}
.stat b{display:block;font:700 20px/1.1 JetBrains Mono,monospace;letter-spacing:-.02em}
.stat span{font-size:12px;color:var(--fg3);font-weight:500}
.cta{display:flex;gap:10px;flex-wrap:wrap;margin-top:24px}
.btn{display:inline-flex;align-items:center;gap:8px;height:40px;padding:0 16px;border-radius:10px;font-weight:600;font-size:14px;border:1px solid var(--line2);background:var(--bg2);color:var(--fg)}
.btn:hover{background:var(--bg3);text-decoration:none}
.btn.pri{background:var(--accent);border-color:var(--accent);color:#fff}
.btn.pri:hover{background:var(--accent2)}
.legend{display:flex;flex-wrap:wrap;gap:8px 16px;margin-top:22px;font-size:12.5px;color:var(--fg2)}
.legend .pill{display:inline-flex;align-items:center;gap:6px}
.legend .tag{padding:1px 7px}
.legend .hint{display:inline;color:var(--fg3)}
.legend .hint b{color:var(--fg2)}
@media (max-width:640px){.legend .hint{flex-basis:100%;margin-top:4px}}

/* layout */
.wrap{max-width:1400px;margin:0 auto;padding:24px 20px 80px;display:grid;grid-template-columns:250px minmax(0,1fr);gap:36px}
aside.toc{position:sticky;top:72px;align-self:start;max-height:calc(100vh - 88px);overflow:auto;padding-right:6px;scrollbar-width:thin}
.toc h5{margin:4px 0 8px;font:600 11px JetBrains Mono,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--fg3)}
.toc ul{list-style:none;margin:0;padding:0;border-left:1px solid var(--line)}
.toc li a{display:block;padding:5px 10px 5px 12px;margin-left:-1px;border-left:2px solid transparent;color:var(--fg2);font-size:13px;line-height:1.35}
.toc li.l1 a{font-weight:600;color:var(--fg);margin-top:6px}
.toc li.l2 a{padding-left:22px}
.toc li.l3 a{padding-left:34px;font-size:12px;color:var(--fg3)}
.toc li a:hover{color:var(--fg);text-decoration:none;background:var(--bg3)}
.toc li a.on{border-left-color:var(--accent);color:var(--accent)}
.toc .num{font:500 11px JetBrains Mono,monospace;color:var(--fg3);margin-right:7px}
.toc li.l1 a .num{color:var(--accent)}
main{min-width:0}

/* sections */
.sec.l1{margin-top:44px;padding-top:28px;border-top:1px solid var(--line)}
.sec.l1:first-child{margin-top:0;padding-top:0;border-top:0}
.sec.l2{margin-top:30px}
.sec.l3{margin-top:22px}
.sh{margin:0;letter-spacing:-.02em;font-weight:700;display:flex;align-items:baseline;gap:10px}
.sec.l1>.sh{font-size:26px}
.sec.l2>.sh{font-size:19px}
.sec.l3>.sh{font-size:15.5px;color:var(--fg2)}
.sh .num{font:600 .72em JetBrains Mono,monospace;color:var(--accent);letter-spacing:0}
.sec.l3>.sh .num{color:var(--fg3)}
.desc{color:var(--fg2);font-size:14px;max-width:900px;margin:6px 0 14px}
.desc b{color:var(--fg)}
.sec.l3>.desc{font-size:13px;margin-bottom:10px}

/* cards */
.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-bottom:8px}
.card{background:var(--bg2);border:1px solid var(--line);border-radius:var(--r);padding:12px 14px 14px;box-shadow:var(--shadow);position:relative;transition:border-color .15s,box-shadow .15s}
.card.wide{grid-column:1/-1}
.card.playing{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft),var(--shadow)}
.card.hide{display:none}
.card-h{display:flex;align-items:center;gap:10px;margin-bottom:10px;min-height:28px}
.tag{font:700 11px/1 JetBrains Mono,monospace;letter-spacing:.02em;padding:5px 8px;border-radius:7px;white-space:nowrap;background:var(--bg3);color:var(--fg2)}
.card.rm .tag,.legend .rm{background:var(--rm-soft);color:var(--rm)}
.card.add .tag,.legend .add{background:var(--add-soft);color:var(--add)}
.card.data .tag,.legend .data{background:var(--data-soft);color:var(--data)}
.card.fail .tag,.legend .fail{background:var(--fail-soft);color:var(--fail)}
.prompt{margin:0;font-size:14.5px;font-weight:600;flex:1;min-width:0;letter-spacing:-.01em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.prompt .verb{color:var(--fg3);font-weight:500}
.prompt q{color:var(--accent);font-style:italic}
.card.rm .prompt q{color:var(--rm)}.card.add .prompt q{color:var(--add)}.card.data .prompt q{color:var(--data)}.card.fail .prompt q{color:var(--fail)}
.ctl{display:flex;gap:6px}
.playall{display:inline-flex;align-items:center;gap:6px;height:28px;padding:0 10px;border-radius:8px;border:1px solid var(--line2);background:var(--bg2);cursor:pointer;font-size:12px;font-weight:600;color:var(--fg2)}
.playall:hover{background:var(--bg3);color:var(--fg)}
.card.playing .playall{background:var(--accent);border-color:var(--accent);color:#fff}
.card.audio .playall{display:none}
.grid{display:grid;gap:10px}
.grid.c2{grid-template-columns:repeat(2,minmax(0,1fr));max-width:480px}
.grid.c3{grid-template-columns:repeat(3,minmax(0,1fr))}
.grid.c4{grid-template-columns:repeat(4,minmax(0,1fr))}
.grid.c5{grid-template-columns:repeat(5,minmax(0,1fr))}
.grid.c6{grid-template-columns:repeat(6,minmax(0,1fr))}
.fig{margin:0;min-width:0}
.vwrap{position:relative;aspect-ratio:1/1;background:#000;border-radius:9px;overflow:hidden;border:2px solid transparent;transition:border-color .15s}
.vwrap video{width:100%;height:100%;display:block;object-fit:cover;cursor:pointer}
.fig.ours .vwrap{border-color:color-mix(in srgb,var(--ours) 55%,transparent)}
.fig.ref .vwrap{border-color:color-mix(in srgb,var(--ref) 45%,transparent)}
.fig.solo .vwrap{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.fig .solo{position:absolute;right:6px;top:6px;width:24px;height:24px;border-radius:7px;border:0;background:rgba(0,0,0,.55);color:#fff;cursor:pointer;opacity:0;transition:opacity .15s;display:flex;align-items:center;justify-content:center}
.fig .solo::before{content:"";width:12px;height:12px;background:currentColor;-webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0 0 14 8v8a4.5 4.5 0 0 0 2.5-4z'/%3E%3C/svg%3E") center/contain no-repeat;mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0 0 14 8v8a4.5 4.5 0 0 0 2.5-4z'/%3E%3C/svg%3E") center/contain no-repeat}
.card.playing .fig:not(.silent) .solo,.fig:hover .solo{opacity:1}
.fig.solo .solo{background:var(--accent);opacity:1}
.fig .badge{position:absolute;left:6px;top:6px;font:600 9.5px/1 JetBrains Mono,monospace;letter-spacing:.06em;text-transform:uppercase;padding:4px 6px;border-radius:5px;background:rgba(0,0,0,.55);color:#ddd;pointer-events:none}
.vwrap .st{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;opacity:0;transition:opacity .15s}
.vwrap .st::before{content:"";width:44px;height:44px;border-radius:50%;background:rgba(0,0,0,.5);backdrop-filter:blur(4px)}
.vwrap .st::after{content:"";position:absolute;width:0;height:0;border-left:14px solid #fff;border-top:9px solid transparent;border-bottom:9px solid transparent;margin-left:4px}
.vwrap:not(.on) .st{opacity:.85}
.vwrap .bar{position:absolute;left:0;right:0;bottom:0;height:3px;background:rgba(255,255,255,.18)}
.vwrap .bar i{display:block;height:100%;width:0;background:var(--accent2)}
figcaption{margin-top:6px;text-align:center;line-height:1.25}
figcaption .lbl{display:block;font-size:12.5px;font-weight:600}
.fig.ours figcaption .lbl{color:var(--ours)}
.fig.ref figcaption .lbl{color:var(--ref)}
figcaption .sub{display:block;font-size:11px;color:var(--fg3);margin-top:2px}
.fig.au audio{width:100%;height:36px;display:block;border-radius:8px}
.why{margin:12px 0 0;padding:10px 12px;border-radius:10px;background:var(--fail-soft);color:var(--fg);font-size:12.5px;line-height:1.45;border-left:3px solid var(--fail)}
.why .who{display:inline-block;font:700 10px/1 JetBrains Mono,monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--fail);margin-right:8px;vertical-align:1px}
.empty{display:none;padding:40px;text-align:center;color:var(--fg3);border:1px dashed var(--line2);border-radius:var(--r)}
.sec.hide{display:none}
footer{border-top:1px solid var(--line);color:var(--fg3);font-size:12.5px;padding:24px 20px;text-align:center}
.totop{position:fixed;right:18px;bottom:18px;width:40px;height:40px;border-radius:12px;border:1px solid var(--line2);background:var(--bg2);box-shadow:var(--shadow);cursor:pointer;opacity:0;pointer-events:none;transition:opacity .2s;display:flex;align-items:center;justify-content:center;color:var(--fg2)}
.totop.on{opacity:1;pointer-events:auto}

@media (max-width:1100px){.grid.c6,.grid.c5{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:980px){.wrap{grid-template-columns:1fr;gap:0}aside.toc{display:none}.cards{grid-template-columns:1fr}.grid.c2{max-width:none}}
@media (max-width:640px){.hero .in{padding:36px 16px 28px}.wrap{padding:16px 16px 60px}.top .in{padding:0 12px;gap:8px}.topnav{display:none}.search input{width:150px}.grid.c4{grid-template-columns:repeat(2,minmax(0,1fr))}.grid.c6,.grid.c5,.grid.c3{grid-template-columns:repeat(3,minmax(0,1fr))}.card{padding:10px}.prompt{white-space:normal}.playall span{display:none}.playall{padding:0 8px}}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
</style>
</head>
<body>
<div class="top"><div class="in">
  <a class="brand" href="#top"><i></i>{{TITLE}}</a>
  <nav class="topnav">{{NAV}}</nav>
  <div class="sp"></div>
  <div class="search"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg><input id="q" type="search" placeholder="Filter by object or tag…" autocomplete="off" spellcheck="false"><span class="n" id="qn"></span></div>
  <button class="ib" id="theme" type="button" title="Toggle theme" aria-label="Toggle theme"><svg id="ic-sun" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4m11.4-11.4 1.4-1.4"/></svg></button>
  <a class="ib" href="{{REPO}}" target="_blank" rel="noopener" title="GitHub"><svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg><span>Code</span></a>
</div></div>

<header class="hero" id="top"><div class="in">
  <div class="kicker">Demo page · audio-visual editing</div>
  <h1 class="title">{{TITLE}}: <span>{{SUBTITLE}}</span></h1>
  <p class="lead">{{INTRO}}</p>
  <div class="stats">
    <div class="stat"><b>{{N_EX}}</b><span>examples</span></div>
    <div class="stat"><b>{{N_CLIP}}</b><span>clips on this page</span></div>
    <div class="stat"><b>24,444</b><span>training pairs</span></div>
    <div class="stat"><b>1,425</b><span>test pairs · 374 objects</span></div>
  </div>
  <div class="cta">
    <a class="btn pri" href="#best-results">See best results ↓</a>
    <a class="btn" href="#joint">Baseline comparisons</a>
    <a class="btn" href="#failures">Failure cases</a>
  </div>
  <div class="legend">
    <span class="pill"><span class="tag rm">R</span> removal</span>
    <span class="pill"><span class="tag add">A</span> addition</span>
    <span class="pill"><span class="tag data">D</span> dataset</span>
    <span class="pill"><span class="tag fail">F</span> failure</span>
    <span class="pill hint"><b>Play all</b>&nbsp;runs a card's clips in sync; the speaker button picks which clip's audio you hear.</span>
  </div>
</div></header>

<div class="wrap">
<aside class="toc"><h5>Contents</h5><ul>
{{TOC}}
</ul></aside>
<main>
{{BODY}}
<div class="empty" id="empty">No example matches this filter.</div>
</main>
</div>
<footer>All clips are 5 s, 256×256, 16 fps, from the held-out test set. Page generated from <code>index.md</code>.</footer>
<button class="totop" id="totop" type="button" aria-label="Back to top"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5m-7 7 7-7 7 7"/></svg></button>

<script>
(function(){
  // theme
  var root=document.documentElement, tb=document.getElementById('theme');
  try{var t=localStorage.getItem('avio-theme'); if(t) root.setAttribute('data-theme',t);}catch(e){}
  tb.addEventListener('click',function(){
    var dark=root.getAttribute('data-theme')==='dark' || (!root.getAttribute('data-theme') && matchMedia('(prefers-color-scheme:dark)').matches);
    var nt=dark?'light':'dark'; root.setAttribute('data-theme',nt);
    try{localStorage.setItem('avio-theme',nt);}catch(e){}
  });

  // lazy media: attach src only when near the viewport
  var lazy=[].slice.call(document.querySelectorAll('[data-src]'));
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){load(e.target);io.unobserve(e.target);}});},{rootMargin:'700px 0px'});
    lazy.forEach(function(m){io.observe(m);});
  }else{lazy.forEach(load);}
  function load(m){if(m.src)return; m.src=m.getAttribute('data-src'); m.preload='metadata'; m.removeAttribute('data-src');}

  // per-video: click toggles play; show play glyph + progress bar
  var current=null; // card currently in play-all mode
  document.querySelectorAll('.vwrap').forEach(function(w){
    var v=w.querySelector('video'); var st=document.createElement('div'); st.className='st'; w.appendChild(st);
    var bar=document.createElement('div'); bar.className='bar'; var bi=document.createElement('i'); bar.appendChild(bi); w.appendChild(bar);
    v.addEventListener('play',function(){w.classList.add('on');});
    v.addEventListener('pause',function(){w.classList.remove('on');});
    v.addEventListener('ended',function(){w.classList.remove('on');});
    v.addEventListener('timeupdate',function(){if(v.duration)bi.style.width=(v.currentTime/v.duration*100)+'%';});
    v.addEventListener('click',function(){
      var card=v.closest('.card');
      if(card.classList.contains('playing')){stopCard(card);return;}
      if(v.paused){ pauseAll(v); load(v); v.muted=v.hasAttribute('muted')&&v.defaultMuted; v.play().catch(function(){}); }
      else v.pause();
    });
  });
  document.querySelectorAll('video[muted]').forEach(function(v){v.defaultMuted=true;v.closest('.fig').classList.add('silent');});
  function pauseAll(except){document.querySelectorAll('video,audio').forEach(function(m){if(m!==except&&!m.paused)m.pause();});}

  // play-all with solo audio
  document.querySelectorAll('.card').forEach(function(card){
    var vids=[].slice.call(card.querySelectorAll('video')); if(!vids.length)return;
    var btn=card.querySelector('.playall');
    var figs=[].slice.call(card.querySelectorAll('.fig'));
    var solo=card.querySelector('.fig.ours:not(.silent)')||card.querySelector('.fig:not(.silent)');
    function setSolo(f){figs.forEach(function(x){x.classList.toggle('solo',x===f);}); solo=f;
      vids.forEach(function(v){v.muted=!(v.closest('.fig')===f)||v.defaultMuted;});}
    if(solo) figs.forEach(function(x){x.classList.toggle('solo',x===solo);});
    card.querySelectorAll('.solo').forEach(function(b){b.addEventListener('click',function(e){e.stopPropagation();setSolo(b.closest('.fig'));});});
    btn.addEventListener('click',function(){
      if(card.classList.contains('playing')){stopCard(card);return;}
      if(current&&current!==card)stopCard(current);
      pauseAll(); vids.forEach(load);
      card.classList.add('playing'); current=card;
      var ready=vids.map(function(v){return new Promise(function(res){ if(v.readyState>=2)return res(); v.addEventListener('loadeddata',res,{once:true}); v.addEventListener('error',res,{once:true}); setTimeout(res,4000); });});
      Promise.all(ready).then(function(){ if(!card.classList.contains('playing'))return;
        vids.forEach(function(v){v.currentTime=0; v.muted=!(v.closest('.fig')===solo)||v.defaultMuted;});
        vids.forEach(function(v){v.play().catch(function(){});});
      });
      var done=0; vids.forEach(function(v){v.addEventListener('ended',onEnd);});
      function onEnd(){ if(++done>=vids.length){ vids.forEach(function(v){v.removeEventListener('ended',onEnd);}); if(card.classList.contains('playing'))stopCard(card,true);} }
    });
    card._stop=function(keepFrame){ vids.forEach(function(v){ if(!v.paused)v.pause(); if(!keepFrame)v.currentTime=0; v.muted=v.defaultMuted||false; }); card.classList.remove('playing'); if(current===card)current=null; };
  });
  function stopCard(card,keepFrame){ if(card._stop)card._stop(keepFrame); }

  // filter
  var q=document.getElementById('q'), qn=document.getElementById('qn'), cards=[].slice.call(document.querySelectorAll('.card')), secs=[].slice.call(document.querySelectorAll('.sec')), empty=document.getElementById('empty');
  function filter(){
    var s=q.value.trim().toLowerCase(), n=0;
    cards.forEach(function(c){var ok=!s||c.getAttribute('data-search').indexOf(s)>=0; c.classList.toggle('hide',!ok); if(ok)n++;});
    secs.forEach(function(sec){ var any=sec.querySelector('.card:not(.hide)'); sec.classList.toggle('hide',!!s&&!any); });
    qn.textContent=s?n+'/'+cards.length:''; empty.style.display=(s&&!n)?'block':'none';
  }
  q.addEventListener('input',filter);
  document.addEventListener('keydown',function(e){ if(e.key==='/'&&document.activeElement!==q){e.preventDefault();q.focus();} if(e.key==='Escape'&&document.activeElement===q){q.value='';filter();q.blur();} });

  // scroll spy + back to top
  var links=[].slice.call(document.querySelectorAll('.toc a, .topnav a')); var byId={};
  links.forEach(function(a){var id=a.getAttribute('href').slice(1);(byId[id]=byId[id]||[]).push(a);});
  var heads=[].slice.call(document.querySelectorAll('.sec')); var totop=document.getElementById('totop');
  function spy(){
    var y=window.scrollY+90, cur=null, top1=null;
    heads.forEach(function(h){ if(h.classList.contains('hide'))return; if(h.offsetTop<=y){cur=h.id; if(h.classList.contains('l1'))top1=h.id;} });
    links.forEach(function(a){a.classList.remove('on');});
    if(cur&&byId[cur])byId[cur].forEach(function(a){if(a.closest('.toc'))a.classList.add('on');});
    if(top1&&byId[top1])byId[top1].forEach(function(a){if(a.closest('.topnav'))a.classList.add('on');});
    if(cur){var on=document.querySelector('.toc a.on'); if(on){var r=on.getBoundingClientRect(), tr=on.closest('aside').getBoundingClientRect(); if(r.top<tr.top||r.bottom>tr.bottom)on.scrollIntoView({block:'nearest'});}}
    totop.classList.toggle('on',window.scrollY>600);
  }
  window.addEventListener('scroll',spy,{passive:true}); window.addEventListener('resize',spy); spy();
  totop.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'});});
})();
</script>
</body>
</html>
"""


def main():
    intro, nodes = parse(SRC.read_text(encoding="utf-8"))
    n_ex = sum(1 for n in nodes if n["kind"] == "ex")
    n_fig = sum(len(n["figs"]) for n in nodes if n["kind"] == "ex")
    missing = [f["src"] for n in nodes if n["kind"] == "ex" for f in n["figs"] if not (ROOT / f["src"]).is_file()]
    OUT.write_text(render(intro, nodes), encoding="utf-8")
    print(f"headings={sum(1 for n in nodes if n['kind']=='h')} examples={n_ex} media={n_fig} missing={len(missing)} -> {OUT.name} ({OUT.stat().st_size/1024:.0f} KB)")
    if missing:
        print("\n".join(missing), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
