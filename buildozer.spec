[app]
title = Matrix Dunk
package.name = matrixdunk
package.domain = org.lecahi
source.dir = .
source.include_exts = py,png,jpg,json
version = 0.1
requirements = python3,pygame,android,shutil,json
orientation = portrait
fullscreen = 1
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
