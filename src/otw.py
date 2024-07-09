import numpy as np


def find_key(d, k):
    if k in d:
        return d[k]
    else:
        return None


class OTW(object):
    def __init__(self, ref, params):
        """Implements Online Time Warping [1]. Algorithm adopted to work in python
        as a streaming algorithm, and includes a few modifications for clarity.

        - ref: set of features (assumed chroma) as the reference time series
        - params: parameters dict with config variables.

        [1] Simon Dixon Live Tracking of Musical Performances Using On-Line Tine Warping.
        """

        super(OTW, self).__init__()

        self.ref = ref  # ref sequence
        f_len, ref_len = self.ref.shape
        self.live = np.zeros((f_len, ref_len * 4), dtype=np.float32)  # live sequence
        self.D = np.full(
            (ref_len, ref_len * 4), np.inf, dtype=np.float32
        )  # accumulated cost matrix

        self.t = -1  # index into live sequence
        self.j = 0  # index into ref sequence
        self.previous = "---"  # 'ref' | 'live' | 'both'
        self.run_count = 1  # to check against max_run_count

        self.c = params["c"]
        self.max_run_count = params["max_run_count"]
        self.diag_weight = params["diag_weight"]

        self.last_j = 0

        # debugging
        self.path_z = []  # chosen path, but could go backwards

    def insert(self, live):
        """Add a new item representing the real-time input at this moment.

        - live: the live input as a chroma vector
        returns: estimate of current position in the reference time series.
        """

        # always start by inserting the new live data sample
        self.t += 1
        self.live[:, self.t] = live
        #         print('  new live', self.j, self.t)

        for k in range(max(0, self.j - self.c + 1), self.j + 1):
            self.eval_path_cost(k, self.t)

        path = []  # the new path points generated by this call. Could be more than 1
        while True:
            inc, path_pt = self.get_inc()
            path.append(path_pt)

            #             print(f'loop at:({self.j},{self.t}). best:({path_pt[0]}, {path_pt[1]}) prv:{self.previous} inc:{inc} rc:{self.run_count}')

            if (
                inc == "live"
            ):  # nothing more to do. Wait for next insert to get live sample
                break

            # increment j but keep it in bounds.
            self.j = min(self.j + 1, self.ref.shape[1] - 1)

            # calculate a new ref column
            for k in range(max(self.t - self.c + 1, 0), self.t + 1):
                self.eval_path_cost(self.j, k)
            #             print('  new ref', self.j, self.t)

            # if both: we just did a ref, so we need a live to follow.
            if inc == "both":
                break

        # simplest possible: get j of most recent point and don't go backwards:
        j = path[-1][0]
        self.path_z.append(j)
        if j < self.last_j:
            j = self.last_j
        self.last_j = j
        return j

    def get_inc(self):
        # Find the best location at the row & col definied by the current anchor point
        row = self.D[self.j, 0 : self.t + 1]
        col = self.D[0 : self.j + 1, self.t]
        best_t = np.argmin(row)
        best_j = np.argmin(col)

        if self.D[best_j, self.t] < self.D[self.j, best_t]:
            best_t = self.t
            inc = "live"
        else:
            best_j = self.j
            inc = "ref"

        if best_t == self.t and best_j == self.j:
            inc = "both"

        # now: (best_j, best_t) is the min-cost point along the outer edge

        # in the beginning, always run both ref and live
        if self.t < self.c:
            inc = "both"

        # if we've been on one axis for too long, switch
        if self.run_count >= self.max_run_count:
            if self.previous == "ref":
                inc = "live"
            else:
                inc = "ref"

        if inc == "both" or self.previous != inc:
            self.run_count = 1
        else:
            self.run_count += 1

        self.previous = inc

        # if there is no more ref data, then we can only
        # increment live.
        if self.j == self.ref.shape[1] - 1:
            inc = "live"

        return inc, (best_j, best_t)

    # run one DTW step to update accumulated cost at this cell
    def eval_path_cost(self, _j, _t):
        cost = 1 - np.dot(self.ref[:, _j], self.live[:, _t])

        # initial condition for accumulated cost at (0,0)
        if _j == 0 and _t == 0:
            self.D[_j, _t] = cost
            return

        steps = []
        bt = []  # backtrack index into otw.STEPS
        if _j > 0 and _t > 0:
            steps.append(self.D[_j - 1, _t - 1] + self.diag_weight * cost)
            bt.append(0)  # diagonal (-1, -1)
        if _j > 0:
            steps.append(self.D[_j - 1, _t] + cost)
            bt.append(1)  # left (-1, 0)
        if _t > 0:
            steps.append(self.D[_j, _t - 1] + cost)
            bt.append(2)  # down (0, -1)

        # store best step, and backtrack.
        self.D[_j, _t] = min(steps)

