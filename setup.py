from cx_Freeze import setup, Executable

base = "Win32GUI"
# path_platforms = ("platforms\qwindows.dll" )
# build_options = {"includes": ["re", "atexit"], "include_files": [path_platforms]}

setup(
    name="Video Annotation Tool",
    version="0.1",
    description="A tool for manual annotation of objects in video",
    # options={"build_exe": build_options},
    executables=[Executable("AnnotationTool.py", base=base, requires=['numpy'], requires=['cv2'], requires=['PyQt5'],
                            requires=['cv2'], requires=['PyQt5'], requires=['numpy'])]
)
