[app]
title = ChemSmart
project_dir = .
input_file = chemsmart/gui/__main__.py
exec_directory = build/p1/pyside6-deploy/dist
project_file =
icon =

[python]
python_path =
packages = Nuitka==2.7.11
android_packages =

[qt]
qml_files =
excluded_qml_plugins =
modules = Core,Gui,Network,WebEngineCore,WebEngineWidgets,Widgets
plugins =

[android]
wheel_pyside =
wheel_shiboken =
plugins =

[nuitka]
macos.permissions =
mode = standalone
extra_args = --quiet --noinclude-qt-translations --include-package=chemsmart --include-package-data=chemsmart --include-module=anthropic --include-module=openai --nofollow-import-to=chemsmart.agent.tui.*,textual,watchdog,pyperclip,chemsmart.agent.local.*,mlx,mlx_lm,torch,transformers --no-deployment-flag=self-execution --macos-app-name=ChemSmart --macos-signed-app-name=org.zhanglab.chemsmart --macos-app-version=2.0.1 --macos-app-mode=gui --macos-target-arch=arm64 --report=build/p1/pyside6-deploy/nuitka-report.xml

[buildozer]
mode = debug
recipe_dir =
jars_dir =
ndk_path =
sdk_path =
local_libs =
arch =
