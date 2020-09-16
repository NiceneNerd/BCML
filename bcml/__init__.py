DEBUG = False
NO_CEF = False


def native_msg(msg: str, title: str):
    # pylint: disable=import-outside-toplevel
    import ctypes

    ctypes.windll.user32.MessageBoxW(
        0, msg, title, 0x0 | 0x10,
    )
