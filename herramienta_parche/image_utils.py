# image_utils.py
from krita import *
import math

# Cache global de kernels de box blur por radio (evita recalcular [1/size]*size)
_box_kernel_cache = {}

def _separable_blur(data, w, h, kernel):
    """Aplica un blur separable genérico usando un kernel 1D."""
    k_size = len(kernel)
    radius = k_size // 2
    t, o = bytearray(data), bytearray(data)
    
    # Pase horizontal
    for y in range(h):
        row = y * w
        for x in range(w):
            v = 0.0
            for k in range(k_size):
                ix = max(0, min(w - 1, x + k - radius))
                v += data[row + ix] * kernel[k]
            t[row + x] = int(v)
            
    # Pase vertical
    for x in range(w):
        for y in range(h):
            v = 0.0
            for k in range(k_size):
                iy = max(0, min(h - 1, y + k - radius))
                v += t[iy * w + x] * kernel[k]
            o[y * w + x] = int(v)
            
    return o

def blur_gaussiano(data, w, h, r):
    """
    Desenfoque gaussiano aproximado mediante 3 pasadas de box blur.
    O(n) en lugar de O(n*k) — ideal para previsualizaciones en tiempo real.
    """
    if r <= 0:
        return data
    result = data
    box_r = max(1, r // 3)
    for _ in range(3):
        result = blur_gris(result, w, h, box_r)
    return result

def blur_gris(data, w, h, r):
    """Box Blur (promedio simple) con kernel cacheado para máxima velocidad."""
    if r <= 0:
        return data
    if r not in _box_kernel_cache:
        size = r * 2 + 1
        _box_kernel_cache[r] = [1.0 / size] * size
    return _separable_blur(data, w, h, _box_kernel_cache[r])

def preparar_mask(raw, sw, sh, w, h, pad):
    """
    Adapta la máscara de selección al tamaño del área de trabajo con padding.
    Valida límites para evitar escrituras fuera de rango.
    """
    raw_b = bytearray(raw)
    new_m = bytearray(w * h)
    step = 4 if len(raw_b) == (sw * sh * 4) else 1
    raw_len = len(raw_b)
    
    for ly in range(sh):
        dest_y = ly + pad
        if dest_y < 0 or dest_y >= h:
            continue
        row_offset = dest_y * w
        for lx in range(sw):
            dest_x = lx + pad
            if dest_x < 0 or dest_x >= w:
                continue
            idx = (ly * sw + lx) * step + (3 if step == 4 else 0)
            if 0 <= idx < raw_len:
                new_m[row_offset + dest_x] = raw_b[idx]
                
    return new_m