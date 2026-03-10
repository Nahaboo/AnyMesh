path = '/workspace/TRELLIS.2/trellis2/pipelines/rembg/BiRefNet.py'
src = open(path).read()
old = 'AutoModelForImageSegmentation.from_pretrained(\n            model_name, trust_remote_code=True\n        )'
new = 'AutoModelForImageSegmentation.from_pretrained(\n            model_name, trust_remote_code=True, device_map=None\n        )'
if old in src:
    open(path, 'w').write(src.replace(old, new))
    print('Patched BiRefNet.py: device_map=None added')
else:
    print('WARNING: pattern not found in BiRefNet.py, patch skipped')
