import pygame
import random
import math
import os
import sys
import json
import struct
from collections import deque
from datetime import datetime, timedelta

# --- 1. INICIALIZACIÓN ---
pygame.mixer.pre_init(44100, -16, 2, 2048) 
pygame.init()
pygame.mixer.init()
pygame.mixer.set_num_channels(32) 

PANTALLA = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.HWSURFACE)
ANCHO, ALTO = PANTALLA.get_size()
FACTOR = min(ANCHO / 450, ALTO / 900, 2.0)
RELOJ = pygame.time.Clock()
FPS = 60

# --- 2. DATOS Y COLORES ---
COLORES = {
    "BG": (0, 5, 10), 
    "NEON": (0, 255, 50),
    "NEON_DARK": (0, 80, 20),
    "PELIGRO": (255, 0, 0),
    "META": (200, 255, 255),
    "GRAVEDAD": (180, 0, 255),
    "PORTAL_A": (255, 150, 0),
    "PORTAL_B": (0, 150, 255),
    "POWER_AMMO": (0, 200, 255),
    "POWER_GHOST": (255, 50, 50),
    "UI_BG": (0, 20, 0, 200),
    "BLANCO": (255, 255, 255),
    "GOLD": (255, 215, 0),
    "ACHIEVE": (0, 255, 255),
    "CRISTAL": (200, 255, 255),
    "DRONE": (255, 50, 0),
    "BOSS": (255, 0, 100),
    "LOCKED": (50, 50, 50),
    "PAST": (0, 100, 0),
    "DESTRUCT": (150, 150, 150),
    "TURRET": (255, 100, 0),
    "GRID": (0, 60, 60),
    "LASER_EMIT": (50, 50, 50)
}

# --- SISTEMA DE GUARDADO INTELIGENTE (PC / ANDROID) ---
try:
    # Intentamos importar la librería de android
    import android
    from android.storage import app_storage_path
    # Si estamos en el móvil, guardamos en la carpeta de la app
    ruta_base = app_storage_path()
    ARCHIVO_SAVE = os.path.join(ruta_base, "matrix_save_data.json")
except ImportError:
    # Si falla, es que estamos en PC
    ARCHIVO_SAVE = "matrix_save_data.json"

DATOS = {
    "estrellas": 0, "record": 1, "skins": [0], "skin_act": 0,
    "total_muertes": 0, "total_victorias": 0, "total_tiros": 0,
    "logros": [],
    "last_login": "", 
    "daily_streak": 0,
    "mejoras": {"ammo": 0, "aim": 0, "luck": 0}
}

CONFIG = {
    "vibra": True, 
    "vol_musica": 5, 
    "vol_sfx": 8,
    "hardcore": False
}
PRECIOS_MEJORAS = [10, 25, 50, 100, 200] 

SKINS = [
    {"id": 0, "n": "TERMINAL", "c": (0, 255, 50), "p": 0, "ab": None, "desc": "Estándar"},
    {"id": 1, "n": "CRIMSON", "c": (255, 0, 50), "p": 30, "ab": "Power", "desc": "+20% Potencia de tiro"},
    {"id": 2, "n": "GOLDEN", "c": (255, 200, 0), "p": 60, "ab": "Magnet", "desc": "Gran alcance de imán"},
    {"id": 3, "n": "PLASMA", "c": (0, 200, 255), "p": 120, "ab": "TimeStop", "desc": "Click Der: Matrix Time"},
    {"id": 4, "n": "GHOST", "c": (200, 200, 255), "p": 250, "ab": "Ghost", "desc": "Atraviesa 1 muro/tiro"},
    {"id": 99, "n": "THE ONE", "c": (255, 255, 255), "p": 9999, "ab": "Legendary", "desc": "La anomalía perfecta"} 
]

LOGROS_DEF = [
    {"id": "first_win", "t": "HACKER INICIADO", "desc": "Completa 1 nivel", "r": 5, "cond": lambda d: d["total_victorias"] >= 1},
    {"id": "veteran", "t": "VETERANO", "desc": "Completa 10 niveles", "r": 10, "cond": lambda d: d["total_victorias"] >= 10},
    {"id": "sniper", "t": "FRANCOTIRADOR", "desc": "Dispara 50 veces", "r": 5, "cond": lambda d: d["total_tiros"] >= 50},
    {"id": "rich", "t": "MINERO DE DATOS", "desc": "Ten 20 estrellas", "r": 5, "cond": lambda d: d["estrellas"] >= 20},
    {"id": "fail", "t": "ERROR DE CAPA 8", "desc": "Muere 5 veces", "r": 3, "cond": lambda d: d["total_muertes"] >= 5}
]

SHAKE_AMPLITUDE = 0

def io_datos(accion="load"):
    global DATOS
    try:
        if accion == "load":
            if os.path.exists(ARCHIVO_SAVE):
                try:
                    with open(ARCHIVO_SAVE, "r") as f: 
                        leido = json.load(f)
                        DATOS.update(leido)
                        if "mejoras" not in DATOS: DATOS["mejoras"] = {"ammo": 0, "aim": 0, "luck": 0}
                except (json.JSONDecodeError, ValueError): pass
        elif accion == "save":
            with open(ARCHIVO_SAVE, "w") as f: json.dump(DATOS, f)
    except Exception: pass
io_datos("load")

# --- AUDIO ENGINE ---
class AudioManager:
    def __init__(self):
        self.sounds = {}
        self.last_beat_time = 0
        self.beat_step = 0
        self.melody_step = 0
        self.bpm = 120
        self.pulse_val = 0 
        self.mode = "EXPLORE" 
        self.generate_assets()

    def make_sound(self, freq_start, freq_end, duration, vol=0.5, type="sine", fm_mod=0, decay_factor=0.9):
        sample_rate = 44100
        n_samples = int(sample_rate * duration)
        buf = bytearray()
        period = 2 * math.pi
        for i in range(n_samples):
            t = i / sample_rate
            progress = i / n_samples
            current_freq = freq_start + (freq_end - freq_start) * progress
            modulator = 0
            if fm_mod > 0: modulator = math.sin(t * fm_mod * period) * 500
            phase = t * (current_freq + modulator) * period
            val = 0
            if type == "sine": val = math.sin(phase)
            elif type == "square": val = 0.6 if math.sin(phase) > 0 else -0.6
            elif type == "saw": val = 2.0 * (t * current_freq - math.floor(t * current_freq + 0.5)) - 1.0
            elif type == "noise": val = random.random() * 2.0 - 1.0
            elif type == "kick": val = math.sin(phase) * (1 - progress)
            elif type == "plucky": val = math.sin(phase) * (1-progress)**4 
            envelope = 1.0
            if progress < 0.05: envelope = progress * 20 
            else: envelope = (1.0 - progress) ** decay_factor
            final_val = int(val * envelope * vol * 32767)
            final_val = max(-32767, min(32767, final_val))
            packed = struct.pack('<h', final_val)
            buf.extend(packed); buf.extend(packed)
        return pygame.mixer.Sound(bytes(buf))

    def generate_assets(self):
        self.sounds['jump'] = self.make_sound(300, 600, 0.15, 0.4, "saw")
        self.sounds['hit'] = self.make_sound(150, 100, 0.05, 0.5, "square")
        self.sounds['win'] = self.make_sound(440, 880, 0.4, 0.4, "sine")
        self.sounds['die'] = self.make_sound(100, 20, 0.5, 0.6, "noise")
        self.sounds['coin'] = self.make_sound(1200, 1800, 0.1, 0.3, "sine")
        self.sounds['warp'] = self.make_sound(200, 800, 0.3, 0.4, "sine")
        self.sounds['powerup'] = self.make_sound(600, 1200, 0.3, 0.4, "square")
        self.sounds['achieve'] = self.make_sound(800, 1200, 0.4, 0.5, "square", fm_mod=20)
        self.sounds['ui'] = self.make_sound(2000, 2000, 0.05, 0.2, "sine")
        self.sounds['glass'] = self.make_sound(1000, 500, 0.1, 0.3, "square")
        self.sounds['drone'] = self.make_sound(150, 100, 0.15, 0.2, "saw")
        self.sounds['boss_hit'] = self.make_sound(100, 50, 0.2, 0.7, "saw")
        self.sounds['shoot'] = self.make_sound(400, 200, 0.15, 0.3, "square")
        self.sounds['break'] = self.make_sound(200, 50, 0.15, 0.5, "noise")
        self.sounds['timestop'] = self.make_sound(100, 0, 0.8, 0.5, "sine")
        self.sounds['alarm'] = self.make_sound(800, 600, 0.5, 0.6, "saw", fm_mod=10)
        
        self.sounds['m_kick'] = self.make_sound(180, 50, 0.1, 0.9, "kick", decay_factor=3.0)
        self.sounds['m_snare'] = self.make_sound(1200, 200, 0.12, 0.5, "noise")
        self.sounds['m_hat'] = self.make_sound(8000, 9000, 0.04, 0.2, "noise", decay_factor=5)
        self.sounds['m_bass'] = self.make_sound(55, 55, 0.2, 0.7, "saw", fm_mod=1)
        freqs = {"E5": 659, "Ds5": 622, "B4": 493, "D5": 587, "C5": 523, "A4": 440, "E4": 329}
        for name, freq in freqs.items():
            self.sounds[f'note_{name}'] = self.make_sound(freq, freq, 0.2, 0.4, "plucky")
        self.sounds['hit_low'] = self.make_sound(110, 110, 0.1, 0.7, "saw", decay_factor=1.0)
        self.sounds['hit_hi'] = self.make_sound(220, 220, 0.1, 0.6, "saw", decay_factor=1.0)

    def play(self, name):
        vol_factor = CONFIG["vol_sfx"] / 10.0
        if vol_factor > 0 and name in self.sounds:
            snd = self.sounds[name]
            snd.set_volume(vol_factor)
            snd.play()

    def update_music(self):
        self.pulse_val *= 0.9 
        vol_factor = CONFIG["vol_musica"] / 10.0
        if vol_factor <= 0: return
        now = pygame.time.get_ticks()
        step_duration = (60000 / self.bpm) / 4 
        if now - self.last_beat_time >= step_duration:
            self.last_beat_time = now
            step = self.beat_step % 16
            if self.mode == "EXPLORE":
                if step in [0, 8]: self.play_music_sample('m_kick', vol_factor); self.pulse_val = 1.0
                if step in [4, 12]: self.play_music_sample('m_snare', vol_factor)
                if step % 2 == 0: self.play_music_sample('m_hat', vol_factor * 0.6)
                if step in [2, 6, 10, 14]: self.play_music_sample('m_bass', vol_factor * 0.7)
                melody = ["E5", "Ds5", "E5", "Ds5", "E5", "B4", "D5", "C5", "A4", None, "E4", "A4", "C5", "E5", "A4", None]
                note = melody[self.melody_step % 16]
                if note and step % 2 == 0:
                    self.play_music_sample(f'note_{note}', vol_factor * 0.6)
            elif self.mode == "BATTLE":
                if step % 4 == 0:
                    self.play_music_sample('m_kick', vol_factor * 1.0)
                    self.pulse_val = 1.0
                if step in [0, 1, 2,  4, 5, 6,  8, 9, 10,  12, 13, 14]:
                    tone = 'hit_low' if step < 8 else 'hit_hi'
                    self.play_music_sample(tone, vol_factor * 0.8)
                if step in [4, 12]:
                    self.play_music_sample('m_snare', vol_factor * 0.8)
            self.beat_step += 1
            if self.beat_step % 2 == 0: self.melody_step += 1

    def play_music_sample(self, name, vol):
        if name in self.sounds:
            s = self.sounds[name]
            s.set_volume(vol)
            s.play()

AUDIO = AudioManager()

def sound(name):
    AUDIO.play(name)

class Visuals:
    def __init__(self):
        self.cache = {}
        try:
            self.font_big = pygame.font.SysFont("Consolas", int(45*FACTOR), bold=True)
            self.font_huge = pygame.font.SysFont("Consolas", int(70*FACTOR), bold=True)
            self.font_ui = pygame.font.SysFont("Consolas", int(20*FACTOR), bold=True)
            self.font_small = pygame.font.SysFont("Consolas", int(14*FACTOR), bold=True)
        except:
            self.font_big = pygame.font.SysFont("Arial", int(45*FACTOR), bold=True)
            self.font_huge = pygame.font.SysFont("Arial", int(70*FACTOR), bold=True)
            self.font_ui = pygame.font.SysFont("Arial", int(20*FACTOR), bold=True)
            self.font_small = pygame.font.SysFont("Arial", int(14*FACTOR), bold=True)

    def draw_glitch_title(self, surf, text, x, y, color=None):
        if color is None: color = COLORES["NEON"]
        if text == "MATRIX DUNK":
            self.draw_glitch_text(surf, "MATRIX", x + 20*FACTOR, y - 40*FACTOR, color, size="huge")
            self.draw_glitch_text(surf, "DUNK", x + 40*FACTOR, y + 40*FACTOR, COLORES["BLANCO"], size="huge")
        else:
            self.draw_glitch_text(surf, text, x, y, color, size="big")

    def draw_glitch_text(self, surf, text, x, y, color, size="big"):
        font = self.font_huge if size == "huge" else self.font_big
        off_x = random.randint(-3, 3) if random.random() < 0.2 else 0
        off_y = random.randint(-3, 3) if random.random() < 0.2 else 0
        if random.random() < 0.1:
            t_r = font.render(text, True, (255, 0, 0))
            surf.blit(t_r, (x - 5 + off_x, y + off_y))
            t_b = font.render(text, True, (0, 255, 255))
            surf.blit(t_b, (x + 5 + off_x, y + off_y))
        t_main = font.render(text, True, color)
        surf.blit(t_main, (x + off_x, y + off_y))
        if random.random() < 0.05:
            ly = y + random.randint(0, t_main.get_height())
            pygame.draw.line(surf, color, (x, ly), (x + t_main.get_width(), ly), 2)

    def draw_neon_rect(self, surf, rect, color, fill=False):
        c = 8 * FACTOR
        pts = [(rect.left+c, rect.top), (rect.right-c, rect.top), (rect.right, rect.top+c), (rect.right, rect.bottom-c),
               (rect.right-c, rect.bottom), (rect.left+c, rect.bottom), (rect.left, rect.bottom-c), (rect.left, rect.top+c)]
        if fill:
            s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            pygame.draw.polygon(s, (*color, 50), [(p[0]-rect.x, p[1]-rect.y) for p in pts])
            surf.blit(s, (rect.x, rect.y))
        pygame.draw.polygon(surf, color, pts, 2)

    def draw_glow_circle(self, surf, x, y, radius, color):
        s = pygame.Surface((int(radius*2.5), int(radius*2.5)), pygame.SRCALPHA)
        pygame.draw.circle(s, (*color, 60), (int(radius*1.25), int(radius*1.25)), int(radius))
        pygame.draw.circle(s, (*color, 200), (int(radius*1.25), int(radius*1.25)), int(radius*0.6))
        pygame.draw.circle(s, (255, 255, 255, 255), (int(radius*1.25), int(radius*1.25)), int(radius*0.4))
        surf.blit(s, (x - radius*1.25, y - radius*1.25), special_flags=pygame.BLEND_ADD)

    def get_texture(self, w, h, color, type="grid"):
        w, h = int(w), int(h)
        key = (w, h, color, type)
        if key in self.cache: return self.cache[key]
        s = pygame.Surface((w, h)); s.fill((0, 15, 0))
        if type == "grid":
            step = int(10 * FACTOR)
            c_dark = (color[0]//3, color[1]//3, color[2]//3)
            for x in range(0, w, step): pygame.draw.line(s, c_dark, (x, 0), (x, h), 1)
            for y in range(0, h, step): pygame.draw.line(s, c_dark, (0, y), (w, y), 1)
            pygame.draw.rect(s, color, (0, 0, w, h), 2)
        elif type == "danger":
            s.fill((40, 0, 0)); step = int(20 * FACTOR)
            for i in range(-h, w, step): pygame.draw.line(s, color, (i, 0), (i+h, h), 4)
            pygame.draw.rect(s, color, (0,0,w,h), 2)
        elif type == "firewall":
            s.fill((20, 0, 0))
            for y in range(0, h, int(5*FACTOR)): pygame.draw.line(s, (255, 0, 0), (0, y), (w, y), 1)
            pygame.draw.rect(s, (255, 0, 0), (0, 0, w, h), 4)
        elif type == "glass":
            s.fill((0, 20, 30))
            pygame.draw.rect(s, color, (0,0,w,h), 2)
            pygame.draw.line(s, color, (0,0), (w,h), 1)
            s.set_alpha(150)
        elif type == "destruct": 
            s.fill((50, 50, 50))
            pygame.draw.rect(s, (100,100,100), (0,0,w,h), 2)
            pygame.draw.line(s, (0,0,0), (0,0), (w,h), 2)
            pygame.draw.line(s, (0,0,0), (w,0), (0,h), 2)
        elif type == "boss":
            s.fill((30, 0, 10))
            pygame.draw.rect(s, COLORES["BOSS"], (0,0,w,h), 4)
            pygame.draw.line(s, COLORES["BOSS"], (0,0), (w,h), 2)
            pygame.draw.line(s, COLORES["BOSS"], (w,0), (0,h), 2)
        self.cache[key] = s
        return s

    def draw_star(self, surf, x, y, size, color, rot):
        points = []
        for i in range(10):
            angle = math.radians(i * 36 + rot)
            r = size if i % 2 == 0 else size / 2
            px = x + math.cos(angle) * r
            py = y + math.sin(angle) * r
            points.append((px, py))
        pygame.draw.polygon(surf, color, points)

    def draw_drone(self, surf, x, y):
        t = pygame.time.get_ticks() * 0.01
        points = [
            (x + math.cos(t)*15*FACTOR, y + math.sin(t)*15*FACTOR),
            (x + math.cos(t + 2.09)*15*FACTOR, y + math.sin(t + 2.09)*15*FACTOR),
            (x + math.cos(t + 4.18)*15*FACTOR, y + math.sin(t + 4.18)*15*FACTOR)
        ]
        pygame.draw.polygon(surf, COLORES["DRONE"], points, 2)
        pygame.draw.circle(surf, (255,0,0), (int(x), int(y)), 4*FACTOR)
    
    def draw_cyber_grid(self, surf, scroll):
        horizon = ALTO * 0.4
        gap = 40 * FACTOR
        pulse = int(AUDIO.pulse_val * 100)
        grid_c = (0, 40 + pulse, 40 + pulse) 
        cx = ANCHO // 2
        for i in range(-10, 11):
            offset = i * gap * 4
            x_bottom = cx + offset * 3
            x_top = cx + offset * 0.1
            pygame.draw.line(surf, grid_c, (x_top, horizon), (x_bottom, ALTO), 1)
        offset_y = (pygame.time.get_ticks() * 0.1) % gap
        y = ALTO
        depth = 0
        while y > horizon:
            y_screen = ALTO - (depth * depth * 3 * FACTOR) + offset_y
            if y_screen < ALTO and y_screen > horizon:
                pygame.draw.line(surf, grid_c, (0, y_screen), (ANCHO, y_screen), 1)
            depth += 0.5
            y = y_screen

GFX = Visuals()

class FloatingText:
    def __init__(self, x, y, text, color):
        self.x, self.y = x, y
        self.text = text
        self.color = color
        self.life = 60
        self.alpha = 255
        self.vy = -2 * FACTOR 

    def update(self):
        self.y += self.vy
        self.vy *= 0.9 
        self.life -= 1
        self.alpha = max(0, int(255 * (self.life / 60)))

    def draw(self, s):
        if self.life > 0:
            t = GFX.font_ui.render(str(self.text), True, self.color)
            t.set_alpha(self.alpha)
            s.blit(t, (self.x, self.y))

class NotificationSystem:
    def __init__(self):
        self.queue = []
        self.timer = 0
        self.text = ""
    
    def add(self, txt):
        self.queue.append(txt)
    
    def update_draw(self, surf):
        if self.timer > 0:
            self.timer -= 1
            r = pygame.Rect(ANCHO//2 - 200*FACTOR, 10*FACTOR, 400*FACTOR, 40*FACTOR)
            pygame.draw.rect(surf, (0,0,0), r)
            pygame.draw.rect(surf, COLORES["ACHIEVE"], r, 2)
            t = GFX.font_small.render(self.text, True, COLORES["ACHIEVE"])
            surf.blit(t, (r.centerx - t.get_width()//2, r.centery - t.get_height()//2))
        elif len(self.queue) > 0:
            self.text = self.queue.pop(0)
            self.timer = 180
            sound('achieve')

NOTIFIER = NotificationSystem()

def check_achievements():
    for l in LOGROS_DEF:
        if l["id"] not in DATOS["logros"]:
            if l["cond"](DATOS):
                DATOS["logros"].append(l["id"])
                reward = l.get("r", 0)
                DATOS["estrellas"] += reward
                NOTIFIER.add(f"LOGRO: {l['t']} (+{reward} $)")
                io_datos("save")

# --- MATRIX RAIN OPTIMIZADA ---
class MatrixRain:
    def __init__(self):
        self.drops = []
        cols = int(ANCHO / (15 * FACTOR))
        self.trail_surf = pygame.Surface((2*FACTOR, 15*FACTOR))
        self.trail_surf.set_alpha(50)
        self.trail_surf.fill((0, 255, 50))
        for i in range(cols):
            self.drops.append({
                'x': i * 15 * FACTOR, 
                'y': random.randint(-ALTO, ALTO), 
                'speed': random.uniform(2, 8) * FACTOR,
                'len': random.randint(5, 15) * FACTOR 
            })

    def update(self, s):
        for d in self.drops:
            d['y'] += d['speed']
            if d['y'] > ALTO: 
                d['y'] = random.randint(-100, -10)
                d['speed'] = random.uniform(2, 8) * FACTOR
            pygame.draw.rect(s, (0, 50, 0), (d['x'], d['y'] + d['len'], 2*FACTOR, 2*FACTOR))
            s.blit(self.trail_surf, (d['x'], d['y']))

class Pelota:
    def __init__(self, x, y):
        self.start = (x, y)
        self.trail = deque(maxlen=20) 
        self.portal_cd = 0
        self.bounces = 0
        self.touched_wall = False 
        self.timestop_max = 100.0
        self.timestop_val = 100.0
        self.timestop_recharge = 0.5
        self.reset()

    def reset(self):
        self.x, self.y = self.start
        self.vx, self.vy = 0, 0
        self.r = int(11 * FACTOR)
        self.moving = False
        self.grounded = False
        self.portal_cd = 0
        self.ghost_mode = False
        self.bounces = 0
        self.touched_wall = False
        self.trail.clear()
        self.skin_id = DATOS["skin_act"]
        self.skin_data = next((s for s in SKINS if s["id"] == self.skin_id), SKINS[0])
        self.skin_c = self.skin_data["c"]
        self.ability = self.skin_data["ab"]
        self.timestop_val = self.timestop_max
        if self.ability == "Ghost":
            self.ghost_mode = True
            self.skin_c = (200, 200, 255)

    def launch(self, fx, fy):
        mult = 1.2 if self.ability == "Power" else 1.0
        self.vx, self.vy = fx * mult, fy * mult
        self.moving = True; self.grounded = False; self.trail.clear()
        self.bounces = 0; self.touched_wall = False
        DATOS["total_tiros"] += 1
        sound('jump')

    def update(self, obs_list, stars, parts, portals, gravs, powers, drones, bosses, turrets, projectiles, float_texts, dt):
        global SHAKE_AMPLITUDE
        
        if self.ability == "TimeStop":
            if self.timestop_val < self.timestop_max:
                self.timestop_val += self.timestop_recharge
        
        if not self.moving: return "nada"
        if self.portal_cd > 0: self.portal_cd -= 1
        self.grounded = False
        
        if self.ability == "Magnet":
            for s in stars:
                if s.act:
                    dx, dy = self.x - s.rect.centerx, self.y - s.rect.centery
                    dist = math.hypot(dx, dy)
                    if dist < 250 * FACTOR:
                        s.rect.centerx += (dx/dist) * 5 * FACTOR
                        s.rect.centery += (dy/dist) * 5 * FACTOR

        self.vy += 0.45 * FACTOR * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        
        if len(self.trail) == 0 or math.hypot(self.x-self.trail[-1][0], self.y-self.trail[-1][1]) > 5*FACTOR:
            self.trail.append((self.x, self.y))

        for g in gravs:
            dx = g.x - self.x; dy = g.y - self.y; dist = math.hypot(dx, dy)
            if dist < g.radio * 1.5: 
                force = (g.fuerza * 2000 * FACTOR) / (dist * dist + 5)
                self.vx += (dx/dist) * force * dt
                self.vy += (dy/dist) * force * dt

        rect = pygame.Rect(self.x-self.r, self.y-self.r, self.r*2, self.r*2)
        if self.portal_cd == 0:
            for p in portals:
                if rect.colliderect(p.rect):
                    target = p.link
                    if target:
                        self.x = target.rect.centerx; self.y = target.rect.centery
                        sound('warp'); self.portal_cd = 30; self.vx *= 1.2; self.vy *= 1.2
                        spawn_parts(self.x, self.y, p.color, parts)

        for s in stars:
            if s.act and rect.colliderect(s.rect):
                s.act = False; sound('coin')
                spawn_parts(s.rect.centerx, s.rect.centery, COLORES["GOLD"], parts)
                float_texts.append(FloatingText(s.rect.x, s.rect.y, "+1", COLORES["GOLD"]))
                return "star"
        
        for d in drones:
            if math.hypot(self.x - d.x, self.y - d.y) < self.r + 15*FACTOR:
                sound('die'); SHAKE_AMPLITUDE = 20; spawn_parts(self.x, self.y, COLORES["PELIGRO"], parts)
                return "die"
        
        for proj in projectiles:
            if rect.colliderect(proj.rect):
                 sound('die'); SHAKE_AMPLITUDE = 20; spawn_parts(self.x, self.y, COLORES["PELIGRO"], parts)
                 return "die"

        for b in bosses:
            if b.rect.colliderect(rect):
                 if self.ability == "Ghost": pass
                 sound('boss_hit'); SHAKE_AMPLITUDE = 15
                 self.vx *= -1; self.vy *= -1
                 spawn_parts(self.x, self.y, COLORES["BOSS"], parts)
                 self.touched_wall = True
                 dmg = 10
                 if self.ability == "Power": dmg = 20
                 b.hp -= dmg
                 float_texts.append(FloatingText(b.rect.centerx, b.rect.top, f"-{dmg}", (255, 100, 100)))
                 if b.hp <= 0:
                     bosses.remove(b)
                     obs_list.append(Obstaculo(b.rect.x, b.rect.y, b.rect.w, b.rect.h, "meta"))
                     sound('win')

        for p in powers:
            if p.active and rect.colliderect(p.rect):
                p.active = False; sound('powerup')
                spawn_parts(p.rect.centerx, p.rect.centery, p.color, parts)
                if p.type == "ammo": return "ammo"
                if p.type == "ghost": self.ghost_mode = True; self.skin_c = COLORES["PELIGRO"]

        for o in obs_list:
            if o.tipo == "fantasma" and not o.active_state: continue
            
            if o.tipo == "triangle_up":
                if rect.colliderect(o.rect):
                    rel_x = self.x - o.rect.x
                    rel_y = self.y - o.rect.y
                    if rel_y > (o.rect.h - rel_x):
                         sound('hit'); self.touched_wall = True
                         temp = self.vx
                         self.vx = -self.vy * 0.9
                         self.vy = -temp * 0.9
                         self.x -= 5 * FACTOR
                         self.y -= 5 * FACTOR
                         continue

            if rect.colliderect(o.rect):
                if o.tipo == "meta": 
                    sound('win'); SHAKE_AMPLITUDE = 10
                    if not self.touched_wall: return "swish" 
                    if self.bounces >= 3: return "win_combo"
                    return "win"
                
                if o.tipo == "muerte" or o.tipo == "firewall" or (o.tipo == "laser" and o.active_state): 
                    sound('die'); SHAKE_AMPLITUDE = 20; return "die"
                
                if o.tipo == "laser" and not o.active_state: continue
                
                if self.ghost_mode and o.tipo in ["pared", "movil", "cristal", "destructible", "triangle_up"]:
                    if o.tipo in ["cristal", "destructible"]: spawn_parts(o.rect.centerx, o.rect.centery, o.color, parts)
                    o.rect.x = -1000; 
                    if self.ability != "Ghost": 
                        self.ghost_mode = False; 
                        actual_skin = next((s for s in SKINS if s["id"] == DATOS["skin_act"]), SKINS[0])
                        self.skin_c = actual_skin["c"]
                    sound('hit'); spawn_parts(self.x, self.y, COLORES["PELIGRO"], parts); continue

                if o.tipo == "cristal" or o.tipo == "destructible":
                    if o.tipo == "cristal": sound('glass')
                    else: sound('break')
                    spawn_parts(o.rect.centerx, o.rect.centery, o.color, parts)
                    o.rect.x = -2000
                    SHAKE_AMPLITUDE = 5
                    self.vx *= 0.8; self.vy *= 0.8 
                    continue

                dx = self.x - o.rect.centerx; dy = self.y - o.rect.centery
                w_half = o.rect.w / 2 + self.r
                h_half = o.rect.h / 2 + self.r
                
                if abs(dx) < w_half and abs(dy) < h_half:
                    sound('hit'); self.touched_wall = True
                    self.bounces += 1
                    if math.hypot(self.vx, self.vy) > 10*FACTOR: SHAKE_AMPLITUDE = 5
                    bounce = 1.3 if o.tipo == "trampolin" else 0.6
                    if self.ability == "Legendary": bounce = 1.1
                    ox = w_half - abs(dx); oy = h_half - abs(dy)
                    if ox < oy:
                        if dx > 0: self.x += ox
                        else: self.x -= ox
                        self.vx *= -bounce
                    else:
                        if dy > 0: self.y += oy
                        else: self.y -= oy
                        if dy < 0 and self.vy > 0:
                             if self.vy < 3.0 * FACTOR and o.tipo != "trampolin":
                                 self.vy = 0; self.vx = 0; self.grounded = True; self.moving = False
                             else: self.vy *= -bounce
                        else: self.vy *= -bounce

        if self.x < self.r: self.x=self.r; self.vx*=-0.7; self.touched_wall=True
        if self.x > ANCHO-self.r: self.x=ANCHO-self.r; self.vx*=-0.7; self.touched_wall=True
        if self.y < self.r: self.y=self.r; self.vy*=-0.5; self.touched_wall=True
        if self.y > ALTO+100: sound('die'); SHAKE_AMPLITUDE = 20; return "die"
        self.vx *= 0.99
        return "nada"

    def draw(self, s):
        points = list(self.trail)
        if len(points) > 1:
            skin_type = self.ability
            if skin_type == "Legendary":
                for i, (px, py) in enumerate(points):
                    color = (255, 255, 255) if i % 2 == 0 else (0, 255, 0)
                    pygame.draw.line(s, color, (px, py), (px, py+5), 2)
            elif skin_type == "TimeStop":
                for i, (px, py) in enumerate(points):
                    alpha = int(255 * (i/len(points)))
                    sz = int(self.r * (i/len(points)))
                    rect_surf = pygame.Surface((sz*2, sz*2), pygame.SRCALPHA)
                    pygame.draw.rect(rect_surf, (*self.skin_c, alpha), (0,0,sz*2,sz*2), 1)
                    s.blit(rect_surf, (px-sz, py-sz))
            elif skin_type == "Ghost":
                for i, (px, py) in enumerate(points):
                    if i % 3 == 0: 
                        radius = int(self.r * (i/len(points)))
                        pygame.draw.circle(s, (*self.skin_c, 100), (int(px), int(py)), radius, 1)
            elif skin_type == "Magnet":
                for i, (px, py) in enumerate(points):
                    if i % 2 == 0:
                        pygame.draw.circle(s, (255, 255, 200), (int(px + random.randint(-2,2)), int(py + random.randint(-2,2))), 2)
            elif skin_type == "Power":
                for i in range(len(points)-1):
                    pygame.draw.line(s, (255, 100, 0), points[i], points[i+1], int(self.r * (i/len(points))))
            else:
                for i in range(len(points)-1):
                    width = int(self.r * (i / len(points)))
                    pygame.draw.line(s, self.skin_c, points[i], points[i+1], width)

        GFX.draw_glow_circle(s, int(self.x), int(self.y), self.r, self.skin_c)

    def predict(self, start_vx, start_vy, obstacles):
        points = []
        sim_x, sim_y = self.x, self.y; sim_vx, sim_vy = start_vx, start_vy
        bounces_sim = 0
        bonus_aim = DATOS["mejoras"]["aim"] * 20
        limit = (100 if self.ability == "Legendary" else 50) + bonus_aim
        for _ in range(limit): 
            sim_vy += 0.45 * FACTOR; sim_x += sim_vx; sim_y += sim_vy
            if sim_x < 0 or sim_x > ANCHO: sim_vx *= -0.7
            points.append((sim_x, sim_y))
            r = pygame.Rect(sim_x-5, sim_y-5, 10, 10); hit = False
            for o in obstacles:
                if o.tipo not in ["meta", "star", "laser", "firewall"] and r.colliderect(o.rect):
                    if o.tipo == "fantasma" and not o.active_state: continue
                    if abs(sim_x - o.rect.centerx) > abs(sim_y - o.rect.centery): sim_vx *= -0.8
                    else: sim_vy *= -0.8
                    bounces_sim += 1
                    hit = True
                    break 
            if bounces_sim > (2 if self.ability == "Legendary" else 1): break
        return points

class Obstaculo:
    def __init__(self, x, y, w, h, tipo):
        self.rect = pygame.Rect(int(x), int(y), int(w), int(h))
        self.tipo = tipo; self.base_x = x; self.dir = 1; self.timer = 0; self.active_state = True
        self.move_meta = False
        
        c = COLORES["NEON"]; style = "grid"
        if tipo == "muerte": c = COLORES["PELIGRO"]; style = "danger"
        elif tipo == "meta": c = COLORES["META"]; style = "solid"
        elif tipo == "trampolin": c = (255, 0, 255)
        elif tipo == "fantasma": c = (100, 255, 100)
        elif tipo == "firewall": c = COLORES["PELIGRO"]; style = "firewall"
        elif tipo == "cristal": c = COLORES["CRISTAL"]; style = "glass"
        elif tipo == "destructible": c = COLORES["DESTRUCT"]; style = "destruct" 
        elif tipo == "triangle_up": c = COLORES["NEON"]; style = "none"
        
        if tipo not in ["meta", "laser", "triangle_up"]: self.tex = GFX.get_texture(w, h, c, style)
        self.color = c 

    def update(self):
        if self.tipo == "movil":
            self.rect.x += 2 * FACTOR * self.dir
            if abs(self.rect.x - self.base_x) > 100 * FACTOR: self.dir *= -1
        
        if self.tipo == "meta" and self.move_meta:
            self.rect.x += 3 * FACTOR * self.dir
            if self.rect.x < 50*FACTOR or self.rect.x > ANCHO - 100*FACTOR: self.dir *= -1

        if self.tipo == "firewall": self.rect.y += 0.5 * FACTOR
        if self.tipo in ["fantasma", "laser"]:
            self.timer += 1
            if self.timer > 120: self.timer = 0; self.active_state = not self.active_state

    def draw(self, s):
        if self.tipo == "meta":
            cx, cy = self.rect.center; t = pygame.time.get_ticks() * 0.005
            r = self.rect.w//2 + math.sin(t)*5
            GFX.draw_glow_circle(s, cx, cy, int(r), COLORES["META"])
            for i in range(4):
                ang = t + i * (math.pi/2); ex = cx + math.cos(ang) * 25 * FACTOR; ey = cy + math.sin(ang) * 25 * FACTOR
                pygame.draw.line(s, COLORES["META"], (cx,cy), (ex,ey), 2)
        elif self.tipo == "laser":
            pygame.draw.rect(s, COLORES["LASER_EMIT"], (self.rect.x, self.rect.y, 8*FACTOR, self.rect.h))
            pygame.draw.rect(s, COLORES["LASER_EMIT"], (self.rect.right - 8*FACTOR, self.rect.y, 8*FACTOR, self.rect.h))
            if self.active_state: 
                h_beam = int(self.rect.h * 0.6)
                y_beam = self.rect.centery - h_beam // 2
                pulse = abs(math.sin(pygame.time.get_ticks() * 0.01)) * 100
                c_beam = (255, pulse, pulse)
                pygame.draw.rect(s, (255, 255, 255), (self.rect.x + 5, self.rect.centery - 2, self.rect.w - 10, 4))
                s_beam = pygame.Surface((self.rect.w - 16*FACTOR, h_beam), pygame.SRCALPHA)
                s_beam.fill((*c_beam, 150))
                s.blit(s_beam, (self.rect.x + 8*FACTOR, y_beam))
            
        elif self.tipo == "fantasma":
            if self.active_state: s.blit(self.tex, self.rect)
            else: pygame.draw.rect(s, (0, 50, 0), self.rect, 1)
        elif self.tipo == "triangle_up": 
            pts = [(self.rect.bottomleft), (self.rect.bottomright), (self.rect.topright)]
            pygame.draw.polygon(s, COLORES["NEON"], pts)
            pygame.draw.polygon(s, (0,50,0), pts, 2)
        else: s.blit(self.tex, self.rect)

class Drone:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.speed = 1.5 * FACTOR
        self.timer = 0
    
    def update(self, target_x, target_y):
        self.timer += 1
        if self.timer % 60 == 0: sound('drone') 
        dx, dy = target_x - self.x, target_y - self.y
        dist = math.hypot(dx, dy)
        if dist > 0:
            self.x += (dx/dist) * self.speed
            self.y += (dy/dist) * self.speed
            
    def draw(self, s):
        GFX.draw_drone(s, self.x, self.y)

class Bullet:
    def __init__(self, x, y, angle):
        self.x, self.y = x, y
        self.vx = math.cos(angle) * 5 * FACTOR
        self.vy = math.sin(angle) * 5 * FACTOR
        self.rect = pygame.Rect(x, y, 10*FACTOR, 10*FACTOR)
        self.life = 100
        
    def update(self):
        self.x += self.vx; self.y += self.vy
        self.rect.x = int(self.x); self.rect.y = int(self.y)
        self.life -= 1
        
    def draw(self, s):
        pygame.draw.circle(s, COLORES["PELIGRO"], (self.rect.centerx, self.rect.centery), 5*FACTOR)

class Turret:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.last_shot = 0
        self.angle = 0
        
    def update(self, px, py, bullets):
        self.angle = math.atan2(py - self.y, px - self.x)
        now = pygame.time.get_ticks()
        if now - self.last_shot > 2500: # Dispara cada 2.5s
            self.last_shot = now
            bullets.append(Bullet(self.x, self.y, self.angle))
            sound('shoot')
            
    def draw(self, s):
        pygame.draw.circle(s, COLORES["TURRET"], (int(self.x), int(self.y)), 15*FACTOR)
        end_x = self.x + math.cos(self.angle) * 25*FACTOR
        end_y = self.y + math.sin(self.angle) * 25*FACTOR
        pygame.draw.line(s, COLORES["TURRET"], (self.x, self.y), (end_x, end_y), 4)

class Boss:
    def __init__(self, level):
        self.type = (level // 10) % 3 
        self.rect = pygame.Rect(ANCHO//2 - 60*FACTOR, 200*FACTOR, 120*FACTOR, 40*FACTOR)
        self.timer = 0
        self.dir = 1
        self.tex = GFX.get_texture(120*FACTOR, 40*FACTOR, COLORES["BOSS"], "boss")
        self.shoot_timer = 0
        self.speed = 2 + (level * 0.05)
        self.max_hp = 100 + (level * 10)
        self.hp = self.max_hp
        
        if level == 50: self.name = "THE GUARDIAN"
        elif level == 100: self.name = "THE ARCHITECT"
        else: self.name = f"SYSTEM GUARD V{level//10}.0"
    
    def update(self, player, projectiles):
        self.timer += 1
        
        if self.type == 2: 
             if self.timer % 120 == 0:
                self.rect.x = random.randint(0, int(ANCHO - self.rect.w))
                self.rect.y = random.randint(100, 300) * FACTOR
        else:
            target_x = player.x - self.rect.w // 2
            if self.rect.x < target_x: self.rect.x += self.speed
            elif self.rect.x > target_x: self.rect.x -= self.speed
            if self.rect.left < 0: self.rect.left = 0
            if self.rect.right > ANCHO: self.rect.right = ANCHO

        self.shoot_timer += 1
        shoot_delay = max(40, 120 - int(self.speed * 10)) 
        
        if self.shoot_timer > shoot_delay:
            self.shoot_timer = 0
            angle = math.atan2(player.y - self.rect.centery, player.x - self.rect.centerx)
            projectiles.append(Bullet(self.rect.centerx, self.rect.centery, angle))
            sound('shoot')

    def draw(self, s):
        s.blit(self.tex, self.rect)
        pygame.draw.circle(s, (255, 0, 0), self.rect.center, 10*FACTOR + math.sin(self.timer*0.1)*5)
        
        bar_w = self.rect.w
        bar_h = 5 * FACTOR
        fill = (self.hp / self.max_hp) * bar_w
        pygame.draw.rect(s, (50, 0, 0), (self.rect.x, self.rect.y - 10*FACTOR, bar_w, bar_h))
        pygame.draw.rect(s, COLORES["PELIGRO"], (self.rect.x, self.rect.y - 10*FACTOR, fill, bar_h))
        
        t_name = GFX.font_small.render(self.name, True, COLORES["PELIGRO"])
        s.blit(t_name, (self.rect.centerx - t_name.get_width()//2, self.rect.y - 30*FACTOR))

class PowerUp:
    def __init__(self, x, y, type):
        self.rect = pygame.Rect(x, y, 30*FACTOR, 30*FACTOR); self.type = type
        self.color = COLORES["POWER_AMMO"] if type == "ammo" else COLORES["POWER_GHOST"]
        self.active = True; self.anim = 0
    def draw(self, s):
        if self.active:
            self.anim += 0.1; r = 10 * FACTOR + math.sin(self.anim) * 2
            GFX.draw_glow_circle(s, self.rect.centerx, self.rect.centery, int(r), self.color)

class Star:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 30*FACTOR, 30*FACTOR); self.act = True; self.rot = 0
    def draw(self, s):
        if self.act: self.rot += 2; GFX.draw_star(s, self.rect.centerx, self.rect.centery, 15*FACTOR, COLORES["GOLD"], self.rot)

class Portal:
    def __init__(self, x, y, color):
        self.rect = pygame.Rect(x, y, 40*FACTOR, 60*FACTOR); self.color = color; self.link = None; self.anim = 0
    def draw(self, s):
        self.anim += 0.2
        cx, cy = self.rect.center
        for i in range(5):
            rad = (self.anim * 5 + i * 10) % 30
            pygame.draw.circle(s, self.color, (cx, cy), int(rad * FACTOR), 1)
        pygame.draw.ellipse(s, self.color, self.rect, 2)

class GravityWell:
    def __init__(self, x, y):
        self.x, self.y = x, y; self.radio = 150 * FACTOR; self.fuerza = 5.0; self.anim = 0
    def draw(self, s):
        self.anim += 0.2
        for i in range(6):
            ang = (self.anim + i * 60) * 0.05
            ex = self.x + math.cos(ang) * self.radio
            ey = self.y + math.sin(ang) * self.radio
            pygame.draw.line(s, COLORES["GRAVEDAD"], (self.x, self.y), (ex, ey), 1)
        pygame.draw.circle(s, (0,0,0), (int(self.x), int(self.y)), int(20*FACTOR))
        pygame.draw.circle(s, COLORES["GRAVEDAD"], (int(self.x), int(self.y)), int(20*FACTOR), 2)

class Particle:
    def __init__(self, x, y, c, life=30):
        self.x, self.y, self.c = x, y, c; self.life = life
        self.vx = random.uniform(-3, 3) * FACTOR; self.vy = random.uniform(-3, 3) * FACTOR
    def update(self): self.x += self.vx; self.y += self.vy; self.life -= 1
    def draw(self, s):
        if self.life > 0: 
            sz = max(1, int(2 * (self.life/30)))
            GFX.draw_glow_circle(s, int(self.x), int(self.y), int(3*FACTOR), self.c)

def spawn_parts(x, y, c, l):
    for _ in range(10): l.append(Particle(x, y, c))

class WipeEffect:
    def __init__(self):
        self.active = False; self.timer = 0; self.max_time = 60; self.wait_time = 180; self.phase = 0 

    def start(self):
        self.active = True; self.timer = 0; self.phase = 0

    def update_draw(self, s):
        if not self.active: return False
        h_half = ALTO // 2
        
        if self.phase == 0: 
            self.timer += 1; progress = self.timer / self.max_time
            curr_h = int(h_half * progress)
            pygame.draw.rect(s, (0,0,0), (0, 0, ANCHO, curr_h))
            pygame.draw.line(s, COLORES["NEON"], (0, curr_h), (ANCHO, curr_h), 2)
            pygame.draw.rect(s, (0,0,0), (0, ALTO - curr_h, ANCHO, curr_h))
            pygame.draw.line(s, COLORES["NEON"], (0, ALTO - curr_h), (ANCHO, ALTO - curr_h), 2)
            if progress >= 1.0: self.phase = 1; self.timer = 0; return True 
                
        elif self.phase == 1: 
            self.timer += 1; pygame.draw.rect(s, (0,0,0), (0,0,ANCHO,ALTO))
            pygame.draw.line(s, COLORES["NEON"], (0, h_half), (ANCHO, h_half), 2)
            cx, cy = ANCHO//2, h_half; angle = (pygame.time.get_ticks() * 0.5) % 360
            rect_spinner = pygame.Rect(cx - 30*FACTOR, cy - 30*FACTOR, 60*FACTOR, 60*FACTOR)
            pygame.draw.arc(s, COLORES["NEON"], rect_spinner, math.radians(angle), math.radians(angle + 270), int(4*FACTOR))
            if self.timer >= self.wait_time: self.phase = 2; self.timer = 0
                
        elif self.phase == 2: 
            self.timer += 1; progress = self.timer / self.max_time
            curr_h = int(h_half * (1 - progress))
            pygame.draw.rect(s, (0,0,0), (0, 0, ANCHO, curr_h))
            pygame.draw.line(s, COLORES["NEON"], (0, curr_h), (ANCHO, curr_h), 2)
            pygame.draw.rect(s, (0,0,0), (0, ALTO - curr_h, ANCHO, curr_h))
            pygame.draw.line(s, COLORES["NEON"], (0, ALTO - curr_h), (ANCHO, ALTO - curr_h), 2)
            if progress >= 1.0: self.active = False; return False
        return False

# --- 6. NIVELES ---
def make_level(n):
    obs, stars, portals, gravs, powers, drones, bosses, turrets = [], [], [], [], [], [], [], []
    
    if n % 10 == 0 or n == 50 or n == 100:
        boss = Boss(n)
        bosses.append(boss)
        return obs, stars, portals, gravs, powers, drones, bosses, turrets

    meta = Obstaculo(random.randint(50, int(ANCHO-100)), 100*FACTOR, 50*FACTOR, 50*FACTOR, "meta")
    if n > 15 and random.random() < 0.3: meta.move_meta = True
    obs.append(meta)

    if n >= 3 and random.random() < 0.5:
        p1 = Portal(random.randint(50, int(ANCHO-100)), random.randint(200, int(ALTO-300)), COLORES["PORTAL_A"])
        p2 = Portal(random.randint(50, int(ANCHO-100)), random.randint(200, int(ALTO-300)), COLORES["PORTAL_B"])
        p1.link, p2.link = p2, p1; portals.extend([p1, p2])
    if n >= 5 and random.random() < 0.4: gravs.append(GravityWell(random.randint(100, int(ANCHO-100)), random.randint(200, int(ALTO-300))))
    
    if n >= 4 and random.random() < 0.3:
        drones.append(Drone(random.randint(50, int(ANCHO-50)), random.randint(200, int(ALTO-200))))
    
    if n >= 6 and random.random() < 0.25: 
         turrets.append(Turret(random.randint(50, int(ANCHO-50)), random.randint(100, int(ALTO-300))))

    count = 3 + n//2
    for i in range(count):
        y = 250*FACTOR + i * (120*FACTOR)
        if y > ALTO - 200*FACTOR: break
        tipo = "pared"; rnd = random.random()
        if n > 2 and rnd < 0.15: tipo="fantasma"
        elif n > 3 and rnd < 0.30: tipo="laser"
        elif n > 2 and rnd < 0.45: tipo="muerte"
        elif n > 4 and rnd > 0.80: tipo="trampolin"
        elif n > 1 and rnd > 0.90: tipo="movil"
        elif n > 2 and rnd > 0.75: tipo="cristal"
        elif n > 5 and rnd > 0.85: tipo="destructible" 
        elif n > 8 and rnd > 0.90: tipo="triangle_up"
        
        w = random.randint(int(100*FACTOR), int(200*FACTOR)); h = int(30*FACTOR)
        if tipo == "laser": h = int(10*FACTOR)
        elif tipo == "triangle_up": h = w 
        x = random.randint(20, int(ANCHO-w-20))
        obs.append(Obstaculo(x, y, w, h, tipo))
        if random.random() < 0.5: stars.append(Star(x+w//2-15*FACTOR, y-40*FACTOR))
        if random.random() < 0.1:
            ptype = "ammo" if random.random() < 0.7 else "ghost"
            powers.append(PowerUp(x + w//2, y - 80*FACTOR, ptype))
    return obs, stars, portals, gravs, powers, drones, bosses, turrets

# --- 7. UI ---
def btn(s, r, txt):
    hover = r.collidepoint(pygame.mouse.get_pos())
    c = COLORES["META"] if hover else COLORES["NEON"]
    GFX.draw_neon_rect(s, r, c, fill=hover)
    t = GFX.font_ui.render(txt, True, (0,0,0) if hover else c)
    s.blit(t, (r.centerx-t.get_width()//2, r.centery-t.get_height()//2))
    return r

def draw_stats(s):
    t_title = GFX.font_big.render("HACKER STATS", True, COLORES["META"])
    s.blit(t_title, (ANCHO//2 - t_title.get_width()//2, 80*FACTOR))
    stats = [f"VICTORIAS: {DATOS['total_victorias']}", f"MUERTES: {DATOS['total_muertes']}",
             f"TIROS: {DATOS['total_tiros']}", f"RECORD NIVEL: {DATOS['record']}", f"ESTRELLAS: {DATOS['estrellas']}"]
    for i, stat in enumerate(stats):
        t = GFX.font_ui.render(stat, True, COLORES["BLANCO"])
        s.blit(t, (ANCHO//2 - t.get_width()//2, 200*FACTOR + i*50*FACTOR))

def draw_info(s):
    t_title = GFX.font_big.render("INFORMACION", True, COLORES["NEON"])
    s.blit(t_title, (ANCHO//2 - t_title.get_width()//2, 50*FACTOR))
    
    lines = ["CREADOR: LECAHI", "CO-PILOT: GROK", 
             "HONORABLE MENTIONS:", "Leyser Calzadilla H", "Karel Santos",
             "MUSIC PRODUCED BY GEMINI", "VER: V56.2 FINAL HUD FIX"]
    for i, l in enumerate(lines):
        c = COLORES["GOLD"] if "LECAHI" in l or "GEMINI" in l else COLORES["BLANCO"]
        t = GFX.font_ui.render(l, True, c)
        s.blit(t, (ANCHO//2 - t.get_width()//2, 150*FACTOR + i*40*FACTOR))

    r_msg = pygame.Rect(ANCHO//2 - 180*FACTOR, ALTO - 200*FACTOR, 360*FACTOR, 60*FACTOR)
    pygame.draw.rect(s, (0, 30, 0), r_msg)
    pygame.draw.rect(s, COLORES["META"], r_msg, 2)
    msg = GFX.font_small.render("MUCHAS GRACIAS POR PROBAR MI JUEGO", True, COLORES["META"])
    s.blit(msg, (r_msg.centerx - msg.get_width()//2, r_msg.centery - msg.get_height()//2))

def check_daily_reward():
    hoy = datetime.now().strftime("%Y-%m-%d")
    last = DATOS["last_login"]
    streak = DATOS["daily_streak"]
    if last != hoy:
        try:
            d_last = datetime.strptime(last, "%Y-%m-%d") if last else None
            d_hoy = datetime.strptime(hoy, "%Y-%m-%d")
            temp_streak = streak
            if not d_last: temp_streak = 1
            else:
                delta = (d_hoy - d_last).days
                if delta == 1: temp_streak += 1
                elif delta > 1: temp_streak = 1
            return {"active": True, "streak": temp_streak}
        except: return {"active": True, "streak": 1}
    return {"active": False, "streak": streak}

# --- 8. MAIN ---
def main():
    global SHAKE_AMPLITUDE
    estado = "MENU"
    
    daily_status = check_daily_reward()
    if daily_status["active"]:
        estado = "REWARD"
        DATOS["daily_streak"] = daily_status["streak"]

    rain = MatrixRain()
    wipe = WipeEffect()
    start_coord = (ANCHO//2, ALTO - 150*FACTOR)
    pelota = Pelota(start_coord[0], start_coord[1])
    obs, stars, parts, portals, gravs, powers, drones, bosses, turrets = [], [], [], [], [], [], [], [], []
    projectiles = []
    float_texts = []
    nivel, tiros, drag_start = 1, 3, None
    time_scale = 1.0
    timer_warn = 0 
    level_timer = 30.0
    
    tut_texts = {
        "BASICO": ["Arrastra el mouse/dedo para apuntar", "Suelta para disparar", "Llega a la meta (Azul)"],
        "OBSTACULOS": ["Verde: Rebote", "Rojo: Muerte", "Cristal: Se rompe", "Triangulo: Rampa", "Portal: Teletransporte"],
        "JEFES": ["Aparecen cada 10 niveles", "Tienen mucha vida", "Te disparan", "Municion extra en combate"]
    }
    current_tut = "BASICO"
    
    GAME_SURF = pygame.Surface((ANCHO, ALTO))
    
    running = True
    while running:
        AUDIO.update_music()
        
        target_time = 1.0
        if estado == "WIN" or estado == "FAIL":
            target_time = 0.1 
        
        freeze_time = False
        is_paused = (estado == "PAUSA")
        
        if not is_paused:
             if pygame.mouse.get_pressed()[2] and pelota.skin_data["ab"] == "TimeStop":
                if pelota.timestop_val > 0: 
                    freeze_time = True
                    target_time = 0.2
                    pelota.timestop_val -= 1.5 
                    if pygame.time.get_ticks() % 10 == 0: sound('timestop')
        
             if estado == "JUEGO" and drag_start and pelota.moving:
                target_time = 0.2 
        
             time_scale += (target_time - time_scale) * 0.1 
        
        dt = time_scale if not is_paused else 0

        GAME_SURF.fill(COLORES["BG"])
        
        if not is_paused: 
            GFX.draw_cyber_grid(GAME_SURF, pelota.y) 
            rain.update(GAME_SURF)

        mx, my = pygame.mouse.get_pos()
        click = False
        for e in pygame.event.get():
            if e.type == pygame.QUIT: running = False
            if e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1: 
                    click = True
                    if estado == "JUEGO" and not pelota.moving and tiros > 0: drag_start = (mx, my)
                    elif estado == "JUEGO" and pelota.moving and tiros > 0: drag_start = (mx, my)

            if e.type == pygame.MOUSEBUTTONUP:
                if e.button == 1 and estado == "JUEGO" and drag_start:
                    fx, fy = (drag_start[0]-mx)/5.0, (drag_start[1]-my)/5.0
                    if math.hypot(fx,fy) > 2:
                        if math.hypot(fx,fy) > 30*FACTOR: s=(30*FACTOR)/math.hypot(fx,fy); fx*=s; fy*=s
                        pelota.launch(fx, fy); tiros -= 1
                    drag_start = None

        cx, cy = ANCHO//2, ALTO//2
        check_achievements()
        
        if estado == "BOSS_WARN":
            GAME_SURF.fill((0,0,0))
            if (pygame.time.get_ticks() // 200) % 2 == 0:
                pygame.draw.rect(GAME_SURF, (50, 0, 0), (0,0,ANCHO,ALTO), 5)
            
            GFX.draw_glitch_title(GAME_SURF, "WARNING: BOSS", cx-200*FACTOR, cy-50*FACTOR, color=(255,0,0))
            
            if timer_warn % 60 == 0: sound('alarm')
            timer_warn -= 1
            if timer_warn <= 0:
                wipe.start()
                estado = "TRANSITION"
                AUDIO.mode = "BATTLE" 

        elif estado == "REWARD" or estado == "CALENDAR_VIEW":
            GFX.draw_glitch_title(GAME_SURF, "CALENDARIO DIARIO", cx-200*FACTOR, 50*FACTOR)
            streak = DATOS["daily_streak"]
            box_w, box_h = 80 * FACTOR, 100 * FACTOR
            gap = 20 * FACTOR
            for dia in range(1, 8):
                if dia <= 4: x = (cx - (2 * box_w + 1.5 * gap)) + (dia-1) * (box_w + gap); y = cy - box_h - gap/2
                else: x = (cx - (1.5 * box_w + 1 * gap)) + (dia-5) * (box_w + gap); y = cy + gap/2
                r_box = pygame.Rect(x, y, box_w, box_h)
                
                if dia < streak: c_bg, c_b = COLORES["PAST"], COLORES["NEON_DARK"]
                elif dia == streak:
                    pulse = abs(math.sin(pygame.time.get_ticks() * 0.005)) * 100
                    c_bg, c_b = (min(255, 100 + pulse), min(255, 100 + pulse), 0), COLORES["GOLD"]
                else: c_bg, c_b = COLORES["LOCKED"], (100, 100, 100)

                pygame.draw.rect(GAME_SURF, c_bg, r_box, border_radius=int(5*FACTOR))
                pygame.draw.rect(GAME_SURF, c_b, r_box, 2, border_radius=int(5*FACTOR))
                t_day = GFX.font_small.render(f"DIA {dia}", True, COLORES["BLANCO"])
                GAME_SURF.blit(t_day, (r_box.centerx - t_day.get_width()//2, r_box.y + 10*FACTOR))
                
                rew_txt = "SKIN+50" if dia == 7 else f"+{dia+1} $"
                col_rew = COLORES["PELIGRO"] if dia==7 else COLORES["GOLD"]
                t_rew = GFX.font_ui.render(rew_txt, True, col_rew)
                GAME_SURF.blit(t_rew, (r_box.centerx - t_rew.get_width()//2, r_box.centery))

                if estado == "REWARD" and dia == streak and click and r_box.collidepoint((mx, my)):
                    DATOS["last_login"] = datetime.now().strftime("%Y-%m-%d")
                    if streak == 7: DATOS["estrellas"] += 50; 
                    if 99 not in DATOS["skins"]: DATOS["skins"].append(99)
                    else: DATOS["estrellas"] += (streak + 1)
                    io_datos("save"); sound('achieve'); estado = "MENU"
            
            if estado == "CALENDAR_VIEW":
                 if click and btn(GAME_SURF, pygame.Rect(cx-60*FACTOR, ALTO-80*FACTOR, 120*FACTOR, 50*FACTOR), "VOLVER").collidepoint((mx,my)): estado="MENU"; sound('ui')
                 else: btn(GAME_SURF, pygame.Rect(cx-60*FACTOR, ALTO-80*FACTOR, 120*FACTOR, 50*FACTOR), "VOLVER")


        elif estado == "MENU":
            GFX.draw_glitch_title(GAME_SURF, "MATRIX DUNK", cx-200*FACTOR, 50*FACTOR)
            r_play = pygame.Rect(cx-100*FACTOR, cy-80*FACTOR, 200*FACTOR, 50*FACTOR)
            r_shop = pygame.Rect(cx-100*FACTOR, cy-10*FACTOR, 200*FACTOR, 50*FACTOR)
            r_upg = pygame.Rect(cx-100*FACTOR, cy+60*FACTOR, 200*FACTOR, 50*FACTOR)
            
            r_stat = pygame.Rect(cx-100*FACTOR, cy+130*FACTOR, 95*FACTOR, 50*FACTOR)
            r_conf = pygame.Rect(cx+5*FACTOR, cy+130*FACTOR, 95*FACTOR, 50*FACTOR)
            
            r_daily = pygame.Rect(cx-100*FACTOR, cy+200*FACTOR, 95*FACTOR, 50*FACTOR)
            r_tut = pygame.Rect(cx+5*FACTOR, cy+200*FACTOR, 95*FACTOR, 50*FACTOR)

            r_exit = pygame.Rect(cx-100*FACTOR, cy+270*FACTOR, 200*FACTOR, 50*FACTOR)
            r_info = pygame.Rect(ANCHO-60*FACTOR, ALTO-60*FACTOR, 40*FACTOR, 40*FACTOR)
            
            r_hc = pygame.Rect(cx + 120*FACTOR, cy-80*FACTOR, 80*FACTOR, 50*FACTOR)
            hc_col = COLORES["PELIGRO"] if CONFIG["hardcore"] else (50,50,50)
            pygame.draw.rect(GAME_SURF, hc_col, r_hc, border_radius=5)
            t_hc = GFX.font_small.render("HARD", True, COLORES["BLANCO"])
            GAME_SURF.blit(t_hc, (r_hc.centerx-t_hc.get_width()//2, r_hc.centery-t_hc.get_height()//2))
            if click and r_hc.collidepoint((mx,my)):
                CONFIG["hardcore"] = not CONFIG["hardcore"]
                sound('ui')

            if click:
                if btn(GAME_SURF, r_play, "JUGAR").collidepoint((mx,my)):
                    estado="JUEGO"; nivel=1; 
                    tiros = 3 + DATOS["mejoras"]["ammo"]
                    level_timer = 30.0
                    pelota.start=start_coord; pelota.reset(); 
                    obs, stars, portals, gravs, powers, drones, bosses, turrets = make_level(nivel); 
                    projectiles = []
                    AUDIO.mode = "EXPLORE"
                    sound('ui')
                if btn(GAME_SURF, r_shop, "TIENDA").collidepoint((mx,my)): estado="TIENDA"; sound('ui')
                if btn(GAME_SURF, r_upg, "MEJORAS").collidepoint((mx,my)): estado="UPGRADES"; sound('ui')
                if btn(GAME_SURF, r_stat, "STATS").collidepoint((mx,my)): estado="STATS"; sound('ui')
                if btn(GAME_SURF, r_conf, "AJUSTES").collidepoint((mx,my)): estado="AJUSTES"; sound('ui')
                if btn(GAME_SURF, r_daily, "DIARIO").collidepoint((mx,my)): estado="CALENDAR_VIEW"; sound('ui')
                if btn(GAME_SURF, r_tut, "TUTORIAL").collidepoint((mx,my)): estado="TUTORIAL"; sound('ui')
                if btn(GAME_SURF, r_exit, "SALIR").collidepoint((mx,my)): running=False
                if btn(GAME_SURF, r_info, "i").collidepoint((mx,my)): estado="INFO"; sound('ui')
            else:
                btn(GAME_SURF, r_play, "JUGAR"); btn(GAME_SURF, r_shop, "TIENDA")
                btn(GAME_SURF, r_upg, "MEJORAS"); 
                btn(GAME_SURF, r_stat, "STATS"); btn(GAME_SURF, r_conf, "AJUSTES")
                btn(GAME_SURF, r_daily, "DIARIO"); btn(GAME_SURF, r_tut, "TUTORIAL")
                btn(GAME_SURF, r_exit, "SALIR")
                btn(GAME_SURF, r_info, "i")

        elif estado == "TUTORIAL":
            t = GFX.font_big.render("TUTORIAL", True, COLORES["NEON"]); GAME_SURF.blit(t, (cx-t.get_width()//2, 30*FACTOR))
            
            if click:
                if btn(GAME_SURF, pygame.Rect(cx-100*FACTOR, 150*FACTOR, 200*FACTOR, 50*FACTOR), "BASICO").collidepoint((mx,my)): current_tut = "BASICO"
                if btn(GAME_SURF, pygame.Rect(cx-100*FACTOR, 220*FACTOR, 200*FACTOR, 50*FACTOR), "OBSTACULOS").collidepoint((mx,my)): current_tut = "OBSTACULOS"
                if btn(GAME_SURF, pygame.Rect(cx-100*FACTOR, 290*FACTOR, 200*FACTOR, 50*FACTOR), "JEFES").collidepoint((mx,my)): current_tut = "JEFES"
            else:
                btn(GAME_SURF, pygame.Rect(cx-100*FACTOR, 150*FACTOR, 200*FACTOR, 50*FACTOR), "BASICO")
                btn(GAME_SURF, pygame.Rect(cx-100*FACTOR, 220*FACTOR, 200*FACTOR, 50*FACTOR), "OBSTACULOS")
                btn(GAME_SURF, pygame.Rect(cx-100*FACTOR, 290*FACTOR, 200*FACTOR, 50*FACTOR), "JEFES")

            r_text = pygame.Rect(cx-150*FACTOR, 380*FACTOR, 300*FACTOR, 200*FACTOR)
            pygame.draw.rect(GAME_SURF, (0,20,20), r_text, border_radius=5)
            pygame.draw.rect(GAME_SURF, COLORES["NEON"], r_text, 2, border_radius=5)
            
            lines = tut_texts[current_tut]
            for i, l in enumerate(lines):
                txt = GFX.font_small.render(l, True, COLORES["BLANCO"])
                GAME_SURF.blit(txt, (r_text.centerx - txt.get_width()//2, r_text.y + 20*FACTOR + i*30*FACTOR))

            if click and btn(GAME_SURF, pygame.Rect(cx-60*FACTOR, ALTO-80*FACTOR, 120*FACTOR, 50*FACTOR), "VOLVER").collidepoint((mx,my)): estado="MENU"; sound('ui')
            else: btn(GAME_SURF, pygame.Rect(cx-60*FACTOR, ALTO-80*FACTOR, 120*FACTOR, 50*FACTOR), "VOLVER")

        elif estado == "UPGRADES":
            t = GFX.font_big.render("SISTEMA", True, COLORES["NEON"]); GAME_SURF.blit(t, (cx-t.get_width()//2, 30*FACTOR))
            t2 = GFX.font_ui.render(f"CREDITOS: {DATOS['estrellas']}", True, COLORES["GOLD"]); GAME_SURF.blit(t2, (cx-t2.get_width()//2, 70*FACTOR))

            upgrades_list = [
                ("ammo", "CARGADOR", "Balas extra al iniciar"),
                ("aim", "LASER", "Mejor prediccion de tiro"),
                ("luck", "SUERTE", "Chance de doble recompensa")
            ]
            
            start_y = 120 * FACTOR
            for i, (key, name, desc) in enumerate(upgrades_list):
                lvl = DATOS["mejoras"][key]
                cost = PRECIOS_MEJORAS[lvl] if lvl < len(PRECIOS_MEJORAS) else "MAX"
                r = pygame.Rect(cx-180*FACTOR, start_y + i*100*FACTOR, 360*FACTOR, 80*FACTOR)
                pygame.draw.rect(GAME_SURF, (0,20,20), r, border_radius=5)
                pygame.draw.rect(GAME_SURF, COLORES["PORTAL_B"], r, 2, border_radius=5)
                
                t_name = GFX.font_ui.render(f"{name} [LVL {lvl}]", True, COLORES["BLANCO"])
                GAME_SURF.blit(t_name, (r.x+20*FACTOR, r.y+10*FACTOR))
                t_desc = GFX.font_small.render(desc, True, (150,150,150))
                GAME_SURF.blit(t_desc, (r.x+20*FACTOR, r.y+40*FACTOR))
                
                btn_txt = "MAX" if cost == "MAX" else f"${cost}"
                r_btn = pygame.Rect(r.right-100*FACTOR, r.centery-20*FACTOR, 80*FACTOR, 40*FACTOR)
                col_btn = COLORES["GOLD"] if cost != "MAX" and DATOS["estrellas"] >= cost else (100,100,100)
                pygame.draw.rect(GAME_SURF, col_btn, r_btn, border_radius=5)
                t_cost = GFX.font_ui.render(str(btn_txt), True, (0,0,0))
                GAME_SURF.blit(t_cost, (r_btn.centerx-t_cost.get_width()//2, r_btn.centery-t_cost.get_height()//2))
                
                if click and r_btn.collidepoint((mx,my)) and cost != "MAX" and DATOS["estrellas"] >= cost:
                    DATOS["estrellas"] -= cost
                    DATOS["mejoras"][key] += 1
                    io_datos("save")
                    sound('powerup')

            if click and btn(GAME_SURF, pygame.Rect(cx-60*FACTOR, ALTO-60*FACTOR, 120*FACTOR, 50*FACTOR), "VOLVER").collidepoint((mx,my)): estado="MENU"; sound('ui')
            else: btn(GAME_SURF, pygame.Rect(cx-60*FACTOR, ALTO-60*FACTOR, 120*FACTOR, 50*FACTOR), "VOLVER")

        elif estado == "STATS":
            draw_stats(GAME_SURF)
            if click and btn(GAME_SURF, pygame.Rect(cx-60*FACTOR, ALTO-80*FACTOR, 120*FACTOR, 50*FACTOR), "VOLVER").collidepoint((mx,my)): estado="MENU"; sound('ui')
            else: btn(GAME_SURF, pygame.Rect(cx-60*FACTOR, ALTO-80*FACTOR, 120*FACTOR, 50*FACTOR), "VOLVER")

        elif estado == "INFO":
            draw_info(GAME_SURF)
            if click and btn(GAME_SURF, pygame.Rect(cx-60*FACTOR, ALTO-80*FACTOR, 120*FACTOR, 50*FACTOR), "VOLVER").collidepoint((mx,my)): estado="MENU"; sound('ui')
            else: btn(GAME_SURF, pygame.Rect(cx-60*FACTOR, ALTO-80*FACTOR, 120*FACTOR, 50*FACTOR), "VOLVER")

        elif estado == "TRANSITION":
            # TRANSICION SHUTTER
            if wipe.update_draw(GAME_SURF):
                nivel += 1; pelota.start = start_coord; pelota.reset(); 
                
                base_ammo = 3 + DATOS["mejoras"]["ammo"]
                is_boss = (nivel % 10 == 0)
                
                if is_boss: 
                    tiros = base_ammo + 12 
                    level_timer = 90.0 
                else:
                    tiros = base_ammo
                    level_timer = 30.0
                
                obs, stars, portals, gravs, powers, drones, bosses, turrets = make_level(nivel)
                projectiles = []
                estado = "JUEGO"

        elif estado == "JUEGO":
            res = pelota.update(obs, stars, parts, portals, gravs, powers, drones, bosses, turrets, projectiles, float_texts, dt)
            
            if not freeze_time and not is_paused:
                level_timer -= (1.0/60.0) * dt
                if level_timer <= 0:
                    sound('die')
                    res = "die"

                for o in obs: o.update()
                for d in drones: d.update(pelota.x, pelota.y)
                for b in bosses: b.update(pelota, projectiles)
                for t in turrets: t.update(pelota.x, pelota.y, projectiles)
                for pr in projectiles[:]:
                    pr.update()
                    if pr.life <= 0: projectiles.remove(pr)
            
            if res == "win" or res == "win_combo" or res == "swish":
                reward_win = 0
                if res == "win": DATOS["total_victorias"] += 1; 
                elif res == "win_combo": 
                     DATOS["total_victorias"] += 1; DATOS["estrellas"] += 2; reward_win = 2
                     NOTIFIER.add("COMBO X2!")
                elif res == "swish":
                     DATOS["total_victorias"] += 1; 
                     tiros += 1; NOTIFIER.add("SWISH: +1 BALA")
                
                luck_lvl = DATOS["mejoras"]["luck"]
                if luck_lvl > 0 and random.random() < (luck_lvl * 0.1): 
                     DATOS["estrellas"] += 5
                     NOTIFIER.add("SUERTE: BONUS $")
                
                io_datos("save")
                if nivel >= DATOS["record"]: DATOS["record"] = nivel+1
                
                if (nivel + 1) % 10 == 0:
                    estado = "BOSS_WARN"
                    timer_warn = 180 
                else:
                    AUDIO.mode = "EXPLORE"
                    wipe.start()
                    estado = "TRANSITION"
            
            elif res == "die": 
                DATOS["total_muertes"] += 1; io_datos("save"); 
                if CONFIG["hardcore"]:
                    nivel = 1 
                    DATOS["estrellas"] = max(0, DATOS["estrellas"] - 10)
                estado = "FAIL"
            elif res == "star": DATOS["estrellas"] += 1; io_datos("save")
            elif res == "ammo": tiros += 1
            elif not pelota.moving and tiros == 0: 
                DATOS["total_muertes"] += 1; io_datos("save"); 
                if CONFIG["hardcore"]: nivel = 1
                estado = "FAIL"
            
            for g in gravs: g.draw(GAME_SURF)
            for p in portals: p.draw(GAME_SURF)
            for p in powers: p.draw(GAME_SURF)
            for t in turrets: t.draw(GAME_SURF)
            for pr in projectiles: pr.draw(GAME_SURF)
            for o in obs: o.draw(GAME_SURF)
            for s in stars: s.draw(GAME_SURF)
            for d in drones: d.draw(GAME_SURF)
            for b in bosses: b.draw(GAME_SURF)
            for ft in float_texts[:]:
                ft.update(); ft.draw(GAME_SURF)
                if ft.life <= 0: float_texts.remove(ft)
            
            pelota.draw(GAME_SURF)
            
            if drag_start:
                # Linea eliminada a petición
                pts = pelota.predict((drag_start[0]-mx)/5.0, (drag_start[1]-my)/5.0, obs)
                for px, py in pts: pygame.draw.circle(GAME_SURF, (255, 255, 255), (int(px), int(py)), 2)

            # --- UI CORREGIDA (HUD FINAL) ---
            # 1. STATS (Izquierda)
            t = GFX.font_ui.render(f"LVL:{nivel}  BALAS:{tiros}  $: {DATOS['estrellas']}", True, COLORES["BLANCO"])
            GAME_SURF.blit(t, (20, 10*FACTOR))
            
            # 2. TIMER (Derecha, separado)
            c_time = COLORES["NEON"] if level_timer > 10 else COLORES["PELIGRO"]
            t_str = f"TIME: {int(level_timer)}"
            t_timer = GFX.font_ui.render(t_str, True, c_time)
            
            # Fondo para timer
            r_timer_bg = pygame.Rect(ANCHO - 140*FACTOR, 10*FACTOR, 120*FACTOR, 35*FACTOR)
            pygame.draw.rect(GAME_SURF, (0,0,0,180), r_timer_bg, border_radius=5)
            GAME_SURF.blit(t_timer, (r_timer_bg.centerx - t_timer.get_width()//2, r_timer_bg.centery - t_timer.get_height()//2))
            
            if pelota.ability:
                ab_txt = GFX.font_small.render(f"HABILIDAD: {pelota.ability}", True, COLORES["ACHIEVE"])
                GAME_SURF.blit(ab_txt, (20, 40*FACTOR))
                if pelota.ability == "TimeStop":
                    bar_w, bar_h = 200 * FACTOR, 10 * FACTOR
                    bx, by = cx - bar_w // 2, ALTO - 60 * FACTOR
                    fill = (pelota.timestop_val / pelota.timestop_max) * bar_w
                    pygame.draw.rect(GAME_SURF, (50,50,50), (bx, by, bar_w, bar_h))
                    c_bar = COLORES["PORTAL_B"] if not freeze_time else COLORES["GOLD"]
                    pygame.draw.rect(GAME_SURF, c_bar, (bx, by, fill, bar_h))
                    if freeze_time:
                        warn = GFX.font_ui.render("TIEMPO DETENIDO", True, COLORES["PORTAL_B"])
                        GAME_SURF.blit(warn, (cx-warn.get_width()//2, by - 30*FACTOR))

            # 3. BOTÓN PAUSA (Grande y con símbolo ||)
            r_p = pygame.Rect(ANCHO - 70*FACTOR, 60*FACTOR, 60*FACTOR, 60*FACTOR)
            # Fondo
            s_pause = pygame.Surface((r_p.w, r_p.h), pygame.SRCALPHA)
            pygame.draw.rect(s_pause, (0, 20, 0, 150), s_pause.get_rect(), border_radius=8)
            GAME_SURF.blit(s_pause, r_p.topleft)
            # Borde
            pygame.draw.rect(GAME_SURF, COLORES["NEON"], r_p, 2, border_radius=8)
            # Simbolo ||
            bar_w = 8 * FACTOR
            bar_h = 25 * FACTOR
            pygame.draw.rect(GAME_SURF, COLORES["NEON"], (r_p.centerx - bar_w - 4*FACTOR, r_p.centery - bar_h//2, bar_w, bar_h))
            pygame.draw.rect(GAME_SURF, COLORES["NEON"], (r_p.centerx + 4*FACTOR, r_p.centery - bar_h//2, bar_w, bar_h))
            
            if click and r_p.collidepoint((mx,my)): estado="PAUSA"; sound('ui')

        elif estado == "PAUSA":
            for o in obs: o.draw(GAME_SURF)
            pelota.draw(GAME_SURF)
            s = pygame.Surface((ANCHO, ALTO)); s.set_alpha(180); s.fill((0,0,0)); GAME_SURF.blit(s,(0,0))
            t = GFX.font_big.render("PAUSA", True, COLORES["BLANCO"]); GAME_SURF.blit(t, (cx-t.get_width()//2, cy-80*FACTOR))
            if click:
                if btn(GAME_SURF, pygame.Rect(cx-100*FACTOR, cy, 200*FACTOR, 50*FACTOR), "SEGUIR").collidepoint((mx,my)): estado="JUEGO"
                if btn(GAME_SURF, pygame.Rect(cx-100*FACTOR, cy+60*FACTOR, 200*FACTOR, 50*FACTOR), "MENU").collidepoint((mx,my)): estado="MENU"
            else:
                btn(GAME_SURF, pygame.Rect(cx-100*FACTOR, cy, 200*FACTOR, 50*FACTOR), "SEGUIR")
                btn(GAME_SURF, pygame.Rect(cx-100*FACTOR, cy+60*FACTOR, 200*FACTOR, 50*FACTOR), "MENU")

        elif estado == "TIENDA":
            t = GFX.font_big.render("TIENDA", True, COLORES["META"]); GAME_SURF.blit(t, (cx-t.get_width()//2, 30*FACTOR))
            t2 = GFX.font_ui.render(f"CREDITOS: {DATOS['estrellas']}", True, COLORES["GOLD"]); GAME_SURF.blit(t2, (cx-t2.get_width()//2, 70*FACTOR))
            
            start_y = 120*FACTOR
            for i, s in enumerate(SKINS):
                if i > 5: break
                r = pygame.Rect(cx-180*FACTOR, start_y + i*75*FACTOR, 360*FACTOR, 65*FACTOR)
                owned = s["id"] in DATOS["skins"]; usando = s["id"] == DATOS["skin_act"]
                
                pygame.draw.rect(GAME_SURF, (0,30,0), r, border_radius=5)
                color_borde = COLORES["NEON"] if owned else COLORES["PELIGRO"]
                if s["id"] == 99: color_borde = (255, 255, 255)
                
                pygame.draw.rect(GAME_SURF, color_borde, r, 2, border_radius=5)
                GFX.draw_glow_circle(GAME_SURF, r.x+35*FACTOR, r.centery, 15*FACTOR, s["c"])
                
                name = s["n"]
                if s["id"] == 99: name = "???" if not owned else "THE ONE"
                
                t_name = GFX.font_ui.render(name, True, COLORES["BLANCO"])
                GAME_SURF.blit(t_name, (r.x+70*FACTOR, r.y + 10*FACTOR))
                
                desc = s["desc"]
                if s["id"] == 99 and not owned: desc = "Recompensa dia 7"
                t_desc = GFX.font_small.render(desc, True, (150,150,150))
                GAME_SURF.blit(t_desc, (r.x+70*FACTOR, r.y + 35*FACTOR))
                
                status = "USANDO" if usando else ("TIENES" if owned else f"${s['p']}")
                t_stat = GFX.font_ui.render(status, True, COLORES["GOLD"] if not owned else COLORES["META"])
                GAME_SURF.blit(t_stat, (r.right - t_stat.get_width() - 10, r.centery - t_stat.get_height()//2))

                if click and r.collidepoint((mx,my)):
                    if owned: DATOS["skin_act"] = s["id"]; io_datos("save"); sound('ui')
                    elif DATOS["estrellas"] >= s["p"] and s["id"] != 99:
                        DATOS["estrellas"] -= s["p"]; DATOS["skins"].append(s["id"]); DATOS["skin_act"] = s["id"]
                        io_datos("save"); sound('win')

            if click and btn(GAME_SURF, pygame.Rect(cx-60*FACTOR, ALTO-60*FACTOR, 120*FACTOR, 50*FACTOR), "VOLVER").collidepoint((mx,my)): estado="MENU"; sound('ui')
            else: btn(GAME_SURF, pygame.Rect(cx-60*FACTOR, ALTO-60*FACTOR, 120*FACTOR, 50*FACTOR), "VOLVER")

        elif estado == "AJUSTES":
            t = GFX.font_big.render("AJUSTES", True, COLORES["NEON"]); GAME_SURF.blit(t, (cx-t.get_width()//2, 30*FACTOR))
            
            y_mus = 120 * FACTOR
            t_mus = GFX.font_ui.render(f"MUSICA: {CONFIG['vol_musica']}", True, COLORES["BLANCO"])
            GAME_SURF.blit(t_mus, (cx - 150*FACTOR, y_mus))
            if click and btn(GAME_SURF, pygame.Rect(cx + 50*FACTOR, y_mus, 40*FACTOR, 30*FACTOR), "-").collidepoint((mx,my)):
                CONFIG["vol_musica"] = max(0, CONFIG["vol_musica"] - 1); sound('ui')
            else: btn(GAME_SURF, pygame.Rect(cx + 50*FACTOR, y_mus, 40*FACTOR, 30*FACTOR), "-")
            if click and btn(GAME_SURF, pygame.Rect(cx + 100*FACTOR, y_mus, 40*FACTOR, 30*FACTOR), "+").collidepoint((mx,my)):
                CONFIG["vol_musica"] = min(10, CONFIG["vol_musica"] + 1); sound('ui')
            else: btn(GAME_SURF, pygame.Rect(cx + 100*FACTOR, y_mus, 40*FACTOR, 30*FACTOR), "+")
            pygame.draw.rect(GAME_SURF, (50,50,50), (cx-150*FACTOR, y_mus+35*FACTOR, 290*FACTOR, 10*FACTOR))
            pygame.draw.rect(GAME_SURF, COLORES["PORTAL_B"], (cx-150*FACTOR, y_mus+35*FACTOR, 29*FACTOR*CONFIG["vol_musica"], 10*FACTOR))

            y_sfx = 200 * FACTOR
            t_sfx = GFX.font_ui.render(f"EFECTOS: {CONFIG['vol_sfx']}", True, COLORES["BLANCO"])
            GAME_SURF.blit(t_sfx, (cx - 150*FACTOR, y_sfx))
            if click and btn(GAME_SURF, pygame.Rect(cx + 50*FACTOR, y_sfx, 40*FACTOR, 30*FACTOR), "-").collidepoint((mx,my)):
                CONFIG["vol_sfx"] = max(0, CONFIG["vol_sfx"] - 1); sound('ui')
            else: btn(GAME_SURF, pygame.Rect(cx + 50*FACTOR, y_sfx, 40*FACTOR, 30*FACTOR), "-")
            if click and btn(GAME_SURF, pygame.Rect(cx + 100*FACTOR, y_sfx, 40*FACTOR, 30*FACTOR), "+").collidepoint((mx,my)):
                CONFIG["vol_sfx"] = min(10, CONFIG["vol_sfx"] + 1); sound('ui')
            else: btn(GAME_SURF, pygame.Rect(cx + 100*FACTOR, y_sfx, 40*FACTOR, 30*FACTOR), "+")
            pygame.draw.rect(GAME_SURF, (50,50,50), (cx-150*FACTOR, y_sfx+35*FACTOR, 290*FACTOR, 10*FACTOR))
            pygame.draw.rect(GAME_SURF, COLORES["PORTAL_A"], (cx-150*FACTOR, y_sfx+35*FACTOR, 29*FACTOR*CONFIG["vol_sfx"], 10*FACTOR))

            if click and btn(GAME_SURF, pygame.Rect(cx-60*FACTOR, ALTO-80*FACTOR, 120*FACTOR, 50*FACTOR), "VOLVER").collidepoint((mx,my)): estado="MENU"; sound('ui')
            else: btn(GAME_SURF, pygame.Rect(cx-60*FACTOR, ALTO-80*FACTOR, 120*FACTOR, 50*FACTOR), "VOLVER")

        elif estado in ["WIN", "FAIL"]:
            s = pygame.Surface((ANCHO,ALTO)); s.set_alpha(200); s.fill((0,0,0)); GAME_SURF.blit(s,(0,0))
            msg = "HACKEO COMPLETADO" if estado == "WIN" else "ERROR SISTEMA"
            c = COLORES["NEON"] if estado == "WIN" else COLORES["PELIGRO"]
            GFX.draw_neon_rect(GAME_SURF, pygame.Rect(cx-150*FACTOR, cy-100*FACTOR, 300*FACTOR, 250*FACTOR), c, True)
            t = GFX.font_big.render(msg, True, COLORES["BLANCO"]); GAME_SURF.blit(t, (cx-t.get_width()//2, cy-80*FACTOR))
            b_txt = "SIGUIENTE" if estado == "WIN" else "REINTENTAR"
            if click:
                if btn(GAME_SURF, pygame.Rect(cx-100*FACTOR, cy, 200*FACTOR, 50*FACTOR), b_txt).collidepoint((mx,my)):
                    if estado == "WIN": nivel+=1; pelota.start = start_coord
                    else: nivel=1; pelota.start = start_coord
                    tiros=3 + DATOS["mejoras"]["ammo"]; pelota.reset(); 
                    obs, stars, portals, gravs, powers, drones, bosses, turrets = make_level(nivel); 
                    projectiles = []
                    if nivel % 10 == 0: level_timer = 90.0 
                    else: level_timer = 30.0
                    estado="JUEGO"
                if btn(GAME_SURF, pygame.Rect(cx-100*FACTOR, cy+60*FACTOR, 200*FACTOR, 50*FACTOR), "MENU").collidepoint((mx,my)): estado="MENU"
            else:
                btn(GAME_SURF, pygame.Rect(cx-100*FACTOR, cy, 200*FACTOR, 50*FACTOR), b_txt)
                btn(GAME_SURF, pygame.Rect(cx-100*FACTOR, cy+60*FACTOR, 200*FACTOR, 50*FACTOR), "MENU")

        NOTIFIER.update_draw(GAME_SURF)
        for p in parts[:]:
            p.update(); p.draw(GAME_SURF)
            if p.life <= 0: parts.remove(p)
            
        render_x, render_y = 0, 0
        if SHAKE_AMPLITUDE > 0:
            render_x = random.randint(-SHAKE_AMPLITUDE, SHAKE_AMPLITUDE)
            render_y = random.randint(-SHAKE_AMPLITUDE, SHAKE_AMPLITUDE)
            SHAKE_AMPLITUDE -= 1
        
        PANTALLA.fill((0,0,0))
        PANTALLA.blit(GAME_SURF, (render_x, render_y))

        pygame.display.flip()
        RELOJ.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
