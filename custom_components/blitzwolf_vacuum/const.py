"""Constants for the BlitzWolf Vacuum integration."""

DOMAIN = "blitzwolf_vacuum"
MANUFACTURER = "BlitzWolf"
PLATFORMS = ["vacuum"]

# Slamtec Cloud
CLOUD_URL = "https://cloud.slamtec.com"
MQTT_HOST = "iot.slamtec.com"
MQTT_PORT = 8883

# OAuth2 credentials (decoded from app)
OAUTH_CLIENT_ID = "blitz_wolf"
OAUTH_CLIENT_SECRET = "y@c9w&L7Ht"

# Config keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"

# MQTT topics (formatted with device_id)
TOPIC_PUB = "device/{}/robot"
TOPIC_SUB = "device/{}/app"

# ── MQTT Function Codes: App → Robot ──────────────────────────
CMD_JOYSTICK = 20
CMD_ACTION = 24             # p=1: start sweep, p=2: pause
CMD_GET_SWEEP_MODE = 25
CMD_GET_STATUS = 26
CMD_SPOT_CLEAN = 27         # p: {"x": float, "y": float}
CMD_MOVE_TO = 28            # p: {"x": float, "y": float}
CMD_SET_VIRTUAL_WALL = 29
CMD_GET_MAP = 33
CMD_GET_BATTERY = 34
CMD_STOP = 35
CMD_DOCK = 36               # Return to charging dock
CMD_START_UPDATE = 40       # Subscribe to real-time data
CMD_STOP_UPDATE = 41
CMD_GET_INFO = 42
CMD_ROBO_TRACK = 53
CMD_SET_SWEEP_MODE = 59     # p: 0=normal, 1=silence, 2=high, 3=full
CMD_CHILD_LOCK = 61         # p: true/false
CMD_GET_DEVICE_INFO = 62
CMD_SILENCE_MODE = 63
CMD_GET_REGIONS = 64
CMD_START_REGION_CLEAN = 68
CMD_SET_MAP = 72
CMD_GET_NETWORK = 77
CMD_SET_SWEEP_DIR = 78      # p: 0=horizontal, 1=vertical, 2=net

# ── MQTT Function Codes: Robot → App ─────────────────────────
RESP_POSE = 1
RESP_CURRENT_ACTION = 2
RESP_BATTERY = 3
RESP_CHARGING = 4
RESP_DC_CONNECTED = 5
RESP_TEMPERATURE = 6
RESP_EXPLORE_MAP = 7
RESP_SWEEP_MAP = 8
RESP_VIRTUAL_WALL = 9
RESP_SWEEP_TIME = 12
RESP_FW_PROCESS = 13
RESP_FW_INFO = 14
RESP_FULL_MAP = 17
RESP_ROBO_TRACK = 19
RESP_DOCK_POSE = 22
RESP_NETWORK_INFO = 24
RESP_SWEEP_MODE = 25
RESP_SWEEP_REGIONS = 28
RESP_SWEEP_MOP_MODE = 32
RESP_SYSTEM_EVENT = 50

# ── Sweep Modes (fan speed) ──────────────────────────────────
SWEEP_MODES = {
    0: "Normal",
    1: "Silence",
    2: "High",
    3: "Full",
}
SWEEP_MODE_LIST = ["Normal", "Silence", "High", "Full"]
SWEEP_MODE_TO_INT = {v: k for k, v in SWEEP_MODES.items()}

# ── Robot Action States ──────────────────────────────────────
ACTION_IDLE = 0
ACTION_SWEEPING = 1
ACTION_GOING_HOME = 2
ACTION_CHARGING = 3
ACTION_EXPLORING = 4
ACTION_STUCK = 5
ACTION_PAUSED = 6
