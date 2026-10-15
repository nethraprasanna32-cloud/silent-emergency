"""Batch assignment solver. Candidate feature extraction stays in SQL; SciPy solves the matrix."""
import numpy as np
from scipy.optimize import linear_sum_assignment

def solve(costs):
    """Return (row, column) assignments and total cost; rows/columns with infinite cost are skipped."""
    if not costs or not costs[0]: return [], 0.0
    matrix=np.asarray(costs,dtype=float)
    if matrix.ndim!=2: raise ValueError('cost matrix must be rectangular')
    finite=matrix[np.isfinite(matrix)]
    if finite.size==0: return [], 0.0
    sentinel=float(finite.max()+max(1,abs(finite.max()))*1000)
    rows,cols=linear_sum_assignment(np.where(np.isfinite(matrix),matrix,sentinel))
    pairs=[(int(i),int(j)) for i,j in zip(rows,cols) if np.isfinite(matrix[i,j])]
    return pairs,float(sum(matrix[i,j] for i,j in pairs))

def fairness_cost(distance_m, priority, skill_hits, reliability, starvation, zone_service, expiry_urgency, weights):
    """Lower is better. Remote waiting and expiring stock reduce cost; over-served zones add cost."""
    return (weights['distance']*distance_m/50000 - weights['priority']*priority/100
            - weights['skill']*min(skill_hits,3)/3 - weights['reliability']*reliability
            - weights['starvation']*starvation + weights['zone_service']*zone_service
            - weights['expiry']*expiry_urgency)
