[app]
title = 万能格式转换器
package.name = fileconverter
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0.0
requirements = python3,kivy,pillow,plyer
orientation = portrait
fullscreen = 0
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 31
android.minapi = 24
android.archs = arm64-v8a
android.ndk_api = 24
android.allow_backup = True
android.keep_android_archs = True

[buildozer]
log_level = 2
warn_on_root = 1
