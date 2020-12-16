DEBUG = False
NO_CEF = False


def native_msg(msg: str, title: str):
    # pylint: disable=import-outside-toplevel
    import ctypes

    ctypes.windll.user32.MessageBoxW(  # type: ignore
        0,
        msg,
        title,
        0x0 | 0x10,
    )


def dependency_check():
    # pylint: disable=import-outside-toplevel
    # fmt: off
    try:
        import oead
        del oead
    except ImportError:
        from platform import system
        if system() == "Windows":
            native_msg(
                "The latest (2019) Visual C++ redistributable is required to run BCML. "
                "Please download it from the following link and try again:\n"
                "https://aka.ms/vs/16/release/vc_redist.x64.exe",
                "Dependency Error"
            )
        from sys import exit as ex
        ex(1)
    # fmt: on


dependency_check()