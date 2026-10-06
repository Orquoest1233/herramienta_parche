# __init__.py
from krita import *
import math
from .parche_ui import ParcheDialog
from .image_utils import blur_gris, blur_gaussiano, preparar_mask

class ParcheExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)
        # Cachés de estado
        self.cached_feather = -1
        self.cached_blur_type = -1
        self.cached_mask = None
        self.mask_base = None
        self.full_source_data = None

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction("activar_parche_pro", "Parche PRO", "tools/scripts")
        action.triggered.connect(self.iniciar_parche)

    def iniciar_parche(self):
        doc = Krita.instance().activeDocument()
        if not doc or not doc.selection():
            return
            
        self.doc, self.nodo = doc, doc.activeNode()
        sel = doc.selection()
        
        self.pad = 30
        self.x, self.y = sel.x() - self.pad, sel.y() - self.pad
        self.w, self.h = sel.width() + (self.pad * 2), sel.height() + (self.pad * 2)
        
        # Resetear cachés ANTES de crear el diálogo
        self.cached_feather = -1
        self.cached_blur_type = -1
        self.cached_mask = None
        self.mask_base = None
        self.full_source_data = None
        
        # Crear diálogo SIN callback todavía (evita disparos durante __init__)
        dialogo = ParcheDialog(update_callback=None)

        # Calcular área de origen expandida
        max_offset = dialogo.spin_x.maximum() 
        source_pad = self.pad + max_offset
        
        self.source_x = max(0, sel.x() - source_pad)
        self.source_y = max(0, sel.y() - source_pad)
        self.source_w = min(doc.width() - self.source_x, sel.width() + source_pad * 2)
        self.source_h = min(doc.height() - self.source_y, sel.height() + source_pad * 2)

        # Cachear buffers de origen y backup
        raw_data = self.nodo.pixelData(self.source_x, self.source_y, self.source_w, self.source_h)
        self.full_source_data = bytearray(raw_data)
        
        self.backup = self.nodo.pixelData(self.x, self.y, self.w, self.h)
        
        # Preparar máscara base
        m_raw = sel.pixelData(sel.x(), sel.y(), sel.width(), sel.height())
        self.mask_base = preparar_mask(m_raw, sel.width(), sel.height(), self.w, self.h, self.pad)
        
        # AHORA conectar el callback (todo el estado está listo)
        dialogo.update_callback = self.actualizar_lienzo
        
        if not dialogo.exec_():
            # Cancelado: restaurar backup
            self.nodo.setPixelData(self.backup, self.x, self.y, self.w, self.h)
        else:
            # Aceptado: refrescar proyección
            self.doc.refreshProjection()
            
        # Limpieza
        self.full_source_data = None
        self.cached_mask = None
        self.mask_base = None

    def actualizar_lienzo(self, ox, oy, feather, skip, blur_type=0, angulo=0):
        # Guard de seguridad: defensa en profundidad
        if self.full_source_data is None or self.mask_base is None:
            return

        # 1. Gestión de caché de suavizado
        if feather != self.cached_feather or blur_type != self.cached_blur_type:
            if feather <= 0:
                self.cached_mask = self.mask_base
            elif blur_type == 0:
                self.cached_mask = blur_gris(self.mask_base, self.w, self.h, feather)
            else:
                self.cached_mask = blur_gaussiano(self.mask_base, self.w, self.h, feather)
            
            self.cached_feather = feather
            self.cached_blur_type = blur_type

        # 2. Preparación de datos locales
        bg = bytearray(self.backup)
        res = bytearray(bg)
        src = self.full_source_data
        mask = self.cached_mask
        
        # Pre-cálculo de límites
        mask_len = len(mask)
        src_len = len(src)
        res_len = len(res)
        w4 = self.w * 4
        src_w4 = self.source_w * 4
        
        # Trigonometría precalculada
        ang_rad = math.radians(angulo)
        cos_a = math.cos(ang_rad)
        sin_a = math.sin(ang_rad)
        cx = self.w * 0.5
        cy = self.h * 0.5
        
        # 3. Bucle optimizado
        for ly in range(0, self.h, skip):
            row_mask_offset = ly * self.w
            local_y = ly - cy
            
            for lx in range(0, self.w, skip):
                m_idx = row_mask_offset + lx
                
                if m_idx >= mask_len:
                    continue
                val_alpha = mask[m_idx]
                
                if val_alpha == 0:
                    continue
                
                local_x = lx - cx
                
                # Rotación 2D inversa
                rot_x = local_x * cos_a - local_y * sin_a + cx
                rot_y = local_x * sin_a + local_y * cos_a + cy

                # Coordenada de origen global
                global_src_x = self.x + int(rot_x) + ox
                global_src_y = self.y + int(rot_y) + oy

                # Coordenada local del buffer de origen
                local_src_x = global_src_x - self.source_x
                local_src_y = global_src_y - self.source_y
                
                # ÚNICA validación necesaria: origen dentro del buffer
                # (si esto pasa, g_idx + 3 < src_len SIEMPRE se cumple)
                if not (0 <= local_src_x < self.source_w and 0 <= local_src_y < self.source_h):
                    continue
                
                a = val_alpha / 255.0
                inv_a = 1.0 - a
                
                i = (ly * self.w + lx) * 4
                g_idx = local_src_y * src_w4 + local_src_x * 4
                
                # i + 3 < res_len SIEMPRE se cumple porque ly < h y lx < w
                # No hace falta validar i

                # Interpolación RGBA
                r = int(src[g_idx]     * a + bg[i]     * inv_a)
                g = int(src[g_idx + 1] * a + bg[i + 1] * inv_a)
                b = int(src[g_idx + 2] * a + bg[i + 2] * inv_a)
                alpha = int(src[g_idx + 3] * a + bg[i + 3] * inv_a)
                
                # Relleno de bloque con slicing
                pixel_bytes = bytes([r, g, b, alpha])
                block_w = min(skip, self.w - lx)
                
                for block_y in range(skip):
                    dy = ly + block_y
                    if dy >= self.h:
                        break
                    dest_row_start = dy * w4
                    start = dest_row_start + lx * 4
                    end = start + block_w * 4
                    if end <= res_len:
                        res[start:end] = pixel_bytes * block_w

        # Aplicar cambios y refrescar
        self.nodo.setPixelData(bytes(res), self.x, self.y, self.w, self.h)
        self.doc.refreshProjection()

Krita.instance().addExtension(ParcheExtension(Krita.instance()))