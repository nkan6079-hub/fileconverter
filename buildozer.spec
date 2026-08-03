[app]
title = 万能格式转换器
package.name = fileconverter
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0.0
requirements = python3,kivy,pillow,plyer,pymupdf
orientation = portrait
fullscreen = 0
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 30
android.minapi = 21
android.archs = arm64-v8a,armeabi-v7a
android.ndk_api = 24
android.allow_backup = True
android.keep_android_archs = True

[buildozer]
log_level = 2
warn_on_root = 1
