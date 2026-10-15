from app.matching import solve, fairness_cost

def test_global_assignment_is_not_row_greedy():
    pairs,total=solve([[1,2],[1.1,100]])
    assert pairs==[(0,1),(1,0)]
    assert total==3.1

def test_fairness_reward_lowers_waiting_remote_cost():
    w={'distance':1,'priority':0,'skill':0,'reliability':0,'starvation':2,'zone_service':1,'expiry':0}
    remote_waiter=fairness_cost(40000,0,0,0,1,0,0,w)
    local_served=fairness_cost(1000,0,0,0,0,1,0,w)
    assert remote_waiter < local_served
