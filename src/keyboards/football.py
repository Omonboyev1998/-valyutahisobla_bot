from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from src.config import WEB_APP_URL

def get_leagues_keyboard() -> InlineKeyboardMarkup:
    """Chempionatlar ro'yxati inline tugmalari"""
    buttons = [
        [
            InlineKeyboardButton(text="📺 TV kanallar", callback_data="fb_streams"),
            InlineKeyboardButton(text="📱 Mini Appda Ko'rish", web_app=WebAppInfo(url=WEB_APP_URL))
        ],
        [
            InlineKeyboardButton(text="🏴󠁧󠁢󠁥󠁮󠁧󠁿 APL (Angliya)", callback_data="fb_menu:eng.1"),
            InlineKeyboardButton(text="🇪🇸 La Liga (Ispaniya)", callback_data="fb_menu:esp.1")
        ],
        [
            InlineKeyboardButton(text="🇮🇹 Serie A (Italiya)", callback_data="fb_menu:ita.1"),
            InlineKeyboardButton(text="🇩🇪 Bundesliga (Germaniya)", callback_data="fb_menu:ger.1")
        ],
        [
            InlineKeyboardButton(text="🏆 Chempionlar Ligasi", callback_data="fb_menu:uefa.champions")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_streams_keyboard(streams: list = None) -> InlineKeyboardMarkup:
    """Jonli translatsiyalar va Famelack telekanallari bosh menyusi"""
    buttons = [
        [
            InlineKeyboardButton(text="📱 Mini Appda Barcha 205 Kanalni Ko'rish", web_app=WebAppInfo(url=WEB_APP_URL))
        ],
        [
            InlineKeyboardButton(text="🇺🇿 O'zbekiston Kanallari (35 ta)", callback_data="tv_sub:uz"),
            InlineKeyboardButton(text="⚽️ Dunyo Sport Kanallari (170 ta)", callback_data="tv_sub:sports")
        ],
        [
            InlineKeyboardButton(text="◀️ Futbol va Chempionatlar", callback_data="fb_leagues")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_tv_sub_keyboard(sub_type: str) -> InlineKeyboardMarkup:
    """Telekanallar toifalari bo'yicha tezkor havolalar"""
    buttons = [
        [
            InlineKeyboardButton(text="📱 Mini Appda Jonli Pleyerni Ochish", web_app=WebAppInfo(url=WEB_APP_URL))
        ]
    ]
    if sub_type == "uz":
        buttons.extend([
            [
                InlineKeyboardButton(text="🎭 Zo'r TV", url="https://stream8.cinerama.uz/1016/tracks-v1a1/mono.m3u8"),
                InlineKeyboardButton(text="⚽️ Futbol TV", url="https://stream3.cinerama.uz/1010/tracks-v1a1/mono.m3u8")
            ],
            [
                InlineKeyboardButton(text="🏆 Sport TV", url="https://stream8.cinerama.uz/1004/tracks-v1a1/mono.m3u8"),
                InlineKeyboardButton(text="❤️ Sevimli TV", url="https://stream8.cinerama.uz/1017/tracks-v1a1/playlist.m3u8")
            ],
            [
                InlineKeyboardButton(text="🎬 Milliy TV", url="https://stream8.cinerama.uz/1014/tracks-v1a1/playlist.m3u8"),
                InlineKeyboardButton(text="⭐️ MY5 TV", url="https://stream8.cinerama.uz/1217/tracks-v1a1/playlist.m3u8")
            ],
            [
                InlineKeyboardButton(text="🍿 Kinoteatr", url="https://stream8.cinerama.uz/1009/tracks-v1a1/playlist.m3u8"),
                InlineKeyboardButton(text="🔴 O'zbekiston 24", url="https://stream8.cinerama.uz/1011/tracks-v1a1/playlist.m3u8")
            ]
        ])
    else:
        buttons.extend([
            [
                InlineKeyboardButton(text="👑 Real Madrid TV", url="https://rmtv.akamaized.net/hls/live/2043153/rmtv-es-web/master.m3u8"),
                InlineKeyboardButton(text="🔵 Inter TV", url="https://d3k8wzt41aflvx.cloudfront.net/INTERTV/Live.m3u8")
            ],
            [
                InlineKeyboardButton(text="🇹🇷 A Spor", url="https://rnttwmjcin.turknet.ercdn.net/lcpmvefbyo/aspor/aspor.m3u8"),
                InlineKeyboardButton(text="🇷🇺 Match! Ultra 4K", url="https://flussonic.linkintel.ru/match/index.m3u8")
            ],
            [
                InlineKeyboardButton(text="🇺🇸 CBS Sports Golazo", url="https://dai.google.com/linear/hls/event/7f3Wv6f7QEKfQna22jHqLQ/master.m3u8"),
                InlineKeyboardButton(text="🐂 Red Bull TV", url="https://rbmn-live.akamaized.net/hls/live/590964/BoRB-AT/master.m3u8")
            ]
        ])
    buttons.append([
        InlineKeyboardButton(text="◀️ Telekanallar menyusiga qaytish", callback_data="fb_streams")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_league_actions_keyboard(league_code: str) -> InlineKeyboardMarkup:
    """Tanlangan liga uchun menyu"""
    buttons = [
        [
            InlineKeyboardButton(text="🏆 Turnir jadvali", callback_data=f"fb_table:{league_code}"),
            InlineKeyboardButton(text="⚽️ O'yinlar & Natijalar", callback_data=f"fb_matches:{league_code}")
        ],
        [
            InlineKeyboardButton(text="📺 TV kanallar", callback_data="fb_streams")
        ],
        [
            InlineKeyboardButton(text="◀️ Boshqa chempionatlar", callback_data="fb_leagues")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_football_back_keyboard(league_code: str) -> InlineKeyboardMarkup:
    """Liganing asosiy bo'limiga qaytish"""
    buttons = [
        [
            InlineKeyboardButton(text="◀️ Ortga", callback_data=f"fb_menu:{league_code}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
