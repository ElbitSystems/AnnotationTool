# AnnotationTool
Video ground truth annotation tool for manual object marking.
Currently works on .avi video files and on images.

# Dependencies:
1. python 3
2. pyqt 5
3. opencv (cv2)

Annotations are saved in a sql file (suffix .atc) and can be opened with standard tools such as sqliteviewer.
They can be exported to color .png's (useful mainly for visualization) or to single channel 16-bit tiff images.