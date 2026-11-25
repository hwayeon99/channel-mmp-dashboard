"""Dashboard settings. Edit here, not in loader/app."""
import os
from pathlib import Path

# CSVs live in the project root (parent of dashboard/). Override with env DASHBOARD_DATA_DIR.
DATA_DIR = Path(os.environ.get("DASHBOARD_DATA_DIR", Path(__file__).resolve().parent.parent))

# AppsFlyer media_source -> channel name used in channel CSV
MEDIA_SOURCE_MAP = {
    "googleadwords_int": "구글",
    "Facebook Ads": "메타",
    "naver_search": "네이버",
}

# Join keys between channel CSV and MMP CSV
KEYS = ["date", "channel", "campaign", "group", "creative"]

# |MMP / channel - 1| above this (percent) is flagged on the validation tab
GAP_THRESHOLD_PCT = 30.0

# Korean column headers in the source CSVs -> internal English names
CHANNEL_COLS = {
    "일": "date", "채널": "channel", "채널분류": "channel_type", "캠페인": "campaign",
    "캠페인목적": "objective", "그룹": "group", "소재": "creative", "노출": "impressions",
    "클릭": "clicks_ch", "비용": "cost", "회원가입": "signups_ch", "구매": "purchases_ch",
    "구매매출": "revenue_ch",
}
MMP_COLS = {
    "일": "date", "미디어소스": "media_source", "캠페인": "campaign", "그룹": "group",
    "소재": "creative", "클릭": "clicks_mmp", "회원가입": "signups_mmp",
    "구매": "purchases_mmp", "구매매출": "revenue_mmp",
}

# Display labels
SOURCE_LABEL = {"ch": "매체", "mmp": "MMP"}
LEVEL_COLS = {"채널": ["channel"], "캠페인": ["channel", "campaign"],
              "그룹": ["channel", "campaign", "group"],
              "소재": ["channel", "campaign", "group", "creative"]}
