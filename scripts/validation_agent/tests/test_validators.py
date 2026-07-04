from validators.val_acreage import AcreageFootingGate
from validators.val_interest import InterestConservationGate
from validators.val_chain import ChainContinuityGate

def test_acreage_catches_wrong_total():
    ctx = {"expected_acres":"637.42","tracts":[
        {"tract":1,"gross_acres":"80","owners":[{"net_acres":"80"}],"open_balance":"0"},
    ]}
    res = AcreageFootingGate().run(ctx)
    assert any(r["status"]=="FAIL" for r in res)  # 80 != 637.42

def test_acreage_pass_when_matches():
    ctx={"expected_acres":"120","tracts":[
        {"tract":1,"gross_acres":"80","owners":[{"net_acres":"80"}],"open_balance":"0"},
        {"tract":2,"gross_acres":"40","owners":[{"net_acres":"40"}],"open_balance":"0"},
    ]}
    res=AcreageFootingGate().run(ctx)
    assert any(r["status"]=="PASS" for r in res)
    assert not any(r["status"]=="FAIL" for r in res)

def test_interest_overconveyance_detected_exact():
    # 1/2 owned, conveys 3/4, retains 0 -> delta -1/4 overconveyance
    ctx={"tracts":[{"tract":1,"conveyances":[
        {"grantor":"X","interest_in":"1/2","conveyed":"3/4","retained":"0"}]}]}
    res=InterestConservationGate().run(ctx)
    assert any(r["failure_class"]=="Title Chain Gap" and r["status"]=="ESCALATE" for r in res)
    # never marked repairable
    assert all(not r["repairable"] for r in res)

def test_interest_conserves_exactly():
    ctx={"tracts":[{"tract":1,"conveyances":[
        {"grantor":"X","interest_in":"1/2","conveyed":"1/4","retained":"1/4"}]}]}
    res=InterestConservationGate().run(ctx)
    assert res[0]["status"]=="PASS"

def test_chain_escalates_missing_vesting():
    ctx={"tracts":[{"tract":1,"owners":[{"name":"Y","net_acres":"10","source_in":None}]}]}
    res=ChainContinuityGate().run(ctx)
    assert res[0]["status"]=="ESCALATE"
    assert res[0]["repairable"] is False
