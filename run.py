# run.py — 깃허브 자동 실행용 감싸개 (Mr.Red 하네스, 조정 운영 체계 0절 44·45번)
# dial_core.py(다이얼 계산 원본)를 돌려 결과를 dial.json에 쓰고, dial_history.csv에 하루 한 줄 쌓는다.
# 비중 한도가 직전 기록보다 20%p 넘게 떨어지면 "줄임" 표시(늘림은 금요일 종가 뒤에만).
import subprocess, json, csv, os, sys
cmd = [sys.executable, "dial_core.py"]
if os.path.exists("holdings.json"):
    cmd += ["--pos", "holdings.json"]
if os.environ.get("FORCE") == "1":
    cmd += ["--force"]
p = subprocess.run(cmd, capture_output=True, text=True)
txt = p.stdout
line = next((l[len("알림줄: "):] for l in txt.splitlines() if l.startswith("알림줄: ")), None)
if p.returncode != 0 or line is None:
    out = {"상태": "계산 실패", "알림줄": "다이얼: 계산 실패(깃허브 실행 오류)", "오류": p.stderr[-1500:]}
    json.dump(out, open("dial.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sys.exit(0)
data = json.JSONDecoder().raw_decode(txt[txt.index("{"):])[0]
data["알림줄"] = line
hist = "dial_history.csv"
prev = {}
if os.path.exists(hist):
    rows = list(csv.DictReader(open(hist, encoding="utf-8")))
    for r in rows:
        prev[r["티커"]] = r
if data.get("상태") == "계산":
    cuts = []
    new = not os.path.exists(hist)
    with open(hist, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["날짜", "티커", "종가", "추세", "30주선_괴리%", "20일변동성%", "다이얼%", "비중한도%", "손절_닿음"])
        for t, r in data["결과"].items():
            if "다이얼%" not in r:
                continue
            if prev.get(t, {}).get("날짜") == r["종가일"]:
                continue  # 같은 날 두 번 쌓지 않음
            old = prev.get(t, {}).get("비중한도%")
            if old not in (None, "") and float(old) - r["비중한도%"] > 20:
                cuts.append(t)
            w.writerow([r["종가일"], t, r["종가"], r["추세"], r["30주선_괴리%"], r["20일변동성%"],
                        r["다이얼%"], r["비중한도%"], r.get("병조", {}).get("손절_닿음", "")])
    if cuts:
        data["알림줄"] += " · 줄임 신호: " + ", ".join(cuts)
q = subprocess.run([sys.executable, "paper.py"], capture_output=True, text=True)
pl = next((l for l in q.stdout.splitlines() if l.startswith("장부: ")), None)
data["장부"] = pl or "장부: 계산 실패"
json.dump(data, open("dial.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
# 페이지 자료에 오늘 다이얼 줄과 갱신 시각을 붙인다
import datetime as _dt
if os.path.exists("docs/data.json"):
    s = json.load(open("docs/data.json", encoding="utf-8"))
    s["다이얼줄"] = data.get("알림줄", "")
    # 지금 상황 해석(Mr.Red 261124): 그날 숫자로 네 줄을 새로 짓는다. 실패해도 나머지는 돈다.
    try:
        import interp
        _p = json.load(open("paper.json", encoding="utf-8"))
        s["해석"] = interp.build(data, _p)
        s["경고등"] = interp.stop_line(_p)
    except Exception as e:
        s["해석"] = [{"제목": "지금 상태", "글": f"해석을 만들지 못했다({type(e).__name__})."}]
        s["경고등"] = ""
    s["갱신"] = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M (한국)")
    json.dump(s, open("docs/data.json", "w", encoding="utf-8"), ensure_ascii=False)
print(data["알림줄"]); print(data["장부"])
