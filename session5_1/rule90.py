from template import AbstractSimulation
from copy import deepcopy as cp

class ruleNinety(AbstractSimulation):
    '''
    Implementation: only for 2d

    Rules: If the current pattern is:      111 110 101 100 011 010 001 000
    then the new state for center cell is:  0   1   0   1   1   0   1   0

    '''
    def __init__(self, number_steps=9):
        super().__init__(number_steps)

        self.s = [0]*number_steps
        self.record = [[0]*number_steps]
        self.iter = 0
        self.lookup = {
            (1,1,1): 0,
            (1,1,0): 1,
            (1,0,1): 0,
            (1,0,0): 1,
            (0,1,1): 1,
            (0,1,0): 0,
            (0,0,1): 1,
            (0,0,0): 0
        }

    def initialize_sim(self):
        self.record[-1][self.number_steps//2] = 1

    def run_one_step(self):
        self.iter += 1

        nState = cp(self.record[-1])
        for c in range(1,self.number_steps-1):
            key = tuple(self.record[-1][c-1:c+2])
            nState[c] = self.lookup[key]
        self.record.append(nState)
        '''
        # for everything except the ends
        def helper(i):
            return(self.s[i-1]==self.s[i+1]))

        self.s = self.s[0]+[helper(i) for i range(1,self.number_steps-1)] + self.s[-1]

        # im lazy now but if you refactor everything to be true false this should be ok ish
        '''



    def print_sim_state(self):
        print("_____State {}_____".format(self.iter))
        for r in range(self.iter):
            res = []
            for c in range(self.number_steps):
                if self.record[r][c] == 0:
                    res.append("_")
                else:
                    res.append(u"\u2588")
            print(res)

if __name__ == '__main__':
    test = ruleNinety(30)
    test.run()
