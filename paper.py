# paper.py — 가상 장부 (Mr.Red 261123): 네 가지 노출 방식을 같은 날부터 나란히 돌려 비교한다.
# 매번 시세로 처음부터 다시 계산한다(저장 상태 없음 → 하루 빠져도 틀어지지 않음).
# 방식 이름은 줄이지 않고 다 쓴다(Mr.Red 261123).
# 배분: holdings.json의 weight(주식 자금 중 비율). 남는 몫은 현금(수익 0).
# 신호는 그날 종가로 정하고 다음 거래일부터 적용, 비중 변화 1회당 비용 0.1%.
import json, numpy as np, pandas as pd, yfinance as yf
START = "2026-11-20"   # 장부 시작 기준일(이 날 종가에서 출발)
hold = json.load(open("holdings.json", encoding="utf-8"))
alloc = {t: float(v.get("weight", 0)) / 100 for t, v in hold.items() if v.get("weight")}
tick = list(alloc)
px = yf.download(tick, period="3y", auto_adjust=True, progress=False)["Close"]
if isinstance(px, pd.Series):
    px = px.to_frame(tick[0])
px = px.dropna()
def weights(p):
    r = p.pct_change()
    wk = p.resample("W-FRI").last(); sma = wk.rolling(30).mean()
    tr = (wk > sma).astype(float).reindex(p.index, method="ffill").fillna(0)
    vm = (0.30 / (r.rolling(20).std() * np.sqrt(252))).clip(upper=1).fillna(0)
    return {"보유(지금 그대로, 항상 100%)": pd.Series(1.0, index=p.index), "올인/털기(추세만: 30주선 위 100%·아래 0%)": tr, "변동성만 조절(30%÷20일 변동성)": vm, "추세×변동성(지금 다이얼)": tr * vm}
W = {t: weights(px[t]) for t in tick}
out = {"시작": START, "기준일": str(px.index[-1].date()), "배분%": {t: alloc[t] * 100 for t in tick}, "방식": {}}
for m in ["보유(지금 그대로, 항상 100%)", "올인/털기(추세만: 30주선 위 100%·아래 0%)", "변동성만 조절(30%÷20일 변동성)", "추세×변동성(지금 다이얼)"]:
    wt = pd.DataFrame({t: W[t][m] * alloc[t] for t in tick})          # 포트폴리오 안 실제 노출
    r = px.pct_change().fillna(0)
    held = wt.shift(1).fillna(0)
    cost = wt.diff().abs().sum(axis=1).fillna(0) * 0.001
    d = (held * r).sum(axis=1) - cost
    d = d[d.index > START]
    eq = (1 + d).cumprod() if len(d) else pd.Series([1.0])
    out["방식"][m] = {"오늘 노출%": {t: round(float(wt[t].iloc[-1]) * 100) for t in tick},
                    "현금%": round(100 - float(wt.iloc[-1].sum()) * 100),
                    "누적%": round((float(eq.iloc[-1]) - 1) * 100, 2),
                    "최대낙폭%": round(float((eq / eq.cummax() - 1).min()) * 100, 2),
                    "거래일": int(len(d))}
json.dump(out, open("paper.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
# 기록: 하루 한 줄씩 방식별 누적
import csv, os
f = "paper_history.csv"; new = not os.path.exists(f)
rows = list(csv.reader(open(f, encoding="utf-8"))) if not new else []
if not any(len(x) > 0 and x[0] == out["기준일"] for x in rows):
    with open(f, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["날짜", "방식", "누적%", "최대낙폭%", "현금%"] + [f"{t} 노출%" for t in tick])
        for m, v in out["방식"].items():
            w.writerow([out["기준일"], m, v["누적%"], v["최대낙폭%"], v["현금%"]] + [v["오늘 노출%"][t] for t in tick])
print("장부: " + " · ".join(f"{m} {v['누적%']:+.1f}%" for m, v in out["방식"].items()))
