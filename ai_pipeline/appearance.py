import sys
from tkinter import ttk


# WinDirStat's DarkMode::Color roles and the first color in its treemap palette.
WINDOW = "#202020"
CONTROL = "#2d2d2d"
FRAME = "#323232"
LIGHT = "#3c3c3c"
EDGE = "#464646"
TEXT = "#dcdcdc"
DISABLED_TEXT = "#787878"
SELECTION = "#0078d7"
SELECTION_TEXT = "#ffffff"
GRAPH_BLUE = "#4f9de8"


def apply_dark_theme(root):
    style = ttk.Style(root)
    # The Windows ttk theme paints system colors directly. Clam exposes its colors.
    style.theme_use("clam")
    style.configure(".", background=CONTROL, foreground=TEXT,
                    bordercolor=EDGE, lightcolor=EDGE, darkcolor=EDGE,
                    troughcolor=WINDOW, arrowcolor=TEXT,
                    selectbackground=SELECTION, selectforeground=SELECTION_TEXT,
                    focuscolor=GRAPH_BLUE)
    style.map(".", background=[("disabled", CONTROL), ("active", LIGHT)],
              foreground=[("disabled", DISABLED_TEXT)],
              arrowcolor=[("disabled", DISABLED_TEXT)])

    style.configure("TButton", background=FRAME)
    style.map("TButton", background=[("disabled", CONTROL), ("pressed", WINDOW), ("active", LIGHT)],
              bordercolor=[("!disabled", "focus", GRAPH_BLUE), ("!disabled", "alternate", GRAPH_BLUE)],
              lightcolor=[("pressed", EDGE)], darkcolor=[("pressed", EDGE)])
    style.configure("TCheckbutton", indicatorbackground=WINDOW, indicatorforeground=TEXT)
    style.map("TCheckbutton", indicatorbackground=[("disabled", CONTROL), ("selected", SELECTION)],
              indicatorforeground=[("disabled", DISABLED_TEXT), ("selected", SELECTION_TEXT)])

    for widget in ("TEntry", "TSpinbox", "TCombobox"):
        style.configure(widget, fieldbackground=WINDOW, insertcolor=TEXT)
        style.map(widget, background=[("disabled", CONTROL), ("active", LIGHT)],
                  fieldbackground=[("disabled", CONTROL), ("readonly", WINDOW)],
                  bordercolor=[("focus", GRAPH_BLUE)], arrowcolor=[("disabled", DISABLED_TEXT)])
    style.map("TCombobox", foreground=[("disabled", DISABLED_TEXT)])
    for option, color in (("background", WINDOW), ("foreground", TEXT),
                          ("selectBackground", SELECTION), ("selectForeground", SELECTION_TEXT)):
        root.option_add(f"*TCombobox*Listbox.{option}", color)

    style.configure("TNotebook.Tab", background=FRAME, padding=(8, 4))
    style.map("TNotebook.Tab", background=[("selected", CONTROL), ("active", LIGHT)],
              lightcolor=[("selected", GRAPH_BLUE), ("!selected", EDGE)])
    style.configure("Treeview", fieldbackground=WINDOW, background=WINDOW)
    style.map("Treeview", background=[("selected", SELECTION)],
              foreground=[("selected", SELECTION_TEXT)])
    style.configure("Treeview.Heading", background=FRAME, padding=(5, 3))
    style.map("Treeview.Heading", background=[("active", LIGHT)])
    style.configure("Vertical.TScrollbar", background=FRAME)
    style.map("Vertical.TScrollbar", background=[("pressed", EDGE), ("active", LIGHT)])
    style.configure("Horizontal.TProgressbar", background=GRAPH_BLUE,
                    lightcolor=GRAPH_BLUE, darkcolor=GRAPH_BLUE)

    root.configure(background=CONTROL)
    if sys.platform == "win32":
        root.bind("<Map>", set_dark_title_bar, add="+")


def set_dark_title_bar(event):
    root = event.widget
    if root is not root.winfo_toplevel():
        return

    import ctypes
    from ctypes import wintypes

    try:
        get_ancestor = ctypes.windll.user32.GetAncestor
        get_ancestor.argtypes = (wintypes.HWND, wintypes.UINT)
        get_ancestor.restype = wintypes.HWND
        hwnd = get_ancestor(root.winfo_id(), 2)  # GA_ROOT includes Tk's native frame.
        set_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
    except (AttributeError, OSError):
        return
    set_attribute.argtypes = (wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
    enabled = wintypes.BOOL(True)
    for attribute in (20, 19):
        if set_attribute(hwnd, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled)) == 0:
            break

    # Recent Windows releases accept explicit caption colors independently of the system theme.
    for attribute, value in ((35, 0x202020), (36, 0xDCDCDC)):
        color = wintypes.DWORD(value)
        set_attribute(hwnd, attribute, ctypes.byref(color), ctypes.sizeof(color))
