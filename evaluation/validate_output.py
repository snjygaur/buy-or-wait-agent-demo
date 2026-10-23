#!/usr/bin/env python3
"""Validate output.csv against the public output contract."""
from pathlib import Path
import pandas as pd, re

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"dataset"
OUT=ROOT/"output.csv"
EXPECTED=["request_id","amount_safe_to_pay","affordability_status",
          "recommended_payment_method","payment_plan",
          "earliest_date_for_full_payment","spending_changes_needed",
          "decision_explanation"]
S={"affordable_now","affordable_with_plan","affordable_later","not_affordable"}
M={"full_payment","partial_payment","installments","wait","not_recommended"}

def main():
    req=pd.read_csv(DATA/"requests.csv"); out=pd.read_csv(OUT)
    assert out.columns.tolist()==EXPECTED
    assert len(out)==len(req)==250
    assert out.request_id.nunique()==len(req)
    reqi=req.set_index("request_id")
    for _,r in out.iterrows():
        q=reqi.loc[r.request_id]
        a=float(r.amount_safe_to_pay); wanted=float(q.requested_amount)
        assert 0<=a<=wanted
        assert r.affordability_status in S
        assert r.recommended_payment_method in M
        assert str(r.payment_plan)=="none" or all(re.fullmatch(r"\d{4}-\d{2}-\d{2}:\d+(?:\.\d+)?",x) for x in str(r.payment_plan).split("|"))
        if r.recommended_payment_method=="partial_payment":
            p=str(r.payment_plan).split("|")
            assert len(p)==2
            assert abs(float(p[0].split(":")[1])-a)<0.011
            assert abs(sum(float(x.split(":")[1]) for x in p)-wanted)<0.011
    print("VALID:",len(out),"rows; schema and core plan constraints pass.")

if __name__=="__main__":
    main()
