## Design Patterns - Singleton and Iterator

Design patterns are a set of architectural solutions to common problems.
By following these design patterns when appropriate you will be able to build
well-designed software systems without needing many years of experience to
get there.  Instead you will just need to know when a design pattern applies
and what the most appropriate pattern is for a given situation.  (But don't
turn all your code into a collection of design patterns!)

These design patterns are also useful for communication. Since a design pattern
often encompasses several classes together, it can be much more efficient to
simply say "our simulation uses a template pattern", than describe each class
and its relation to the other classes.

## The Singleton Design pattern
One of the most common design patterns is the Singleton design pattern.  This
pattern is used whenever there should only be a single instance of the class.
This occurs more often than you might suspect. Some examples include:

 - **logging**: whenever you want to perform logging, then you want to perform
 the logging in a single consistent manner.  This means that any configuration
 should be performed only once, and then reused.
 - **database connections**: database connections are expensive to establish
 and close.  It is much cheaper to instead maintain one (or more) connections,
 and let multiple threads share the single connection(s).  This means that
 the same database connection should be used (and hence accesible) from
 anywhere in the program.

Notice the commonality here.  In all cases there should be a universal means of
accessing a single object.

## The Iterator Design Pattern

Many objects in Python are iteratable.  This means that they can produce items
in some sort of order.

Run the following code in a terminal:
```python
t = [1,2,3]
it = iter(t)
print(next(it))
print(next(it))
print(next(it))
print(next(it))
```
Notice that `iter()` and `next()` are actually keywords in Python, which shows
how important iterators are to the language!

By providing this simple interface it allows us to consistently use the same
code for dealing with sequences, even if there are wildly different
implementations underneath.  The code could be displaying a simple linked list,
or it could be making web calls to an online service and displaying consecutive
results.

## Questions

### 1. Singleton Implementation: Logging

A Christmas Tree program is contained in the ChristmasTree folder.

 - Run the file using `python3 main.py`.
 - Consult the internet to find example implementations of a singleton in Python.
 - Add your own FileLog class in `log.py` so that wherever you create a new 
   Logger, that it ends up using the same set of handlers, even though in
   this case there is only a single handler class.
    - Just use an INFO level, a WARNING level, and an ERROR level.
    - No need for logging filters.
    - No need for logging formatters.
 - **YOUR SOLUTION MUST NOT USE `import logging`! The point is to implement our own**
   **logging library**
 - You must be able to change the appropriate level of logging **globally** by 
   adding a single line of logging configuration in main.py. 

Please note that the Christmas tree application is a very hypothetical set of 
libraries. It generates a random set of presents and distributes them to a 
set of children. However the library requires that the process follows a particular 
order. The usage of the library in `main.py` first does things correctly, and then
does things incorrectly. This is fine. We are using this example purely as a means
of testing your logging library, so we actually want to generate a few warnings and
errors!

Bring your code to class and be prepared to paste it into a poll answer.

### 2. The clock iterator

An iterator doesn't necessarily need to raise the StopIteration exception if
you want to represent an infinite sequence.

An example infinite loop might be given by our digital clocks.  These devices
endlessly display the time of day before looping back to display a new day.

In this question write a class `ClockIterator` which can be used in the
following code snippet:

```python
clock = ClockIterator()
for time in clock:
    print(time)
```

And the code should produce an infinite loop of output:

```
00:00
00:01
00:02
...
23:59
00:00
...
```

Bring your code to class and be prepared to paste it into a poll answer.
