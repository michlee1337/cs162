import random
try:
    from log import FileLog
    logFile = FileLog()
except Exception as e:
    print('a WARNING: Missing Filelog() in log.py')

def giftGenerate(count = 1):
    """ Gift Generation.

    Input:
        count: int. Number of gifts.

    Output:
        List object, containing the gifts as string.
    """
    glist = ['kettle', 'bell', 'chicken', 'donut', 'gingerman', \
             'doll', 'figure', 'N\' Switch', 'toy car', \
             'skateboard', 'LEGO set', \
             'crayons', 'Rubik\'s cube', 'toy truck']

    ans = []
    for _ in range(count):
        ans.append(random.choice(glist))

    try:
        logFile.info('Generated ' + str(count) + ' gifts from giftGenerate().')
    except:
        pass
    return ans

def nameGenerate(count = 1):
    """ Name Generation.

    Input:
        cunt: int. Number of children.

    Output:
        List object, containing the names as string.
    """
    nlist = ['James', 'David', 'Christopher', 'George', 'Ronal', 'John', \
             'Richard', 'Daniel', 'Kenneth', 'Anthon', 'Robert', 'Charles',\
             'Paul', 'Steven', 'Kevi', 'Michael', 'Joseph', 'Mark', 'Edward', \
             'Jaso', 'William', 'Thomas', 'Donald', 'Brian', 'Jeff', \
             'Mary', 'Jennifer', 'Lisa', 'Sandra', 'Michell', 'Patricia',\
             'Maria', 'Nancy', 'Donna', 'Laur', 'Linda', 'Susan', 'Karen',\
             'Carol', 'Sara', 'Barbara', 'Margaret', 'Betty', 'Ruth',\
             'Kimberl', 'Elizabeth', 'Dorothy', 'Helen', 'Sharon', 'Debora']

    ans = []
    for _ in range(count):
        ans.append(random.choice(nlist))

    try:
        logFile.info('Generated ' + str(count) + ' names from nameGenerate().')
    except:
        pass
    return ans
