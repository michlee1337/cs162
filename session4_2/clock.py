class ClockIterator():
    def __iter__(self):
        self.h = 0
        self.m = 0
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
for time in clock:
    print(time)
