path = '/workspace/TRELLIS.2/trellis2/pipelines/rembg/BiRefNet.py'
src = open(path).read()

old = '''class BiRefNet:
    def __init__(self, model_name: str = "ZhengPeng7/BiRefNet"):
        self.model = AutoModelForImageSegmentation.from_pretrained(
            model_name, trust_remote_code=True
        )'''

new = '''class BiRefNet:
    def __init__(self, model_name: str = "ZhengPeng7/BiRefNet"):
        # Disable init_empty_weights temporarily: briaai/RMBG-2.0 custom code
        # calls .item() in __init__, which fails on meta tensors.
        from contextlib import contextmanager
        import accelerate.big_modeling as _bm
        import transformers.modeling_utils as _mu
        _orig_bm = _bm.init_empty_weights
        _orig_mu = getattr(_mu, 'init_empty_weights', None)
        _noop = contextmanager(lambda: (yield))
        _bm.init_empty_weights = _noop
        if _orig_mu is not None:
            _mu.init_empty_weights = _noop
        try:
            self.model = AutoModelForImageSegmentation.from_pretrained(
                model_name, trust_remote_code=True, device_map=None
            )
        finally:
            _bm.init_empty_weights = _orig_bm
            if _orig_mu is not None:
                _mu.init_empty_weights = _orig_mu'''

if old in src:
    open(path, 'w').write(src.replace(old, new))
    print('Patched BiRefNet.py: init_empty_weights disabled during load')
else:
    print('WARNING: pattern not found in BiRefNet.py, patch skipped')
    print('First 500 chars of file:')
    print(src[:500])
