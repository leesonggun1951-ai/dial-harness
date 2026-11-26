# paper.py — 가상 장부 + 매일 보는 페이지 자료 (Mr.Red 261123)
# 네 가지 노출 방식을 4/17부터(261127부터 SOXX 100%) 나란히 돌린다. 매번 시세로 처음부터 다시 계산(저장 상태 없음).
# 방식 이름은 줄이지 않고 다 쓴다. 배분 = holdings.json의 weight(주식 자금 중 %), 남는 몫은 현금(수익 0).
# 신호는 그날 종가로 정하고 다음 거래일부터 적용, 노출 변화 1회당 비용 0.1%. 매매 권유가 아닌 모델 기준 가상 기록.
import json, csv, os, numpy as np, pandas as pd, yfinance as yf
START = "2026-04-17"
NAMES = ["보유(지금 그대로, 항상 100%)", "올인/털기(추세만: 30주선 위 100%·아래 0%)",
         "변동성만 조절(30%÷20일 변동성)", "추세×변동성(지금 다이얼)"]
STEP = 5  # 가상 액션으로 적는 최소 변화(%p)
hold = json.load(open("holdings.json", encoding="utf-8"))
alloc = {t: float(v["weight"]) / 100 for t, v in hold.items() if v.get("weight")}
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
    return dict(zip(NAMES, [pd.Series(1.0, index=p.index), tr, vm, tr * vm]))
W = {t: weights(px[t]) for t in tick}
r = px.pct_change().fillna(0)
days = px.index[px.index >= START]
site = {"기준일": START, "마지막_종가일": str(px.index[-1].date()), "배분%": {t: round(alloc[t] * 100) for t in tick},
        "날짜": [str(d.date()) for d in days], "방식": []}
summary, hist_rows = {}, []
for m in NAMES:
    wt = pd.DataFrame({t: W[t][m] * alloc[t] for t in tick}).round(4)
    d = (wt.shift(1).fillna(0) * r).sum(axis=1) - wt.diff().abs().sum(axis=1).fillna(0) * 0.001
    d = d[d.index > START]
    eq = pd.concat([pd.Series([1.0], index=[pd.Timestamp(START)]), (1 + d).cumprod()])
    eq = eq[~eq.index.duplicated()].reindex(days).ffill()
    dd = eq / eq.cummax() - 1
    ex = (wt.reindex(days) * 100).round()
    # 가상 액션: 4/17 시작 노출에서 출발, 종목별로 직전 기록보다 STEP%p 이상 바뀌면 한 줄
    acts, last = [], {}
    for day in days:
        moves = []
        for t in tick:
            v = int(ex.loc[day, t])
            if t not in last:
                last[t] = v; continue
            if abs(v - last[t]) >= STEP or (v == 0) != (last[t] == 0):
                moves.append(f"{t} {last[t]}%→{v}% ({'늘림' if v > last[t] else '줄임'}, 종가 ${px.loc[day, t]:.2f})")
                last[t] = v
        if moves:
            acts.append({"날짜": str(day.date()), "내용": " · ".join(moves)})
    today = {t: int(ex.iloc[-1][t]) for t in tick}
    td_act = next((a["내용"] for a in acts if a["날짜"] == str(days[-1].date())), "변화 없음(그대로 유지)")
    item = {"이름": m, "누적%": [round((v - 1) * 100, 2) for v in eq],
            "오늘": {"누적%": round((eq.iloc[-1] - 1) * 100, 1), "최대낙폭%": round(dd.min() * 100, 1),
                    "노출%": today, "현금%": 100 - sum(today.values()), "오늘_액션": td_act,
                    "고점대비%": round(dd.iloc[-1] * 100, 1)},
            "시작_노출%": {t: int(ex.iloc[0][t]) for t in tick},
            "액션": acts[::-1]}
    site["방식"].append(item)
    summary[m] = item["오늘"]
    for i, day in enumerate(days):
        hist_rows.append([str(day.date()), m, item["누적%"][i], round(dd.iloc[i] * 100, 2),
                          100 - int(ex.loc[day].sum())] + [int(ex.loc[day, t]) for t in tick])
os.makedirs("docs", exist_ok=True)
json.dump(site, open("docs/data.json", "w", encoding="utf-8"), ensure_ascii=False)
json.dump({"시작": START, "기준일": site["마지막_종가일"], "방식": summary},
          open("paper.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
with open("paper_history.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["날짜", "방식", "누적%", "고점대비%", "현금%"] + [f"{t} 노출%" for t in tick])
    w.writerows(hist_rows)
print("장부: " + " · ".join(f"{m} {v['누적%']:+.1f}%" for m, v in summary.items()))
