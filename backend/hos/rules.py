"""HOS constants (HOS_ENGINE_SPEC sections 1.2 and 1.3). All values are integer minutes unless noted."""

GRID = 15  # every event boundary is a multiple of this
DAY_MIN = 1440

REST_MIN = 600  # 10 consecutive hours off before driving
WINDOW_MIN = 840  # 14 hour driving window
DRIVE_LIMIT_MIN = 660  # 11 hour driving limit
BREAK_AFTER_MIN = 480  # 30 min break required after 8 cumulative driving hours
BREAK_MIN = 30
CYCLE_LIMIT_MIN = 4200  # 70 hr / 8 day
RESTART_MIN = 2040  # 34 hour restart

PRE_TRIP_MIN = 30
STOP_MIN = 60  # pickup and dropoff
FUEL_STOP_MIN = 30
FUEL_MAX_MILES = 1000

START_RESTART_THRESHOLD_MIN = 45  # cycle >= 69.5 hr at trip start takes a restart first
START_MIN_MAX = DAY_MIN - GRID  # latest start on day 0
MAX_SPEED_MPH = 100  # sanity bound on ORS legs
MAX_STEPS_PER_LEG = 1000  # progress guard

CYCLE_RESTART_AT_START = "CYCLE_RESTART_AT_START"

MAX_LEG_DURATION_MIN = 20160  # 14 days of driving per leg
MIN_SPEED_MPH = 5  # slower average speeds are upstream data errors
MAX_LABEL_LEN = 200
