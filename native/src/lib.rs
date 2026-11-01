//! Hot physics loops for py-worms-claude, exposed through a plain C ABI and loaded with ctypes.
//!
//! Every function mirrors its Python reference in `src/core` operation by operation (same f64
//! evaluation order, `sqrt(x*x + y*y)` instead of `hypot`, truncating casts like Python's `int()`),
//! so both backends produce bit-identical results. `tests/test_native.py` enforces this.
//!
//! Safety contract for all functions: pointers come from Python objects that stay alive and
//! unchanged in size for the duration of the call; lengths are passed alongside.

#![allow(clippy::missing_safety_doc, clippy::too_many_arguments)]

use std::slice;
use std::sync::OnceLock;

/// Kernel version; the Python loader refuses libraries with another version.
const KERNEL_VERSION: i32 = 4;

struct Config {
    /// Centre followed by the rim sample offsets (unit circle), as computed in Python.
    circle_points: Vec<(f64, f64)>,
    worm_radius: f64,
    projectile_max_age: f64,
}

static CONFIG: OnceLock<Config> = OnceLock::new();

fn config() -> &'static Config {
    CONFIG.get().expect("wk_init must be called first")
}

/// Read-only view on the Python terrain bytearray (1 = solid).
struct Grid<'a> {
    data: &'a [u8],
    width: i64,
    height: i64,
}

impl<'a> Grid<'a> {
    unsafe fn new(data: *const u8, width: i32, height: i32) -> Self {
        let len = (width as usize) * (height as usize);
        Grid {
            data: slice::from_raw_parts(data, len),
            width: width as i64,
            height: height as i64,
        }
    }

    #[inline]
    fn is_solid(&self, x: f64, y: f64) -> bool {
        if x < 0.0 || y < 0.0 {
            return false;
        }
        let xi = x as i64; // truncation == Python int() for non-negative values
        let yi = y as i64;
        if xi >= self.width || yi >= self.height {
            return false;
        }
        self.data[(yi * self.width + xi) as usize] == 1
    }

    #[inline]
    fn circle_collides(&self, cx: f64, cy: f64, radius: f64) -> bool {
        for &(ox, oy) in &config().circle_points {
            let x = cx + ox * radius;
            let y = cy + oy * radius;
            if x < 0.0 || y < 0.0 {
                continue;
            }
            let xi = x as i64;
            let yi = y as i64;
            if xi < self.width
                && yi < self.height
                && self.data[(yi * self.width + xi) as usize] == 1
            {
                return true;
            }
        }
        false
    }

    fn normal_at(&self, x: f64, y: f64, radius: i64) -> (f64, f64) {
        let mut nx = 0.0f64;
        let mut ny = 0.0f64;
        for dy in -radius..=radius {
            for dx in -radius..=radius {
                if dx * dx + dy * dy <= radius * radius
                    && self.is_solid(x + dx as f64, y + dy as f64)
                {
                    nx -= dx as f64;
                    ny -= dy as f64;
                }
            }
        }
        let length = (nx * nx + ny * ny).sqrt();
        if length < 1e-6 {
            return (0.0, -1.0);
        }
        (nx / length, ny / length)
    }
}

/// Worm table shared with Python: (x, y, radius, flags) per worm in `World.worms` order.
/// flags bit 0 = alive, bit 1 = collides with bodies.
const W_LEN: usize = 4;

/// The other worms that can block a moving body: the whole table minus `self_index`.
#[derive(Clone, Copy)]
struct Others<'a> {
    table: &'a [f64],
    self_index: i64,
    enabled: bool, // the moving body itself collides with bodies
}

impl<'a> Others<'a> {
    unsafe fn new(table: *const f64, n: i32, self_index: i32, enabled: i32) -> Self {
        Others {
            table: slice::from_raw_parts(table, (n as usize) * W_LEN),
            self_index: self_index as i64,
            enabled: enabled != 0,
        }
    }

    /// Mirror of `PhysicsWorld.blocking_body`: index of the first worm that blocks a move of a
    /// body (radius `r`, currently at `cur`) to (x, y), or -1.
    fn blocking_index(&self, x: f64, y: f64, r: f64, cur_x: f64, cur_y: f64) -> i32 {
        if !self.enabled {
            return -1;
        }
        for (i, other) in self.table.chunks_exact(W_LEN).enumerate() {
            let flags = other[3] as i64;
            if i as i64 == self.self_index || flags & 1 == 0 || flags & 2 == 0 {
                continue;
            }
            let (ox, oy, or) = (other[0], other[1], other[2]);
            let reach = r + or;
            let reach_sq = reach * reach;
            let ax = ox - x;
            let ay = oy - y;
            let new_sq = ax * ax + ay * ay;
            if new_sq >= reach_sq {
                continue;
            }
            let bx = ox - cur_x;
            let by = oy - cur_y;
            let current_sq = bx * bx + by * by;
            if current_sq <= reach_sq && new_sq >= current_sq {
                continue;
            }
            return i as i32;
        }
        -1
    }

    fn x_of(&self, index: i32) -> f64 {
        self.table[(index as usize) * W_LEN]
    }
}

// --------------------------------------------------------------------------------- setup

#[no_mangle]
pub extern "C" fn wk_version() -> i32 {
    KERNEL_VERSION
}

/// `points`: 2*n doubles (centre first, then rim offsets). Returns 1 on success, 0 if the kernel
/// was already initialised with different values.
#[no_mangle]
pub unsafe extern "C" fn wk_init(
    points: *const f64,
    n: i32,
    worm_radius: f64,
    projectile_max_age: f64,
) -> i32 {
    let raw = slice::from_raw_parts(points, (n as usize) * 2);
    let circle_points: Vec<(f64, f64)> = raw.chunks_exact(2).map(|p| (p[0], p[1])).collect();
    let wanted = Config {
        circle_points,
        worm_radius,
        projectile_max_age,
    };
    let stored = CONFIG.get_or_init(|| Config {
        circle_points: wanted.circle_points.clone(),
        worm_radius,
        projectile_max_age,
    });
    let same = stored.circle_points == wanted.circle_points
        && stored.worm_radius == wanted.worm_radius
        && stored.projectile_max_age == wanted.projectile_max_age;
    same as i32
}

// ------------------------------------------------------------------------------- terrain

#[no_mangle]
pub unsafe extern "C" fn wk_circle_collides(
    data: *const u8,
    width: i32,
    height: i32,
    cx: f64,
    cy: f64,
    radius: f64,
) -> i32 {
    Grid::new(data, width, height).circle_collides(cx, cy, radius) as i32
}

#[no_mangle]
pub unsafe extern "C" fn wk_normal_at(
    data: *const u8,
    width: i32,
    height: i32,
    x: f64,
    y: f64,
    radius: i32,
    out: *mut f64,
) {
    let (nx, ny) = Grid::new(data, width, height).normal_at(x, y, radius as i64);
    *out = nx;
    *out.add(1) = ny;
}

/// Mirror of `Terrain._set_circle` (integer circle rows, clipped to the grid).
#[no_mangle]
pub unsafe extern "C" fn wk_set_circle(
    data: *mut u8,
    width: i32,
    height: i32,
    cx: f64,
    cy: f64,
    radius: f64,
    value: u8,
) {
    let len = (width as usize) * (height as usize);
    let grid = slice::from_raw_parts_mut(data, len);
    let (w, h) = (width as i64, height as i64);
    let r = radius as i64;
    let (icx, icy) = (cx as i64, cy as i64);
    for dy in -r..=r {
        let y = icy + dy;
        if y < 0 || y >= h {
            continue;
        }
        let half = (((r * r - dy * dy).max(0)) as f64).sqrt() as i64;
        let x0 = (icx - half).max(0);
        let x1 = (icx + half + 1).min(w);
        if x1 <= x0 {
            continue;
        }
        let start = (y * w) as usize;
        grid[start + x0 as usize..start + x1 as usize].fill(value);
    }
}

// -------------------------------------------------------------------------------- bodies

/// -2 = terrain blocks, -1 = free, i >= 0 = blocked by worm `i` of the table.
#[no_mangle]
pub unsafe extern "C" fn wk_body_collides(
    data: *const u8,
    width: i32,
    height: i32,
    x: f64,
    y: f64,
    radius: f64,
    cur_x: f64,
    cur_y: f64,
    table: *const f64,
    n: i32,
    self_index: i32,
    enabled: i32,
) -> i32 {
    let grid = Grid::new(data, width, height);
    if grid.circle_collides(x, y, radius) {
        return -2;
    }
    Others::new(table, n, self_index, enabled).blocking_index(x, y, radius, cur_x, cur_y)
}

/// Mirror of the sub-step loop in `World._update_worm`: moves the worm (state = [x, y]) in
/// `steps` increments of (sx, sy) until the next position collides. Returns 1 on contact (the
/// colliding position is written to out[0..2]) and 0 if all steps were free.
#[no_mangle]
pub unsafe extern "C" fn wk_fly(
    data: *const u8,
    width: i32,
    height: i32,
    state: *mut f64,
    sx: f64,
    sy: f64,
    steps: i64,
    radius: f64,
    table: *const f64,
    n: i32,
    self_index: i32,
    enabled: i32,
    out: *mut f64,
) -> i32 {
    let grid = Grid::new(data, width, height);
    let others = Others::new(table, n, self_index, enabled);
    let mut x = *state;
    let mut y = *state.add(1);
    let mut contact = 0;
    for _ in 0..steps {
        let nx = x + sx;
        let ny = y + sy;
        let blocked = grid.circle_collides(nx, ny, radius)
            || others.blocking_index(nx, ny, radius, x, y) >= 0;
        if !blocked {
            x = nx;
            y = ny;
            continue;
        }
        *out = nx;
        *out.add(1) = ny;
        contact = 1;
        break;
    }
    *state = x;
    *state.add(1) = y;
    contact
}

// ------------------------------------------------------------------------------- walking

struct Walker<'a> {
    grid: Grid<'a>,
    others: Others<'a>,
    radius: f64,
    x: f64,
    y: f64,
    grounded: bool,
}

impl<'a> Walker<'a> {
    /// Mirror of `World.worm_collides` for the walking worm at its current position.
    fn collides(&self, x: f64, y: f64) -> bool {
        self.grid.circle_collides(x, y, self.radius)
            || self
                .others
                .blocking_index(x, y, self.radius, self.x, self.y)
                >= 0
    }

    /// Mirror of `World._commit_step`.
    fn commit(&mut self, nx: f64, climb: i64, max_drop: i64) {
        self.x = nx;
        self.y -= climb as f64;
        for _ in 0..=max_drop {
            if self.collides(self.x, self.y + 1.0) {
                return;
            }
            self.y += 1.0;
        }
        self.grounded = false;
    }

    /// Mirror of `World._walk_step`.
    fn step(&mut self, direction: i64, max_climb: i64, crawl_climb: i64, crawl: bool) -> bool {
        let worm_radius = config().worm_radius;
        let nx = self.x + direction as f64;
        if nx < worm_radius || nx > self.grid.width as f64 - worm_radius {
            return false;
        }
        let climb = (0..=max_climb).find(|&c| {
            !self
                .grid
                .circle_collides(nx, self.y - c as f64, self.radius)
        });
        let Some(climb) = climb else { return false };
        let blocker =
            self.others
                .blocking_index(nx, self.y - climb as f64, self.radius, self.x, self.y);
        if blocker < 0 {
            self.commit(nx, climb, max_climb);
            return true;
        }
        if !crawl {
            return false;
        }
        let other_x = self.others.x_of(blocker);
        let beyond = other_x + (direction as f64) * (2.0 * worm_radius + 2.0);
        if self
            .grid
            .circle_collides(beyond, self.y - max_climb as f64, self.radius)
        {
            return false;
        }
        for c in (climb + 1)..=crawl_climb {
            if !self.collides(nx, self.y - c as f64) {
                self.commit(nx, c, crawl_climb);
                return true;
            }
        }
        false
    }
}

/// Mirror of `World._walk_steps`. state = [x, y, walk_progress, grounded];
/// out = [moved, pixels walked, fell off a ledge].
#[no_mangle]
pub unsafe extern "C" fn wk_walk(
    data: *const u8,
    width: i32,
    height: i32,
    state: *mut f64,
    direction: i32,
    radius: f64,
    max_climb: i32,
    crawl_climb: i32,
    crawl: i32,
    table: *const f64,
    n: i32,
    self_index: i32,
    enabled: i32,
    out: *mut f64,
) {
    let state = slice::from_raw_parts_mut(state, 4);
    let out = slice::from_raw_parts_mut(out, 3);
    let mut walker = Walker {
        grid: Grid::new(data, width, height),
        others: Others::new(table, n, self_index, enabled),
        radius,
        x: state[0],
        y: state[1],
        grounded: state[3] != 0.0,
    };
    let mut progress = state[2];
    let mut moved = true;
    let mut distance = 0.0;
    let mut fell = false;
    while progress >= 1.0 {
        progress -= 1.0;
        if !walker.step(
            direction as i64,
            max_climb as i64,
            crawl_climb as i64,
            crawl != 0,
        ) {
            progress = 0.0;
            moved = false;
            break;
        }
        distance += 1.0;
        if !walker.grounded {
            progress = 0.0;
            fell = true;
            break;
        }
    }
    state[0] = walker.x;
    state[1] = walker.y;
    state[2] = progress;
    state[3] = if walker.grounded { 1.0 } else { 0.0 };
    out[0] = if moved { 1.0 } else { 0.0 };
    out[1] = distance;
    out[2] = if fell { 1.0 } else { 0.0 };
}

// --------------------------------------------------------------------------- projectiles

/// Projectile state layout shared with Python (`src/core/native.py`).
const P_X: usize = 0;
const P_Y: usize = 1;
const P_VX: usize = 2;
const P_VY: usize = 3;
const P_AGE: usize = 4;
const P_FUSE: usize = 5;
const P_HAS_FUSE: usize = 6;
const P_BOUNCE: usize = 7;
const P_HAS_BOUNCE: usize = 8;
const P_WIND_FACTOR: usize = 9;
const P_ASLEEP: usize = 10;
const P_OWNER: usize = 11; // index of the owner in the worm table, -1 if none
const P_LEN: usize = 12;

const RESULT_NONE: i32 = 0;
const RESULT_EXPLODE: i32 = 1;
const RESULT_GONE: i32 = 2;

struct StepEnv<'a> {
    grid: Grid<'a>,
    wind: f64,
    wind_acceleration: f64,
    gravity: f64,
    water_level: f64,
    /// (x, y) pairs of the living worms, in Python's order.
    worms: &'a [f64],
}

/// Mirror of `world.step_projectile`.
fn step_projectile(p: &mut [f64], env: &StepEnv, dt: f64) -> i32 {
    let cfg = config();
    p[P_AGE] += dt;
    if p[P_HAS_FUSE] != 0.0 {
        p[P_FUSE] -= dt;
        if p[P_FUSE] <= 0.0 {
            return RESULT_EXPLODE;
        }
    }
    if p[P_AGE] > cfg.projectile_max_age {
        return RESULT_EXPLODE;
    }
    let grid = &env.grid;
    if p[P_ASLEEP] != 0.0 {
        if grid.is_solid(p[P_X], p[P_Y] + 3.0) {
            return RESULT_NONE;
        }
        p[P_ASLEEP] = 0.0;
    }

    p[P_VX] += env.wind * env.wind_acceleration * p[P_WIND_FACTOR] * dt;
    p[P_VY] += env.gravity * dt;
    let dx = p[P_VX] * dt;
    let dy = p[P_VY] * dt;
    let distance = dy.abs().max(dx.abs());
    let steps = (distance / 2.0) as i64 + 1;
    let sx = dx / steps as f64;
    let sy = dy / steps as f64;
    let hit_radius = cfg.worm_radius + 2.0;
    let hit_radius_sq = hit_radius * hit_radius;

    let has_bounce = p[P_HAS_BOUNCE] != 0.0;
    let mut targets: Vec<(f64, f64)> = Vec::new(); // allocates only if a worm is in reach
    if !has_bounce {
        let reach = distance + cfg.worm_radius + 4.0;
        let owner = p[P_OWNER] as i64;
        for (i, worm) in env.worms.chunks_exact(2).enumerate() {
            if i as i64 == owner && p[P_AGE] < 0.3 {
                continue;
            }
            if (worm[0] - p[P_X]).abs() < reach && (worm[1] - p[P_Y]).abs() < reach {
                targets.push((worm[0], worm[1]));
            }
        }
    }

    let mut x = p[P_X];
    let mut y = p[P_Y];
    for _ in 0..steps {
        let nx = x + sx;
        let ny = y + sy;
        for &(wx, wy) in &targets {
            let ax = wx - nx;
            let ay = wy - ny;
            if ax * ax + ay * ay <= hit_radius_sq {
                p[P_X] = nx;
                p[P_Y] = ny;
                return RESULT_EXPLODE;
            }
        }
        if grid.is_solid(nx, ny) {
            p[P_X] = x;
            p[P_Y] = y;
            if !has_bounce {
                p[P_X] = nx;
                p[P_Y] = ny;
                return RESULT_EXPLODE;
            }
            let (normal_x, normal_y) = grid.normal_at(nx, ny, 4);
            let dot = p[P_VX] * normal_x + p[P_VY] * normal_y;
            if dot < 0.0 {
                p[P_VX] -= 2.0 * dot * normal_x;
                p[P_VY] -= 2.0 * dot * normal_y;
            }
            p[P_VX] *= p[P_BOUNCE];
            p[P_VY] *= p[P_BOUNCE];
            let speed = (p[P_VX] * p[P_VX] + p[P_VY] * p[P_VY]).sqrt();
            if speed < 30.0 && normal_y < -0.5 {
                p[P_VX] = 0.0;
                p[P_VY] = 0.0;
                p[P_ASLEEP] = 1.0;
            }
            return RESULT_NONE;
        }
        x = nx;
        y = ny;
    }
    p[P_X] = x;
    p[P_Y] = y;

    if p[P_Y] > env.water_level || p[P_X] < -300.0 || p[P_X] > (grid.width + 300) as f64 {
        return RESULT_GONE;
    }
    RESULT_NONE
}

/// Steps projectiles `start..n` in order (mirror of the loop in `World.update`) and stops at the
/// first one that ends, because its explosion changes the world before the next one moves.
/// Returns `index * 4 + result` for that projectile, or `n * 4` when none ended.
#[no_mangle]
pub unsafe extern "C" fn wk_step_projectiles(
    data: *const u8,
    width: i32,
    height: i32,
    states: *mut f64,
    start: i32,
    n: i32,
    wind: f64,
    wind_acceleration: f64,
    gravity: f64,
    dt: f64,
    water_level: f64,
    worms: *const f64,
    n_worms: i32,
) -> i32 {
    let env = StepEnv {
        grid: Grid::new(data, width, height),
        wind,
        wind_acceleration,
        gravity,
        water_level,
        worms: slice::from_raw_parts(worms, (n_worms as usize) * 2),
    };
    let states = slice::from_raw_parts_mut(states, (n as usize) * P_LEN);
    for index in (start as usize)..(n as usize) {
        let p = &mut states[index * P_LEN..(index + 1) * P_LEN];
        let result = step_projectile(p, &env, dt);
        if result != RESULT_NONE {
            return (index as i32) * 4 + result;
        }
    }
    n * 4
}

/// Mirror of `ai.simulate_projectiles`: dry-runs `n` projectiles (states are modified) and writes
/// (result, x, y) per projectile to `out`; result is 1 for a detonation and 0 for a lost shot.
#[no_mangle]
pub unsafe extern "C" fn wk_simulate(
    data: *const u8,
    width: i32,
    height: i32,
    states: *mut f64,
    n: i32,
    wind: f64,
    wind_acceleration: f64,
    gravity: f64,
    dt: f64,
    water_level: f64,
    worms: *const f64,
    n_worms: i32,
    max_time: f64,
    out: *mut f64,
) {
    let env = StepEnv {
        grid: Grid::new(data, width, height),
        wind,
        wind_acceleration,
        gravity,
        water_level,
        worms: slice::from_raw_parts(worms, (n_worms as usize) * 2),
    };
    let states = slice::from_raw_parts_mut(states, (n as usize) * P_LEN);
    let out = slice::from_raw_parts_mut(out, (n as usize) * 3);
    for (p, result) in states.chunks_exact_mut(P_LEN).zip(out.chunks_exact_mut(3)) {
        result[0] = 0.0;
        let mut elapsed = 0.0f64;
        while elapsed < max_time {
            let r = step_projectile(p, &env, dt);
            if r == RESULT_EXPLODE {
                result[0] = 1.0;
                result[1] = p[P_X];
                result[2] = p[P_Y];
                break;
            }
            if r == RESULT_GONE {
                break;
            }
            elapsed += dt;
        }
    }
}

/// For every worm in the table: does a circle one pixel below its position collide (the
/// "still standing" check of `World._update_worm`)? Writes 1.0/0.0 per worm into `out`.
#[no_mangle]
pub unsafe extern "C" fn wk_ground_mask(
    data: *const u8,
    width: i32,
    height: i32,
    table: *const f64,
    n: i32,
    out: *mut f64,
) {
    let grid = Grid::new(data, width, height);
    let rows = slice::from_raw_parts(table, (n as usize) * W_LEN);
    let out = slice::from_raw_parts_mut(out, n as usize);
    for (i, row) in rows.chunks_exact(W_LEN).enumerate() {
        let (x, y, r, flags) = (row[0], row[1], row[2], row[3] as i64);
        let others = Others {
            table: rows,
            self_index: i as i64,
            enabled: flags & 2 != 0,
        };
        let below = y + 1.0;
        let hit =
            grid.circle_collides(x, below, r) || others.blocking_index(x, below, r, x, y) >= 0;
        out[i] = if hit { 1.0 } else { 0.0 };
    }
}
