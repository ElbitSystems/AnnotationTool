# imports
import sys
import os
import logging
import pickle

from PyQt5 import QtCore, QtGui, uic, QtWidgets

# project imports
import Annotation
import AnnotationToolGS

# remember last annotation tool was used for
CURRENT_ANNOTATION_FILENAME = '.current.p'

# log _filename
LOG_FILENAME = 'annotation.log'

# annotation tool version
VERSION = 0.2


class ConfigError(Exception):
    """ Exception class for errors in configuration """
    pass


class FrameReadError(Exception):
    """ Exception class for video loading problems """
    pass


class AnnotationTool(QtWidgets.QMainWindow):
    """ Main class for the annotation tool. Handles the 'framework': GUI, etc.  """

    def __init__(self):
        """ initialization  """

        # call parent constructor
        super(AnnotationTool, self).__init__()

        # load ui
        uic.loadUi('AnnotationToolGUI.ui', self)

        # override graphicsView's events
        self.graphicsView.wheelEvent = self.wheelEvent
        self.graphicsView.keyPressEvent = self.keyPressEvent

        # initialize scene
        self.scene = AnnotationToolGS.AnnotationScene(self)

        # connect GUI parts
        self.connect_actions()

        # gray-out GUI elements
        self.enable_gui(False)

        # no annotation yet
        self._annotation = None

        # set slider minimum
        self.frameSlider.setMinimum(1)

        # check if there is a previous annotation
        try:
            # attempt to read annotation currently in progress
            current_filename = pickle.load(open(CURRENT_ANNOTATION_FILENAME, "rb"))

            logging.info('Attempt to read annotation currently in progress.')

            # open annotation
            self.open_file('annotation', current_filename)

        # if no previous annotation loaded
        except (ValueError, Annotation.AnnotationFileError, FileNotFoundError):
            logging.info('No annotation currently in progress.')
            # do nothing
            pass

        # update
        self.update()

    def enable_gui(self, value):
        """ gray out GUI elements if no video loaded """
        self.classSelectionComboBox.setEnabled(value)
        self.graphicsView.setEnabled(value)
        self.frameSlider.setEnabled(value)
        self.frameEdit.setEnabled(value)
        self.actionExport.setEnabled(value)
        self.actionCombine_Objects.setEnabled(value)
        self.actionUndo.setEnabled(value)
        self.actionRedo.setEnabled(value)
        self.actionSaveAs.setEnabled(value)

    def populate_class_combobox(self, classes_list):
        """ populate comboBox with config.classes """

        # block signal to avoid recursive calls
        self.classSelectionComboBox.blockSignals(True)

        # clear combobox to delete previous contents
        self.classSelectionComboBox.clear()

        # add option to add a new class
        self.classSelectionComboBox.addItem('(New)')

        # classes from configuration
        for c in classes_list:
            self.classSelectionComboBox.addItem(str(c))

        # unblock signals
        self.classSelectionComboBox.blockSignals(False)

    def connect_actions(self):
        # 'Quit' action
        self.actionQuit.triggered.connect(self.closeEvent)

        # open video
        self.actionNew.triggered.connect(lambda x: self.open_file('video'))

        # open annotation
        self.actionOpen.triggered.connect(lambda x: self.open_file('annotation'))

        # save as
        self.actionSaveAs.triggered.connect(self.save_annotation)

        # export
        self.actionExport.triggered.connect(self.export)

        # combine objects
        self.actionCombine_Objects.triggered.connect(self.combine_objects)

        # disable slider tracking so as not to continuously read frames
        self.frameSlider.setTracking(False)

        # slider moved
        self.frameSlider.valueChanged.connect(self.frame_slider_update)

        # 'User Guide' menu action
        self.actionAbout.triggered.connect(self.user_guide_event)

        # 'About' menu action
        self.actionAbout.triggered.connect(self.about_event)

        # edit box
        self.frameEdit.returnPressed.connect(self.frame_edit_update)

        # class selection comboBox
        self.classSelectionComboBox.activated.connect(self.class_selection_changed)

        # undo
        self.actionUndo.triggered.connect(self.scene.command_stack.undo)

        # redo
        self.actionRedo.triggered.connect(self.scene.command_stack.redo)

    def class_selection_changed(self, event):
        """ slot for class selection combobox """

        # get text from ui
        selected_text = str(self.classSelectionComboBox.currentText())

        # check for new class add
        if '(New)' == selected_text:
            # open window for new class name input ('str' to avoid QStrings)
            name, ok = QtWidgets.QInputDialog.getText(QtWidgets.QInputDialog(), 'New Class', 'Enter class name:')

            if ok:
                # convert QString to string
                name = str(name)

            # if such a class already exists do nothing
            if name not in self._annotation.classes():
                # add to configuration
                self._annotation.add_class(name)

                # re-populate combo
                self.populate_class_combobox(self._annotation.classes())

                # return value of combo to previous selection
                self.classSelectionComboBox.setCurrentIndex(self.classSelectionComboBox.count() - 1)

        else:

            # inform scene TODO delete.
            self.scene.class_name = selected_text

            # see if object classifications have to change
            self.scene.change_class(selected_text)

    def open_file(self, file_type, filename=None):

        title = 'Open Video' if file_type == 'video' else 'Open Annotation'
        file_types = "Video Files (*.avi *.wmv *.mp4 *.mov)" if file_type == 'video' else 'Annotation File (*.atc)'

        # if working on unsaved annotation
        if self._annotation and not self._annotation.is_file_saved():
            message_box = QtWidgets.QMessageBox()
            message_box.setText("Annotation has not been saved")
            message_box.setInformativeText("Create new anyway?")
            message_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            message_box.setDefaultButton(QtWidgets.QMessageBox.No)
            ret = message_box.exec_()

            # user wants not to create new one - do nothing
            if ret != QtWidgets.QMessageBox.Yes:
                return

            # user wants to discard his unsaved temp annotation
            self._annotation.close()

        # ask user if no filename given
        if not filename:
            # open file (the 'str' - some versions of pyqt return a QString instead of a normal string)
            filename = str(QtWidgets.QFileDialog.getOpenFileName(QtWidgets.QFileDialog(),
                                                                 title, QtCore.QDir.currentPath(), file_types)[0])

            # if user presses 'cancel' in dialog, null string is returned
            if not filename:
                return
        try:
            # open annotation
            self._annotation = Annotation.Annotation(filename)

            # Connect scene to annotation
            self.scene.set_annotation(self._annotation)

            # update slider maximum
            self.frameSlider.setMaximum(self._annotation.num_frames() - 1)

            # enable GUI
            self.enable_gui(True)

            # load classes to GUI comboBox
            self.populate_class_combobox(self._annotation.classes())

            # save filename to last video used file (check first that it is not the temporary workspace)
            if self._annotation.is_file_saved():
                pickle.dump(self._annotation.filename(), open(CURRENT_ANNOTATION_FILENAME, "wb"))

            # set window title
            self.setWindowTitle('Video Annotation Tool' +
                                ('*' if file_type == 'video' else self._annotation.filename()))

            # update
            self.update()

        # file reading failed
        except (Annotation.AnnotationFileError, Annotation.VideoLoadError) as e:
            message_box = QtWidgets.QMessageBox()
            message_box.setText(str(e))
            message_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
            message_box.setDefaultButton(QtWidgets.QMessageBox.Ok)
            ret = message_box.exec_()

    def save_annotation(self):
        """ Save current annotation """

        # open file (the 'str' - some versions of pyqt return a QString instead of a normal string)
        filename = str(QtWidgets.QFileDialog.getSaveFileName(QtWidgets.QFileDialog(),
                                                             'Save Annotation', QtCore.QDir.currentPath(),
                                                             'Annotation File (*.atc)')[0])
        try:
            # check suffix exists
            basename, extension = os.path.splitext(filename)

            if extension != Annotation.Annotation.SUFFIX:
                filename += Annotation.Annotation.SUFFIX

            # save annotation
            self._annotation.save(filename)

            # update window title
            self.setWindowTitle('Video Annotation Tool - ' + self._annotation.filename())

            # save filename as last video used
            if self._annotation.is_file_saved():
                pickle.dump(self._annotation.filename(), open(CURRENT_ANNOTATION_FILENAME, "wb"))

        except ValueError:
            pass

    def frame_slider_update(self):
        """ update after slider release """
        self._annotation.set_frame(self.frameSlider.value())

        # update
        self.update()

    def frame_edit_update(self):
        """ update based on frame edit-box change """

        try:
            # try converting to string; will raise exception for illegals
            frame_number = int(self.frameEdit.text())

            # actively raise exception if out of range
            if frame_number < 1 or frame_number > self.frameSlider.maximum():
                raise ValueError

            # set
            self._annotation.set_frame(frame_number)

            # update
            self.update()

        except ValueError:
            self.frameEdit.setText(str(self.frameSlider.value()))

    def wheelEvent(self, event):

        # zoom at current mouse position
        self.graphicsView.setTransformationAnchor(self.graphicsView.AnchorUnderMouse)

        # make sure scene is not in drawing mode
        self.scene.draw = False

        #   zoom factor
        factor = 1.1

        if event.angleDelta().y() < 0:  # zooming out
            factor = 1.0 / factor

        # change zoom
        self.graphicsView.scale(factor, factor)

    def keyPressEvent(self, event):

        # do nothing if not active yet
        if not self._annotation:
            return

        # move back one frame
        if event.key() == QtCore.Qt.Key_Left and self._annotation.current_frame() > 1:
            self._annotation.set_frame(self._annotation.current_frame() - 1)
            self.update()

        # move forward one frame
        elif event.key() == QtCore.Qt.Key_Right and self._annotation.current_frame() < self._annotation.num_frames():
            self._annotation.set_frame(self._annotation.current_frame() + 1)
            self.update()

        # delete object from scene
        elif event.key() == QtCore.Qt.Key_Delete or event.key() == QtCore.Qt.Key_Backspace:
            self.scene.delete()

        # ctrl-z = undo
        elif event.key() == (QtCore.Qt.Key_Control and QtCore.Qt.Key_Z):
            self.actionUndo.trigger()

        # ctrl-y = redo
        elif event.key() == (QtCore.Qt.Key_Control and QtCore.Qt.Key_Y):
            self.actionRedo.trigger()

    def update(self):
        """ main GUI function - update after change """

        # do nothing if there is no annotation
        if self._annotation is None: return

        # block signals to avoid recursive calls
        self.frameSlider.blockSignals(True)
        self.frameEdit.blockSignals(True)

        # set current frame number in slider
        self.frameSlider.setValue(self._annotation.current_frame())

        # set text in edit box according to slider
        self.frameEdit.setText(str(self._annotation.current_frame()))

        # release signals
        self.frameSlider.blockSignals(False)
        self.frameEdit.blockSignals(False)

        frame = self._annotation.get_frame_image()

        # track objects if moving one frame ahead
        # if self.draw['previous_frame'] is not None
        # and self.draw['current_frame'] == self.draw['previous_frame'] + 1:
        #     self.scene.track()

        # deal with opencv's BGR abomination; create Qt image (width, height)
        image = QtGui.QImage(frame.tostring(), frame.shape[1], frame.shape[0],
                             QtGui.QImage.Format_RGB888).rgbSwapped()

        # clear scene from previous drawn elements
        self.scene.clear()

        # load image to scene (set as background)
        self.scene.set_background(image)

        # load objects for current frame
        self.scene.load(self._annotation.current_frame(), self._annotation.get(self._annotation.current_frame()))

        #   display image on graphicsView (canvas)
        self.graphicsView.setScene(self.scene)

        #   set graphics view to scene
        self.graphicsView.show()

    def closeEvent(self, event=None):
        """ overloaded closeEvent to allow quitting by closing window.
            save current draw and quit """

        if self._annotation and not self._annotation.is_file_saved():
            message_box = QtWidgets.QMessageBox()
            message_box.setText("Annotation has not been saved")
            message_box.setInformativeText("Exit anyway?")
            message_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            message_box.setDefaultButton(QtWidgets.QMessageBox.No)
            ret = message_box.exec_()

            if ret != QtWidgets.QMessageBox.Yes:
                event.ignore()
                return

            # save session details
            self._annotation.exit()

        # Qt quit
        QtWidgets.qApp.quit()

    def user_guide_event(self):
        pass

    @staticmethod
    def about_event():
        pass

    def export(self):
        # TODO: frames selection...
        frames = list(range(1, self._annotation.num_frames()))

        filename = str(QtWidgets.QFileDialog.getSaveFileName(QtWidgets.QFileDialog(), "Save as...",
                                                             QtCore.QDir.currentPath(),
                                                             "color png (*.png);;16-bit ID image(*.tiff)")[0])
        if not filename:
            return

        self._annotation.export((self.scene.width(), self.scene.height()), os.path.dirname(filename),
                                os.path.splitext(os.path.basename(str(filename)))[0], frames,
                                self.scene.colormap, self.scene.inverse_colormap,
                                os.path.splitext(os.path.basename(str(filename)))[1])

    def combine_objects(self):

        # generate dialog that gets the objects ID's to combine
        dialogTextBrowser = CombineObjectsDialog(self)
        dialogTextBrowser.exec_()

        if dialogTextBrowser.yes:
            # check if 'from_id' exists in current frame
            record = self._annotation.get(self.scene.frame_number, dialogTextBrowser.from_id)

            try:
                # combine objects in DB file
                self._annotation.combine_objects(dialogTextBrowser.from_id, dialogTextBrowser.target_id)
            except ValueError as e:
                QtWidgets.QMessageBox.information(QtWidgets.QMessageBox(), 'Error Message',
                                                  str(e), QtWidgets.QMessageBox.Ok)
            # If combining action succeeded
            else:

                # update 'From ID' object in current frame (color..)
                if record:
                    # 1-size tuple
                    record = record[0]

                    # the 'To ID' color in scene
                    color = self.scene.get_color(self.scene.colormap[:, dialogTextBrowser.target_id])

                    # remove old contour
                    self.scene.remove_contour(record[1])

                    # add new contour
                    self.scene.add_contour([int(s) for s in record[3].split()], record[1], record[2], record[4], color)


class CombineObjectsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(CombineObjectsDialog, self).__init__(parent)

        # initialize 'from' and 'to' object ID's to combine
        self.from_id, self.target_id = None, None

        # initialize 'yes' to no
        self.yes = False

        # add labels and the edit boxes for ID's
        self.labelFrom = QtWidgets.QLabel('\'From\' ID')
        self.from_edit = QtWidgets.QLineEdit()
        self.labelFrom.setBuddy(self.from_edit)
        self.labelTo = QtWidgets.QLabel('\'To\' ID')
        self.to_edit = QtWidgets.QLineEdit()
        self.labelTo.setBuddy(self.to_edit)

        # add OK and Cancel buttons to the dialog box
        self.buttonBox = QtWidgets.QDialogButtonBox(self)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok)

        # set labels and edit boxes in the layouts
        self.HLayout0 = QtWidgets.QHBoxLayout()
        self.HLayout0.addStretch(0)
        self.HLayout0.addWidget(self.labelFrom)
        self.HLayout0.addWidget(self.from_edit)
        self.HLayout1 = QtWidgets.QHBoxLayout()
        self.HLayout1.addStretch(0)
        self.HLayout1.addWidget(self.labelTo)
        self.HLayout1.addWidget(self.to_edit)
        self.HLayout2 = QtWidgets.QHBoxLayout()
        self.HLayout2.addStretch(0)
        self.HLayout2.addWidget(self.buttonBox)
        self.VLayout1 = QtWidgets.QVBoxLayout()
        self.VLayout1.addLayout(self.HLayout0)
        self.VLayout1.addLayout(self.HLayout1)
        self.VLayout1.addLayout(self.HLayout2)
        self.setLayout(self.VLayout1)

        self.setGeometry(300, 300, 200, 120)
        self.setWindowTitle('Combine Objects')

        # do nothing if user canceled
        self.buttonBox.rejected.connect(self.close)

        # if user pressed OK
        self.buttonBox.accepted.connect(self.check_input)

    def check_input(self):
        """ check content of edit boxes """
        try:
            from_temp = int(self.from_edit.text())
            target_temp = int(self.to_edit.text())
        # if there was nothing in box or an illegal character
        except ValueError:
            return

        # if we got this far, set values
        self.from_id = from_temp
        self.target_id = target_temp
        self.yes = True

        # now close window
        self.close()


if __name__ == "__main__":
    # initialize logger
    logging.basicConfig(filename=LOG_FILENAME, level=logging.DEBUG, filemode='w')
    logging.info('start application.')

    try:
        app = QtWidgets.QApplication(sys.argv)

        annotation_tool = AnnotationTool()

        annotation_tool.show()
        sys.exit(app.exec_())

    except (ConfigError, Annotation.VideoLoadError, FrameReadError) as err:
        # message box
        msgBox = QtWidgets.QMessageBox()
        msgBox.setText(repr(err))
        msgBox.exec_()
