# AnnotationTool
Video ground truth annotation tool for manual object marking.
Currently works on .avi video files and on images.

# Dependencies:
1. python 3
2. pyqt 5
3. opencv (cv2)

Annotations are saved in a sql file (suffix .atc) and can be opened with standard tools such as sqliteviewer.
They can be exported to color .png's (useful mainly for visualization) or to single channel 16-bit tiff images.

# Application Usage

## Create New Annotation

In order to create new Annotation, navigate to File-\>New in the application menu.

In a new dialog window, navigate to the desired video file (Optional: image files) to annotate.

#### Note:

The created Annotation is not saved unless requested to save it on purpose. For more info see Saving Annotation\<link\>

## Saving Annotation

Saving the Annotation under work is done using File-\>Save As menu.

![](media/image1.png)

A ‘\*’ on the application title will indicate that the file is not saved. The application title will also show the path to the working Annotation file.

Once an Annotation is saved, any changes will be committed to the disk immediately.

## Open Existing Annotation

In order to continue working on previous Annotation, open the Annotation file using File-\>Open menu.

## Annotate Video

To annotate an object in the video, mark its contour on the displayed frame using a left button mouse click.

The marked annotation will appear on the frame image.

The annotation can be dragged to change its position.

![](https://cloud.githubusercontent.com/assets/5520561/12976846/88740ee0-d0cf-11e5-8f15-33f47e4b6492.png)

## Modify Annotation

To modify an annotation, press it using a right button mouse click and move the mouse to create a new contour.

While modifying an annotation, its old contour would still appear on frame image but will be grayed out.

![](https://cloud.githubusercontent.com/assets/5520561/12976851/88a133f2-d0cf-11e5-8d6b-168db2cbd611.png)

After releasing the mouse button, only the new contour will be displayed.

![](https://cloud.githubusercontent.com/assets/5520561/12976848/889d19b6-d0cf-11e5-9921-6fb8326a10bb.png)

## Annotation Class

To create a new class select ‘(new)’ from the class list combo box and enter the class name in a new dialog.

![](https://cloud.githubusercontent.com/assets/5520561/12977406/21a8b838-d0d3-11e5-846b-928fbaf865ee.png)

![](https://cloud.githubusercontent.com/assets/5520561/12976849/889fe5b0-d0cf-11e5-9c2f-fed16084cab3.png)

The new class will appear in the class combo box.

![](https://cloud.githubusercontent.com/assets/5520561/12977473/84f4b7ca-d0d3-11e5-8fe3-3e081ed0a305.png)

## View Annotation Class

The class of the annotation can be viewed in the tooltip info.

![](https://cloud.githubusercontent.com/assets/5520561/12976847/888f50ce-d0cf-11e5-9534-05172c24127b.png)

## Change Annotation Class

To change annotation class, select the annotations and choose the class from the class combo box.

![](https://cloud.githubusercontent.com/assets/5520561/12976853/88aafaea-d0cf-11e5-9cef-fc39c054397b.png)

![](https://cloud.githubusercontent.com/assets/5520561/12976855/88ba6156-d0cf-11e5-8c31-35dcc77d9f21.png)

![](https://cloud.githubusercontent.com/assets/5520561/12976858/88c00ed0-d0cf-11e5-94ba-dc98ce5b2d8a.png)

## Export Annotations

The annotations can be exports to \*.png files or \*.tiff files. (Currently \*.tiff export does not work – known issue), using Tools-\>Export menu.

The exported frames will be saves in the provided filename with the frame number at the end.

![](https://cloud.githubusercontent.com/assets/5520561/12977311/a8c9e1da-d0d2-11e5-97eb-8d9d0bdf5eea.png)

## Change Frame

Changing frame can be done either by using the frame slider, using the frame text box or using the left\\right keyboard arrows.

![](https://cloud.githubusercontent.com/assets/5520561/12977310/a8c65b64-d0d2-11e5-8e04-b8b2723b644a.png)
