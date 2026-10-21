import math
import random

import pygame

W, H = 1920, 1080


def soft_dot(radius, color, falloff=2.2):
    size = radius * 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    for r in range(radius, 0, -1):
        k = r / radius
        a = int(255 * (1 - k) ** falloff)
        pygame.draw.circle(surf, (*color, a), (radius, radius), r)
    return surf


def disc(radius, color, alpha, edge=0.18):
    size = radius * 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    for r in range(radius, 0, -1):
        k = r / radius
        a = alpha if k < 1 - edge else int(alpha * (1 - k) / edge)
        pygame.draw.circle(surf, (*color, a), (radius, radius), r)
    return surf


class Ambient:
    def __init__(self, seed=7):
        self.rng = random.Random(seed)
        self.t = 0.0
        self.boost = 0.0
        self.base = self.make_base()
        self.rays = self.make_rays()
        self.sparks = [soft_dot(r, c) for r, c in ((6, (255, 255, 255)), (10, (255, 244, 225)), (16, (255, 236, 210)))]
        self.bokeh_sprites = [disc(r, c, a) for r, c, a in (
            (70, (255, 238, 215), 40), (110, (255, 226, 190), 30), (150, (230, 170, 150), 34),
            (90, (255, 255, 255), 26), (180, (255, 230, 200), 18))]
        self.particles = [self.new_particle(True) for _ in range(int(220 * W / 1920))]
        self.bokeh = [self.new_bokeh(True) for _ in range(max(10, int(14 * W / 1920)))]

    def make_base(self):
        surf = pygame.Surface((W, H))
        for y in range(0, H, 2):
            k = y / H
            c = (int(58 - 30 * k), int(56 - 30 * k), int(58 - 28 * k))
            pygame.draw.rect(surf, c, (0, y, W, 2))
        vign = pygame.Surface((W, H), pygame.SRCALPHA)
        for i in range(40):
            k = i / 40
            pygame.draw.ellipse(vign, (0, 0, 0, int(10 * k)), (-W * 0.3 * (1 - k), -H * 0.4 * (1 - k),
                                                                W * (1 + 0.6 * (1 - k)), H * (1 + 0.8 * (1 - k))), 0)
        return surf

    def make_rays(self):
        surf = pygame.Surface((W, H), pygame.SRCALPHA)
        origin = (int(W * 0.18), -140)
        for i in range(7):
            ang = math.radians(48 + i * 9 + self.rng.uniform(-2, 2))
            width = math.radians(self.rng.uniform(3, 6))
            length = 1700
            pts = [origin]
            for a in (ang - width, ang + width):
                pts.append((origin[0] + math.cos(a) * length, origin[1] + math.sin(a) * length))
            layer = pygame.Surface((W, H), pygame.SRCALPHA)
            pygame.draw.polygon(layer, (255, 236, 214, self.rng.randint(6, 11)), pts)
            surf.blit(layer, (0, 0))
        glow = soft_dot(520, (255, 230, 200), 1.6)
        glow.set_alpha(90)
        surf.blit(glow, (origin[0] - 520, origin[1] - 520))
        small = pygame.transform.smoothscale(pygame.transform.smoothscale(surf, (W // 24, H // 24)), (W // 6, H // 6))
        return pygame.transform.smoothscale(small, (W, H))

    def new_particle(self, anywhere=False):
        r = self.rng
        x = r.uniform(-200, W) if anywhere else r.uniform(-300, W * 0.4)
        y = r.uniform(0, H) if anywhere else r.uniform(H * 0.45, H * 1.05)
        speed = r.uniform(40, 140)
        return {"x": x, "y": y, "vx": speed, "vy": -speed * r.uniform(0.15, 0.45),
                "s": r.choices((0, 1, 2), (70, 22, 8))[0], "a": r.uniform(0.25, 1.0),
                "ph": r.uniform(0, math.tau)}

    def new_bokeh(self, anywhere=False):
        r = self.rng
        return {"x": r.uniform(0, W), "y": r.uniform(H * 0.2, H) if anywhere else H + 200,
                "vx": r.uniform(-12, 12), "vy": r.uniform(-18, -6), "i": r.randrange(len(self.bokeh_sprites)),
                "a": r.uniform(0.3, 1.0), "ph": r.uniform(0, math.tau)}

    def update(self, dt):
        self.t += dt
        self.boost = max(0.0, self.boost - dt * 0.8)
        k = 1 + self.boost * 6
        for p in self.particles:
            p["x"] += p["vx"] * dt * k
            p["y"] += (p["vy"] + 14 * math.sin(self.t * 0.8 + p["ph"])) * dt * k
            if p["x"] > W + 60 or p["y"] < -60:
                p.update(self.new_particle())
        for b in self.bokeh:
            b["x"] += b["vx"] * dt
            b["y"] += b["vy"] * dt * (1 + self.boost * 3)
            if b["y"] < -260:
                b.update(self.new_bokeh())

    def draw(self, surf, alpha=255):
        surf.blit(self.base, (0, 0))
        self.rays.set_alpha(int(alpha * (0.75 + 0.25 * math.sin(self.t * 0.35))))
        surf.blit(self.rays, (0, 0))
        for b in self.bokeh:
            spr = self.bokeh_sprites[b["i"]]
            spr.set_alpha(int(alpha * b["a"] * (0.6 + 0.4 * math.sin(self.t * 0.5 + b["ph"]))))
            surf.blit(spr, (b["x"] - spr.get_width() // 2, b["y"] - spr.get_height() // 2))
        for p in self.particles:
            spr = self.sparks[p["s"]]
            tw = 0.55 + 0.45 * math.sin(self.t * 3 + p["ph"])
            spr.set_alpha(int(alpha * p["a"] * tw))
            surf.blit(spr, (p["x"] - spr.get_width() // 2, p["y"] - spr.get_height() // 2))


class BlueBloom:
    def __init__(self, seed=3):
        rng = random.Random(seed)
        self.blobs = [(rng.uniform(0.1, 0.9) * W, rng.uniform(0.15, 0.85) * H, rng.uniform(140, 320),
                       rng.uniform(0, 0.6)) for _ in range(9)]
        self.sprite = disc(200, (40, 110, 170), 255, 0.6)
        self.stars = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0.3, 1), rng.choice((1, 1, 2))) for _ in range(260)]

    def draw(self, surf, t):
        surf.fill((2, 4, 8))
        for x, y, r, delay in self.blobs:
            k = max(0.0, min(1.0, (t - delay) / 1.2))
            fade = k if t < 2.0 else max(0.0, 1 - (t - 2.0) / 0.9)
            if fade <= 0:
                continue
            size = int(r * 2 * (0.7 + 0.3 * k))
            spr = pygame.transform.smoothscale(self.sprite, (size, size))
            spr.set_alpha(int(110 * fade))
            surf.blit(spr, (x - size // 2, y - size // 2))
        sk = max(0.0, min(1.0, (t - 1.6) / 1.2))
        for x, y, a, s in self.stars:
            c = int(255 * a * sk)
            if c > 8:
                pygame.draw.circle(surf, (c, c, c), (int(x), int(y)), s)
