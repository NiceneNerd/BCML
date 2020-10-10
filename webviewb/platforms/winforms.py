# -*- coding: utf-8 -*-
# pylint: skip-file
"""
(C) 2014-2019 Roman Sirokov and contributors
Licensed under BSD license

http://github.com/r0x0r/pywebview/
"""

import os
import sys
import logging
from threading import Event
from ctypes import windll

from webviewb import (
    windows,
    OPEN_DIALOG,
    FOLDER_DIALOG,
    SAVE_DIALOG,
)
from webviewb.util import (
    interop_dll_path,
    parse_file_type,
    inject_base_uri,
)
from webviewb.localization import localization

import clr

clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Collections")
clr.AddReference("System.Threading")
clr.AddReference(interop_dll_path("Microsoft.WindowsAPICodePack.Shell.dll"))

import System.Windows.Forms as WinForms
from Microsoft.WindowsAPICodePack.Dialogs import CommonOpenFileDialog
from System import IntPtr, Int32, Func, Type
from System.Threading import Thread, ThreadStart, ApartmentState
from System.Drawing import Size, Icon, ColorTranslator, SizeF


logger = logging.getLogger("pywebview")

settings = {}


from . import cef as CEF

IWebBrowserInterop = object

logger.debug("Using WinForms / CEF")
renderer = "cef"


class BrowserView:
    instances = {}

    class BrowserForm(WinForms.Form):
        def __init__(self, window):
            self.uid = window.uid
            self.pywebview_window = window
            self.url = None
            self.Text = window.title
            self.Size = Size(window.initial_width, window.initial_height)
            self.MinimumSize = Size(window.min_size[0], window.min_size[1])
            self.BackColor = ColorTranslator.FromHtml(window.background_color)

            if window.initial_x is not None and window.initial_y is not None:
                self.move(window.initial_x, window.initial_y)
            else:
                self.StartPosition = WinForms.FormStartPosition.CenterScreen

            self.AutoScaleDimensions = SizeF(96.0, 96.0)
            self.AutoScaleMode = WinForms.AutoScaleMode.Dpi

            if not window.resizable:
                self.FormBorderStyle = WinForms.FormBorderStyle.FixedSingle
                self.MaximizeBox = False

            if window.minimized:
                self.WindowState = WinForms.FormWindowState.Minimized

            # Application icon
            handle = windll.kernel32.GetModuleHandleW(None)
            icon_handle = windll.shell32.ExtractIconW(handle, sys.executable, 0)

            if icon_handle != 0:
                self.Icon = Icon.FromHandle(
                    IntPtr.op_Explicit(Int32(icon_handle))
                ).Clone()

            windll.user32.DestroyIcon(icon_handle)

            self.closed = window.closed
            self.closing = window.closing
            self.shown = window.shown
            self.loaded = window.loaded
            self.url = window.url
            self.text_select = window.text_select
            self.on_top = window.on_top

            self.is_fullscreen = False
            if window.fullscreen:
                self.toggle_fullscreen()

            if window.frameless:
                self.frameless = window.frameless
                self.FormBorderStyle = 0
            CEF.create_browser(window, self.Handle.ToInt32(), BrowserView.alert)

            self.Shown += self.on_shown
            self.FormClosed += self.on_close
            self.FormClosing += self.on_closing

            self.Resize += self.on_resize

        def on_shown(self, sender, args):
            return

        def on_close(self, sender, args):
            def _shutdown():
                CEF.shutdown()
                WinForms.Application.Exit()

            CEF.close_window(self.uid)

            del BrowserView.instances[self.uid]

            # during tests windows is empty for some reason. no idea why.
            if self.pywebview_window in windows:
                windows.remove(self.pywebview_window)

            self.closed.set()

            if len(BrowserView.instances) == 0:
                self.Invoke(Func[Type](_shutdown))

        def on_closing(self, sender, args):
            self.closing.set()

            if self.pywebview_window.confirm_close:
                result = WinForms.MessageBox.Show(
                    localization["global.quitConfirmation"],
                    self.Text,
                    WinForms.MessageBoxButtons.OKCancel,
                    WinForms.MessageBoxIcon.Asterisk,
                )

                if result == WinForms.DialogResult.Cancel:
                    args.Cancel = True

        def on_resize(self, sender, args):
            CEF.resize(self.Width, self.Height, self.uid)

        def evaluate_js(self, script):
            def _evaluate_js():
                self.browser.evaluate_js(script)

            self.loaded.wait()
            self.Invoke(Func[Type](_evaluate_js))
            self.browser.js_result_semaphore.acquire()

            return self.browser.js_result

        def load_html(self, content, base_uri):
            def _load_html():
                self.browser.load_html(content, base_uri)

            self.Invoke(Func[Type](_load_html))

        def load_url(self, url):
            def _load_url():
                self.browser.load_url(url)

            self.Invoke(Func[Type](_load_url))

        def get_current_url(self):
            return self.browser.get_current_url

        def hide(self):
            self.Invoke(Func[Type](self.Hide))

        def show(self):
            self.Invoke(Func[Type](self.Show))

        def toggle_fullscreen(self):
            def _toggle():
                screen = WinForms.Screen.FromControl(self)

                if not self.is_fullscreen:
                    self.old_size = self.Size
                    self.old_state = self.WindowState
                    self.old_style = self.FormBorderStyle
                    self.old_location = self.Location
                    self.FormBorderStyle = 0  # FormBorderStyle.None
                    self.Bounds = WinForms.Screen.PrimaryScreen.Bounds
                    self.WindowState = WinForms.FormWindowState.Maximized
                    self.is_fullscreen = True
                    windll.user32.SetWindowPos(
                        self.Handle.ToInt32(),
                        None,
                        screen.Bounds.X,
                        screen.Bounds.Y,
                        screen.Bounds.Width,
                        screen.Bounds.Height,
                        64,
                    )
                else:
                    self.Size = self.old_size
                    self.WindowState = self.old_state
                    self.FormBorderStyle = self.old_style
                    self.Location = self.old_location
                    self.is_fullscreen = False

            if self.InvokeRequired:
                self.Invoke(Func[Type](_toggle))
            else:
                _toggle()

        @property
        def on_top(self):
            return self.on_top

        @on_top.setter
        def on_top(self, on_top):
            def _set():
                z_order = -1 if on_top is True else -2
                SWP_NOSIZE = 0x0001  # Retains the current size
                windll.user32.SetWindowPos(
                    self.Handle.ToInt32(),
                    z_order,
                    self.Location.X,
                    self.Location.Y,
                    None,
                    None,
                    SWP_NOSIZE,
                )

            if self.InvokeRequired:
                self.Invoke(Func[Type](_set))
            else:
                _set()

        def resize(self, width, height):
            windll.user32.SetWindowPos(
                self.Handle.ToInt32(),
                None,
                self.Location.X,
                self.Location.Y,
                width,
                height,
                64,
            )

        def move(self, x, y):
            SWP_NOSIZE = 0x0001  # Retains the current size
            SWP_NOZORDER = 0x0004  # Retains the current Z order
            SWP_SHOWWINDOW = 0x0040  # Displays the window
            windll.user32.SetWindowPos(
                self.Handle.ToInt32(),
                None,
                x,
                y,
                None,
                None,
                SWP_NOSIZE | SWP_NOZORDER | SWP_SHOWWINDOW,
            )

        def minimize(self):
            def _minimize():
                self.WindowState = WinForms.FormWindowState.Minimized

            self.Invoke(Func[Type](_minimize))

        def restore(self):
            def _restore():
                self.WindowState = WinForms.FormWindowState.Normal

            self.Invoke(Func[Type](_restore))

    @staticmethod
    def alert(message):
        WinForms.MessageBox.Show(message)


def _set_ie_mode():
    """
    By default hosted IE control emulates IE7 regardless which version of IE is installed. To fix this, a proper value
    must be set for the executable.
    See http://msdn.microsoft.com/en-us/library/ee330730%28v=vs.85%29.aspx#browser_emulation for details on this
    behaviour.
    """

    try:
        import _winreg as winreg  # Python 2
    except ImportError:
        import winreg  # Python 3

    def get_ie_mode():
        """
        Get the installed version of IE
        :return:
        """
        ie_key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Internet Explorer"
        )
        try:
            version, type = winreg.QueryValueEx(ie_key, "svcVersion")
        except:
            version, type = winreg.QueryValueEx(ie_key, "Version")

        winreg.CloseKey(ie_key)

        if version.startswith("11"):
            value = 0x2AF9
        elif version.startswith("10"):
            value = 0x2711
        elif version.startswith("9"):
            value = 0x270F
        elif version.startswith("8"):
            value = 0x22B8
        else:
            value = 0x2AF9  # Set IE11 as default

        return value

    try:
        browser_emulation = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Internet Explorer\Main\FeatureControl\FEATURE_BROWSER_EMULATION",
            0,
            winreg.KEY_ALL_ACCESS,
        )
    except WindowsError:
        browser_emulation = winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Internet Explorer\Main\FeatureControl\FEATURE_BROWSER_EMULATION",
            0,
            winreg.KEY_ALL_ACCESS,
        )

    try:
        dpi_support = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Internet Explorer\Main\FeatureControl\FEATURE_96DPI_PIXEL",
            0,
            winreg.KEY_ALL_ACCESS,
        )
    except WindowsError:
        dpi_support = winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Internet Explorer\Main\FeatureControl\FEATURE_96DPI_PIXEL",
            0,
            winreg.KEY_ALL_ACCESS,
        )

    mode = get_ie_mode()
    executable_name = sys.executable.split("\\")[-1]
    winreg.SetValueEx(browser_emulation, executable_name, 0, winreg.REG_DWORD, mode)
    winreg.CloseKey(browser_emulation)

    winreg.SetValueEx(dpi_support, executable_name, 0, winreg.REG_DWORD, 1)
    winreg.CloseKey(dpi_support)


def _allow_localhost():
    import subprocess

    # lifted from https://github.com/pyinstaller/pyinstaller/wiki/Recipe-subprocess
    def subprocess_args(include_stdout=True):
        if hasattr(subprocess, "STARTUPINFO"):
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            env = os.environ
        else:
            si = None
            env = None

        if include_stdout:
            ret = {"stdout": subprocess.PIPE}
        else:
            ret = {}

        ret.update(
            {
                "stdin": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "startupinfo": si,
                "env": env,
            }
        )
        return ret

    output = subprocess.check_output(
        "checknetisolation LoopbackExempt -s", **subprocess_args(False)
    )

    if "cw5n1h2txyewy" not in str(output):
        windll.shell32.ShellExecuteW(
            None,
            "runas",
            "checknetisolation",
            'LoopbackExempt -a -n="Microsoft.Win32WebViewHost_cw5n1h2txyewy"',
            None,
            1,
        )


_main_window_created = Event()
_main_window_created.clear()


def create_window(window):
    def create():
        browser = BrowserView.BrowserForm(window)
        BrowserView.instances[window.uid] = browser

        if not window.hidden:
            browser.Show()

        _main_window_created.set()

        if window.uid == "master":
            app.Run()

    app = WinForms.Application

    if window.uid == "master":
        if sys.getwindowsversion().major >= 6:
            windll.user32.SetProcessDPIAware()

        CEF.init(window)

        app.EnableVisualStyles()
        app.SetCompatibleTextRenderingDefault(False)
        thread = Thread(ThreadStart(create))
        thread.SetApartmentState(ApartmentState.STA)
        thread.Start()
        thread.Join()

    else:
        _main_window_created.wait()
        i = list(BrowserView.instances.values())[0]  # arbitrary instance
        i.Invoke(Func[Type](create))


def set_title(title, uid):
    def _set_title():
        window.Text = title

    window = BrowserView.instances[uid]
    if window.InvokeRequired:
        window.Invoke(Func[Type](_set_title))
    else:
        _set_title()


def create_file_dialog(
    dialog_type, directory, allow_multiple, save_filename, file_types, uid
):
    window = BrowserView.instances[uid]

    if not directory:
        directory = os.environ["HOMEPATH"]

    try:
        if dialog_type == FOLDER_DIALOG:
            dialog = CommonOpenFileDialog()
            dialog.IsFolderPicker = True

            if directory:
                dialog.InitialDirectory = directory

            result = dialog.ShowDialog()
            if result == WinForms.DialogResult.OK:
                file_path = (dialog.FileName,)
            else:
                file_path = None
        elif dialog_type == OPEN_DIALOG:
            dialog = WinForms.OpenFileDialog()

            dialog.Multiselect = allow_multiple
            dialog.InitialDirectory = directory

            if len(file_types) > 0:
                dialog.Filter = "|".join(
                    ["{0} ({1})|{1}".format(*parse_file_type(f)) for f in file_types]
                )
            else:
                dialog.Filter = (
                    localization["windows.fileFilter.allFiles"] + " (*.*)|*.*"
                )
            dialog.RestoreDirectory = True

            result = dialog.ShowDialog(window)
            if result == WinForms.DialogResult.OK:
                file_path = tuple(dialog.FileNames)
            else:
                file_path = None

        elif dialog_type == SAVE_DIALOG:
            dialog = WinForms.SaveFileDialog()
            dialog.Filter = localization["windows.fileFilter.allFiles"] + " (*.*)|"
            dialog.InitialDirectory = directory
            dialog.RestoreDirectory = True
            dialog.FileName = save_filename

            result = dialog.ShowDialog(window)
            if result == WinForms.DialogResult.OK:
                file_path = dialog.FileName
            else:
                file_path = None

        return file_path
    except:
        logger.exception("Error invoking {0} dialog".format(dialog_type))
        return None


def get_current_url(uid):
    return CEF.get_current_url(uid)


def load_url(url, uid):
    window = BrowserView.instances[uid]
    window.loaded.clear()

    CEF.load_url(url, uid)


def load_html(content, base_uri, uid):
    CEF.load_html(inject_base_uri(content, base_uri), uid)
    return


def show(uid):
    window = BrowserView.instances[uid]
    window.show()


def hide(uid):
    window = BrowserView.instances[uid]
    window.hide()


def toggle_fullscreen(uid):
    window = BrowserView.instances[uid]
    window.toggle_fullscreen()


def set_on_top(uid, on_top):
    window = BrowserView.instances[uid]
    window.on_top = on_top


def resize(width, height, uid):
    window = BrowserView.instances[uid]
    window.resize(width, height)


def move(x, y, uid):
    window = BrowserView.instances[uid]
    window.move(x, y)


def minimize(uid):
    window = BrowserView.instances[uid]
    window.minimize()


def restore(uid):
    window = BrowserView.instances[uid]
    window.restore()


def destroy_window(uid):
    def _close():
        window.Close()

    window = BrowserView.instances[uid]
    window.Invoke(Func[Type](_close))


def evaluate_js(script, uid):
    return CEF.evaluate_js(script, uid)


def get_position(uid):
    return BrowserView.instances[uid].Left, BrowserView.instances[uid].Top


def get_size(uid):
    size = BrowserView.instances[uid].Size
    return size.Width, size.Height
