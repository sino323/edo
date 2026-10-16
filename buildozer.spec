[app]
title = Jarvis
package.name = jarvis
package.domain = org.jarvis
source.dir = .
source.include_exts = py,png,jpg,ttf,json
source.exclude_dirs = .git,.github,bin,venv,__pycache__
source.exclude_patterns = desktop.py
version = 1.0.0
requirements = python3,kivy==2.3.0,requests,urllib3,idna,charset-normalizer,certifi,plyer,pyjnius,arabic-reshaper==3.0.0,python-bidi==0.4.2,six
icon.filename = %(source.dir)s/assets/icon.png
icon.adaptive_foreground.filename = %(source.dir)s/assets/icon_fg.png
icon.adaptive_background.filename = %(source.dir)s/assets/icon_bg.png
presplash.filename = %(source.dir)s/assets/presplash.png
android.presplash_color = #02080C
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,RECORD_AUDIO,ACCESS_WIFI_STATE,CHANGE_WIFI_MULTICAST_STATE,SET_ALARM,QUERY_ALL_PACKAGES
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.ndk = 25b
p4a.branch = v2024.01.21
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
