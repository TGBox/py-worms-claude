"""Game configuration and global constants."""

# Display settings (virtual resolution; the window is letterboxed to this aspect ratio)
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
TITLE = "py-worms-claude"

# Color palette (RGB)
COLOR_BACKGROUND = (18, 20, 28)
COLOR_PRIMARY = (56, 189, 248)
COLOR_TEXT = (241, 245, 249)
COLOR_ACCENT = (244, 63, 94)
COLOR_MUTED = (148, 163, 184)
COLOR_SKY_TOP = (30, 41, 82)
COLOR_SKY_BOTTOM = (125, 160, 214)
COLOR_WATER = (30, 90, 160)
COLOR_SOIL = (122, 82, 48)
COLOR_SOIL_DARK = (92, 60, 34)
COLOR_GRASS = (88, 170, 64)

TEAM_COLORS = [(244, 63, 94), (56, 189, 248), (250, 204, 21), (74, 222, 128)]
TEAM_NAMES = ["Team Rot", "Team Blau", "Team Gelb", "Team Grün"]
WORM_NAMES = [
    "Boggy",
    "Spadge",
    "Clagnut",
    "Kurt",
    "Heinz",
    "Lotte",
    "Grete",
    "Fritz",
    "Elsa",
    "Paule",
    "Bruno",
    "Wilma",
    "Ida",
    "Otto",
    "Rudi",
    "Frieda",
]

# World
WORLD_WIDTH = 2000
WORLD_HEIGHT = 1000
WATER_LEVEL = 930
GRAVITY = 600.0  # px / s^2
WIND_MAX = 140.0  # horizontal acceleration in px / s^2 at wind strength 1.0

# Worms
WORMS_PER_TEAM = 3
WORM_RADIUS = 7
WORM_MAX_HP = 100
WORM_WALK_SPEED = 55.0  # px / s
WORM_MAX_CLIMB = 6  # px a worm can step up while walking
WORM_JUMP_VELOCITY = (130.0, -230.0)
FALL_DAMAGE_SPEED = 420.0  # landing speed (px/s) above which fall damage applies
FALL_DAMAGE_FACTOR = 0.1  # hp per px/s above the threshold
WORM_BOUNCE = 0.35

# Shooting
MAX_SHOT_SPEED = 900.0  # px / s at full power
CHARGE_TIME = 1.3  # seconds from zero to full power
AIM_SPEED = 1.6  # rad / s
AIM_MIN = -1.45  # rad, relative to the horizon (negative = down)
AIM_MAX = 1.45

# Turns
TURN_TIME = 45.0
RETREAT_TIME = 3.0
SETTLE_MIN_TIME = 0.6
