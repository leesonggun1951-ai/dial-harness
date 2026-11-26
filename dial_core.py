# 다이얼 계산.py  v261123a  (조정 운영 체계 0절 44번, 평시서·병조 담당)
# 쓰는 법: python3 "다이얼 계산.py" [추가 티커 ...] [--pos 보유.json] [--force]
#   - 기본 대상: QQQ(시장), SOXX(반도체). 추가 티커는 뒤에 적는다(261127 Mr.Red: 개별주 안 함, MU 뺌).
#   - --pos: {"MU": {"entry": 600.0}} 형식(진입가). 있으면 병조가 손절가·닿음을 본다.
#   - --force: 미국 휴장일이어도 계산한다(시험용).
# 출력: 맨 끝에 JSON 한 덩어리 + "알림줄:" 한 줄. 아침 작업은 알림줄을 그대로 쓴다(고쳐 쓰지 않는다 = 훅).
# 규칙: 다이얼 = 추세(금요일 주봉 종가 > 30주선 ? 1 : 0) × min(1, 30% ÷ 최근 20거래일 변동성)
#       종목 비중 한도 = min(QQQ 다이얼, 종목 다이얼)
#       비중을 줄이는 판단만 매일(한도가 직전 기록보다 20%p 넘게 낮으면 "줄임"), 늘리는 판단은 금요일 종가 뒤에만.
#       손절 = 진입가 × (1 − 7.5%), 한 번에 거는 손실 1.5% → 종목 비중 최대 20%.
import sys, json, datetime as dt
import numpy as np, pandas as pd, yfinance as yf
from zoneinfo import ZoneInfo

VER = "v261123d"
TARGET_VOL, SMA_WEEKS, VOL_DAYS = 0.30, 30, 20
STOP, RISK = 0.075, 0.015

args = [a for a in sys.argv[1:]]
force = "--force" in args
pos = {}
if "--pos" in args:
    p = args[args.index("--pos") + 1]
    pos = json.load(open(p, encoding="utf-8"))
    args = [a for a in args if a not in ("--pos", p)]
args = [a for a in args if a != "--force"]
tickers = ["QQQ", "SOXX"] + [t.upper() for t in args if t.upper() not in ("QQQ", "SOXX")]
tickers += [t for t in pos if t not in tickers]

raw = yf.download(tickers, period="2y", auto_adjust=True, progress=False)["Close"]
if isinstance(raw, pd.Series):
    raw = raw.to_frame(tickers[0])
# 깃허브 서버에서는 한꺼번에 받을 때 일부 티커가 비는 일이 있어 비었으면 하나씩 다시 받는다(최대 3번).
import time
for t in tickers:
    for _ in range(3):
        if t in raw and raw[t].dropna().shape[0] >= 200:
            break
        time.sleep(5)
        try:
            h = yf.Ticker(t).history(period="2y", auto_adjust=True)["Close"]
            h.index = h.index.tz_localize(None)
            raw = raw.drop(columns=[t], errors="ignore").join(h.rename(t), how="outer")
        except Exception:
            pass
last_bar = raw.dropna(how="all").index[-1].date()
et_today = dt.datetime.now(ZoneInfo("America/New_York")).date()
# 한국 아침(미국 전날 저녁)에 돌면 et_today = 방금 끝난 미국 거래일. 그날 봉이 없으면 휴장.
open_yesterday = (last_bar == et_today)
if not open_yesterday and not force:
    out = {"버전": VER, "상태": "휴장", "마지막_봉": str(last_bar), "미국_날짜": str(et_today)}
    print(json.dumps(out, ensure_ascii=False))
    print(f"알림줄: 미국 휴장({et_today}) → 다이얼 점검 쉼(마지막 종가 {last_bar})")
    sys.exit(0)

res = {}
for t in tickers:
    px = raw[t].dropna()
    if len(px) < 200:
        res[t] = {"오류": "자료 부족"}; continue
    wk = px.resample("W-FRI").last()
    # 추세는 마지막으로 끝난 금요일 기준(이번 주가 끝나지 않았으면 지난주 금요일)
    done = wk.index[wk.index <= px.index[-1]]
    last_fri = done[-1]
    sma = wk.rolling(SMA_WEEKS).mean()
    wclose, wsma = float(wk.loc[last_fri]), float(sma.loc[last_fri])
    trend = 1 if wclose > wsma else 0
    vol = float(px.pct_change().tail(VOL_DAYS).std() * np.sqrt(252))
    vmult = min(1.0, TARGET_VOL / vol) if vol > 0 else 1.0
    res[t] = {"종가": round(float(px.iloc[-1]), 2), "종가일": str(px.index[-1].date()),
              "추세_기준일": str(last_fri.date()), "주봉종가": round(wclose, 2), "30주선": round(wsma, 2),
              "30주선_괴리%": round((wclose / wsma - 1) * 100, 1), "추세": trend,
              "20일변동성%": round(vol * 100, 1), "변동성배수": round(vmult, 2),
              "다이얼%": round(trend * vmult * 100)}

mkt = res.get("QQQ", {}).get("다이얼%")
mkt_missing = mkt is None
if mkt_missing:
    mkt = 0  # 시장 다이얼을 못 구하면 보수적으로 0, 알림줄에 표시
for t, r in res.items():
    if "다이얼%" in r:
        r["비중한도%"] = min(mkt, r["다이얼%"]) if t != "QQQ" else mkt
        if t in pos and pos[t].get("entry"):
            e = float(pos[t]["entry"])
            if pos[t].get("weight") is not None:
                cur = float(pos[t]["weight"]); tgt = round(cur * r["비중한도%"] / 100)
                r["배분"] = {"지금%": cur, "모델%": tgt, "차이%p": round(tgt - cur)}
            if pos[t].get("kind") == "장기":
                # 장기 보유분: 손절 없음, 다이얼과 진입 대비 %만 (Mr.Red 261123, 0절 44번 ③)
                r["병조"] = {"구분": "장기", "진입가": e, "진입대비%": round((r["종가"] / e - 1) * 100, 1)}
            else:
                sl = round(e * (1 - STOP), 2)
                r["병조"] = {"구분": "공격", "진입가": e, "손절가": sl, "손절_닿음": r["종가"] <= sl,
                            "최대비중%": round(RISK / STOP * 100), "진입대비%": round((r["종가"] / e - 1) * 100, 1)}

is_fri_close = pd.Timestamp(last_bar).weekday() == 4
out = {"버전": VER, "상태": "계산", "마지막_봉": str(last_bar), "금요일_종가_반영": is_fri_close,
       "규칙": "추세×변동성, 줄임은 매일·늘림은 금요일 종가 뒤", "결과": res}
print(json.dumps(out, ensure_ascii=False, indent=1))
parts = [f"{t} {r['다이얼%']}%" for t, r in res.items() if "다이얼%" in r]
stops = [t for t, r in res.items() if r.get("병조", {}).get("손절_닿음")]
line = "다이얼 " + " · ".join(parts) + f" ({last_bar} 종가" + (", 추세 갱신" if is_fri_close else "") + ")"
alloc = [f"{t} {r['배분']['모델%']}%(지금 {r['배분']['지금%']:.0f}%)" for t, r in res.items() if "배분" in r]
if alloc:
    line += " · 모델 비중 " + ", ".join(alloc) + " [참고]"
if stops:
    line += " · 손절가 닿음: " + ", ".join(stops)
miss = [t for t, r in res.items() if "오류" in r]
if miss:
    line += " · 못 받음: " + ", ".join(miss) + (" (시장 다이얼 없음 → 한도 0으로 봄)" if mkt_missing else "")
print("알림줄: " + line)
