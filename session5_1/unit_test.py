class ClockIterator():
    def __iter__(self):
        self.h = 23
        self.m = 59
        return(self)

    def __next__(self):
        # increment
        if self.m == 59:
            self.m = 0
            self.h += 1
            self.h %= 24
        else:
            self.m += 1
        return("{:02}:{:02}".format(self.h, self.m))

clock = ClockIterator()

import unittest

class TestClockIter(unittest.TestCase):

    def test_iter(self):
        clock = ClockIterator()
        t = {
        1:"00:00",
        60:"00:59",
        61:"01:00",
        1440: "23:59",
        1441: "00:00"
        }
        iter = 0
        for time in clock:
            iter += 1
            if iter in t:
                self.assertEqual(t[iter],time)
            if iter == 1000:
                break

if __name__ == '__main__':
    unittest.main()
