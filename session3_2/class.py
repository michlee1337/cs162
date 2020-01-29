'''
Event

Variable
- StringVar
- IntVar
- DoubleVar
- BooleanVar


Misc (interior widgets)
- BaseWidget
    - Widget: pack place grid
        - Button
        - Canvas: XView, YView
        - Checkbutton
        - Entry: Xview
        - Frame
        - Label
        - Listbox (XView, YView)
        - Menu
        - MenuButton (no longer used)
            - OptionMenu
        - Message
        - Radiobutton
        - Scale
        - Scrollbar
        - Text: Xview YView
        - Sprinbox: XView
        - LabelFrame
        - PanedWindow

    - Toplevel(Wm)


Call Wrapper (remembers function to call on event)


XView (x axis movement)

YView (y axis movement)

Wm (comm w windows manager)

Pack (base class for common methods to put widgets in widgets)
Place (base class for placement of widgets)
grid (base class for padding)

_setit(wraps command in option menu)

Image
    - PhotoImage
    - Bitmap Image

'''



from tkinter import *
root = Tk()

# entry box
e = Entry(width=35,borderwidth=5)
e.grid(row=0,column=0,columnspan=3,padx=10,pady=10)

# number buttons

def button_add():
    pass

buttons = []
for n in range(10):
    btn = Button(root,text=str(n),padx=40,pady=20,command=button_add)
    btn.grid(row=n//3+1, column = n%3)
    buttons.append(btn)



'''

l1 = Label(root, text="Hello World")
l2 = Label(root, text="sup")

#l1.pack()
l1.grid(row=0,column=0)
l2.grid(row=10,column=10)'''

root.mainloop()
