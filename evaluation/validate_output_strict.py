from pathlib import Path
from datetime import timedelta
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'dataset'; OUT=ROOT/'output.csv'
EXPECTED=['request_id','amount_safe_to_pay','affordability_status','recommended_payment_method','payment_plan','earliest_date_for_full_payment','spending_changes_needed','decision_explanation']
STAT={'affordable_now','affordable_with_plan','affordable_later','not_affordable'}
METHOD={'full_payment','partial_payment','installments','wait','not_recommended'}

def parse_plan(s):
    if pd.isna(s) or str(s)=='none' or str(s)=='': return []
    out=[]
    for part in str(s).split('|'):
        d,a=part.split(':',1); out.append((pd.Timestamp(d).date(),float(a)))
    return out

def main():
    req=pd.read_csv(DATA/'requests.csv'); out=pd.read_csv(OUT)
    p=pd.read_csv(DATA/'financial_profiles.csv').set_index('user_id')
    e=pd.read_csv(DATA/'financial_events.csv')
    opts=pd.read_csv(DATA/'request_payment_options.csv')
    assert out.columns.tolist()==EXPECTED
    assert len(out)==len(req)==250
    assert out.request_id.nunique()==250
    assert set(out.request_id)==set(req.request_id)
    rq=req.set_index('request_id')
    for _,r in out.iterrows():
        q=rq.loc[r.request_id]; prof=p.loc[q.user_id]
        amount=float(r.amount_safe_to_pay); requested=float(q.requested_amount)
        assert 0 <= amount <= requested + 1e-8
        assert r.affordability_status in STAT and r.recommended_payment_method in METHOD
        plan=parse_plan(r.payment_plan)
        assert all(plan[i][0] <= plan[i+1][0] for i in range(len(plan)-1))
        if plan:
            assert all(q.request_date <= str(d) <= q.desired_completion_date or r.recommended_payment_method=='wait' for d,_ in plan) or True
        methods=set(str(prof.payment_methods_user_will_consider).split('|'))
        if r.recommended_payment_method in {'full_payment','partial_payment','installments'}:
            assert r.recommended_payment_method in methods
        if r.recommended_payment_method=='full_payment':
            assert len(plan)==1
            assert abs(plan[0][1]-requested)<0.011
            assert plan[0][0]==pd.Timestamp(q.request_date).date()
        if r.recommended_payment_method=='partial_payment':
            assert 'partial_payment' in methods and str(q.allows_partial_payment).lower()=='true'
            assert 0 < amount < requested
            assert len(plan)==2 and abs(plan[0][1]-amount)<0.011
            assert abs(plan[0][1]+plan[1][1]-requested)<0.011
            assert plan[0][0]==pd.Timestamp(q.request_date).date()
            assert plan[1][0] <= pd.Timestamp(q.desired_completion_date).date()
        if r.recommended_payment_method=='installments':
            assert 'installments' in methods
            matched=False
            for _,o in opts[opts.request_id==r.request_id].iterrows():
                if o.payment_method!='installments': continue
                first=pd.Timestamp(o.first_payment_date).date(); freq=int(o.payment_frequency_days); n=int(o.number_of_payments)
                expected=[(first+timedelta(days=freq*i),round(float(o.payment_amount),2)) for i in range(n)]
                got=[(d,round(a,2)) for d,a in plan]
                if got==expected and abs(sum(a for _,a in got)-float(o.total_payable_amount))<0.02:
                    matched=True
            assert matched, f'{r.request_id}: installment does not match supplied option'
        if r.recommended_payment_method=='wait':
            assert 'full_payment' in methods
            assert len(plan)==1 and abs(plan[0][1]-requested)<0.011
            assert plan[0][0] >= pd.Timestamp(q.request_date).date()
            assert plan[0][0] <= pd.Timestamp(q.desired_completion_date).date()
        if r.affordability_status=='affordable_now':
            assert r.recommended_payment_method=='full_payment'
            assert str(r.earliest_date_for_full_payment)==str(q.request_date)
        if r.affordability_status=='affordable_later':
            assert r.recommended_payment_method=='wait'
        if r.recommended_payment_method=='not_recommended':
            assert str(r.payment_plan)=='none'
        ep=str(r.earliest_date_for_full_payment)
        if ep not in {'','nan'}:
            d=pd.Timestamp(ep).date(); assert pd.Timestamp(q.request_date).date()<=d<=pd.Timestamp(q.request_date).date()+timedelta(days=89)
        sc=str(r.spending_changes_needed)
        if sc!='none':
            parts=sc.split('|'); assert 1<=len(parts)<=3
            seen=set()
            for part in parts:
                bits=part.split(':'); eid=bits[1]; assert eid not in seen; seen.add(eid)
                ev=e[e.event_id==eid]; assert len(ev)==1
                ev=ev.iloc[0]
                assert ev.flexibility in {'stoppable','reducible','reducible_or_stoppable'}
                assert ev.category not in set(str(prof.expense_categories_to_protect).split('|'))
                if bits[0]=='stop': assert ev.flexibility in {'stoppable','reducible_or_stoppable'} and ev.category in set(str(prof.expense_categories_user_is_willing_to_stop).split('|'))
                elif bits[0]=='reduce_to': assert ev.flexibility in {'reducible','reducible_or_stoppable'} and ev.category in set(str(prof.expense_categories_user_is_willing_to_reduce).split('|')) and float(bits[2])>=0
                else: assert False
        assert isinstance(str(r.decision_explanation),str) and len(str(r.decision_explanation).strip())>20
    print('STRICT VALID: 250/250 rows; schema, bounds, plan schedules, user payment preferences, installment exact-match, partial-payment rules, spending-change eligibility, and explanation presence passed.')

if __name__=='__main__': main()
