_MAJOR = 3
_MINOR = 0
_PATCH = "7"

VERSION = f"{_MAJOR}.{_MINOR}.{_PATCH}"
USER_VERSION = f"""{_MAJOR}.{_MINOR}.{_PATCH[0:1]} {
    'alpha' if _MAJOR < 1 else ''
}{
    f'beta {_PATCH[_PATCH.rindex("b") + 1:]}' if 'b' in _PATCH else ''
}{
    f'release candidate {_PATCH[_PATCH.rindex("rc") + 2:]}' if 'rc' in _PATCH else ''
}"""
