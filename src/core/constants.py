"""Fixed simulation constants. Everything a player may tune lives in `GameScheme` instead."""

# Default world size for generated maps (PNG maps are scaled to it)
WORLD_WIDTH = 2000
WORLD_HEIGHT = 1000

# Physics base values (scaled by scheme multipliers where noted)
GRAVITY = 600.0  # px / s^2, scaled by scheme.environment.gravity
WIND_ACCELERATION = 140.0  # px / s^2 at wind 1.0, scaled by scheme.environment.wind_max

# Worms
WORM_RADIUS = 7
WORM_WALK_SPEED = 55.0  # px / s
WORM_MAX_CLIMB = 6  # px a worm can step up while walking
WORM_JUMP_VELOCITY = (130.0, -230.0)
WORM_BOUNCE = 0.35
FALL_DAMAGE_SPEED = 420.0  # landing speed (px/s) above which fall damage applies
FALL_DAMAGE_PER_SPEED = 0.1  # hp per px/s above the threshold, scaled by the scheme factor
LANDING_SPEED = 170.0

# Shooting
MAX_SHOT_SPEED = 900.0  # px / s at full power
CHARGE_TIME = 1.3  # seconds from zero to full power
AIM_SPEED = 1.6  # rad / s
AIM_MIN = -1.45  # rad, relative to the horizon (negative = down)
AIM_MAX = 1.45
PROJECTILE_MAX_AGE = 20.0

# Turn flow
SETTLE_MIN_TIME = 0.6
SIM_DT = 1 / 60  # fixed simulation step used by the game loop, replays and tests

DEFAULT_WORM_NAMES = (
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
)
