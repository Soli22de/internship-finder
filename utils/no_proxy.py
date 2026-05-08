"""
Global proxy bypass patch.
Import this at the start of any module that uses requests.
Monkey-patches requests.Session to disable system proxy (VPN fix).
"""
import requests

_orig_session_init = requests.Session.__init__
_orig_get = requests.get
_orig_post = requests.post


def _patched_session_init(self):
    _orig_session_init(self)
    self.trust_env = False
    self.proxies = {"http": None, "https": None}


def _patched_get(url, **kwargs):
    kwargs.setdefault("proxies", {"http": None, "https": None})
    return _orig_get(url, **kwargs)


def _patched_post(url, **kwargs):
    kwargs.setdefault("proxies", {"http": None, "https": None})
    return _orig_post(url, **kwargs)


requests.Session.__init__ = _patched_session_init
requests.get = _patched_get
requests.post = _patched_post
