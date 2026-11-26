# interp.py — 매일 보기 페이지의 「지금 상황 해석」 (Mr.Red 261124, 조정 운영 체계 0절 44번 ③-1)
# dial.json(오늘 다이얼)과 paper.json(2번·4번 장부)으로 그날 숫자에 맞는 해석 네 줄을 만든다.
# 손으로 쓴 글을 박아 두면 다음 날 틀린 말이 되므로, 문장은 매일 숫자로 새로 짓는다.
import json

M2 = "올인/털기(추세만: 30주선 위 100%·아래 0%)"
M4 = "추세×변동성(지금 다이얼)"
STOP = {M2: -49.0, M4: -42.0}           # 중단 규칙 = 백테스트 최악 낙폭(261123 투자 모델 제안, SOXX)
LATE_COST = "SOXX 연 −3.5%p"            # 추세 모델이 늦게 타는 비용(같은 문서, 보유 대비 연수익 차이)
SYNC = 5                                # 실제와 목표 차이가 이 %p 안이면 '같아짐'


def build(dial, paper):
    res = dial.get("결과", {})
    ps = paper.get("방식", {})
    if not res or M2 not in ps or M4 not in ps:
        return [{"제목": "지금 상태", "글": "오늘 숫자를 못 읽어 해석을 만들지 못했다."}]
    held = [t for t, r in res.items() if "배분" in r]
    e2, e4 = ps[M2]["노출%"], ps[M4]["노출%"]
    tgt = {t: round((e2.get(t, 0) + e4.get(t, 0)) / 2) for t in held}
    cur = {t: round(res[t]["배분"]["지금%"]) for t in held}
    day = res[held[0]]["종가일"] if held else dial.get("마지막_봉", "")

    # 1. 지금 상태
    dials = " · ".join(f"{t} {r['다이얼%']}%" for t, r in res.items() if "다이얼%" in r)
    gap = " · ".join(f"{t} {tgt[t]}%(지금 {cur[t]}%)" for t in held)
    out = [{"제목": "지금 상태", "글": f"다이얼 {dials} ({day} 종가). 규칙 ③-1 목표 비중(2번·4번 평균): {gap}."}]

    # 2. 다시 열리는 조건
    cond = []
    for t in ["QQQ"] + held:
        r = res.get(t)
        if not r or "30주선" not in r:
            continue
        if r["추세"] == 0:
            need = (r["30주선"] / r["종가"] - 1) * 100
            cond.append(f"{t}: 금요일 종가가 30주선 ${r['30주선']:,.2f} 위로 올라와야 열린다(지금 ${r['종가']:,.2f}에서 +{need:.1f}%).")
        else:
            cond.append(f"{t}: 30주선 위({r['30주선_괴리%']:+.1f}%). 다이얼 {r['다이얼%']}%는 변동성({r['20일변동성%']}%)이 정한다.")
    out.append({"제목": "다시 열리는 조건", "글": " ".join(cond) + " 30주선은 매주 조금씩 움직인다."})

    # 3. 할 일 (규칙 44번 ③-1, Mr.Red 261127 기준일 수정)
    t0 = held[0] if held else "SOXX"
    r0 = res.get(t0, {})
    if r0.get("추세") == 0:
        act = (f"놓친 줄임은 뒤늦게 쫓지 않는다(③-1). 기준일 = {t0} 금요일 종가가 30주선(지금 ${r0.get('30주선', 0):,.2f}) 위로 올라와 "
               f"추세 칸이 다시 켜진 첫 금요일. 그날 실제 비중을 그 주 목표 비중(2번·4번 평균)에 맞추고, 그 뒤부터 액션을 그대로 따른다. "
               "다이얼이 닫힌 동안 '지금이 살 때' 같은 글이나 반등을 보면 규칙을 깨고 싶어지는데, 그것이 이 모델의 가장 큰 약점이다. "
               f"늦게 타는 비용은 백테스트에서 이미 계산한 값({LATE_COST})이다. 지금 할 일은 없다.")
    else:
        g = " · ".join(f"{t} {tgt[t]}%" for t in held)
        act = (f"{t0} 추세 칸이 켜져 있다. 켜진 첫 금요일이 기준일이면 그날 실제 비중을 목표({g})에 맞추고, 이미 맞췄다면 2번·4번 액션을 그대로 따른다. "
               "늘림은 금요일 종가 뒤에만, 주문은 Mr.Red가 한다.")
    out.append({"제목": "할 일", "글": act})
    return out


def stop_line(paper):
    """2번·4번 카드 위에 두는 '고장 경고등' 한 문단(Mr.Red 261124: 쉬운 말로)."""
    ps = paper.get("방식", {})
    if M2 not in ps or M4 not in ps:
        return "고장 경고등: 오늘 장부를 못 읽었다."
    parts, broke = [], []
    for m, name in ((M4, "4번"), (M2, "2번")):
        dd, lim = ps[m]["최대낙폭%"], STOP[m]
        if dd <= lim:
            broke.append(name)
            parts.append(f"{name}은 지금까지 최악 {dd:.1f}%로 과거 20년 최악({lim:.0f}%)을 넘었다")
        else:
            parts.append(f"{name}은 지금까지 최악 {dd:.1f}%, 과거 20년 최악({lim:.0f}%)까지 {dd - lim:.1f}%p 남음")
    verdict = (f"→ {'·'.join(broke)}은 멈추고 다시 검토(규칙 ③-1)." if broke else "→ 둘 다 정상.")
    return ("고장 경고등: " + " · ".join(parts) + f" {verdict} "
            "과거 최악(2008 금융위기 포함)보다 더 깨지면 이 방식이 더는 안 통한다는 뜻이라 따르지 않고 멈춘다. "
            "한 달에 한 번 실제 성적을 백테스트와 견준다.")


if __name__ == "__main__":
    d = json.load(open("dial.json", encoding="utf-8"))
    p = json.load(open("paper.json", encoding="utf-8"))
    for x in build(d, p):
        print(f"{x['제목']}: {x['글']}")
    print(stop_line(p))
