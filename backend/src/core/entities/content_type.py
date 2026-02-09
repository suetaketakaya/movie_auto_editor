"""Content type enum for different video montage styles."""

from enum import Enum


class ContentType(str, Enum):
    FPS_MONTAGE = "fps_montage"
    MAD_AMV = "mad_amv"
    SPORTS_HIGHLIGHT = "sports_highlight"
    ANIME_PV = "anime_pv"
    MUSIC_VIDEO = "music_video"
    GENERAL = "general"
