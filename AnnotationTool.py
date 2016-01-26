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
VERSION = 1.3


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
        self.annotation = None

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
        """ populate comboBox with config.classes
        :param classes_list: list of classes
        """

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

        # load classes
        self.actionLoad_Classes.triggered.connect(self.load_classes)

        # find
        self.actionFind.triggered.connect(self.find_annotations)

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

        find_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence('Ctrl+F'), self)
        find_shortcut.activated.connect(self.find_annotations)

    def class_selection_changed(self):
        """ slot for class selection combobox """

        # get text from ui
        selected_text = str(self.classSelectionComboBox.currentText())

        # check for new class add
        if '(New)' == selected_text:
            # open window for new class name input ('str' to avoid QStrings)
            name, ok = QtWidgets.QInputDialog.getText(QtWidgets.QInputDialog(), 'New Class', 'Enter class name:')

            # if user pressed 'cancel' or gave empty name
            if not ok or not name:
                return

            # convert QString to string
            name = str(name)

            # if such a class already exists do nothing
            if name not in self.annotation.classes():
                # add to configuration
                self.annotation.add_class(name)

                # re-populate combo
                self.populate_class_combobox(self.annotation.classes())

                # return value of combo to previous selection
                self.classSelectionComboBox.setCurrentIndex(self.classSelectionComboBox.count() - 1)

        else:

            # inform scene TODO delete.
            self.scene.class_name = selected_text

            # see if object classifications have to change
            self.scene.change_class(selected_text)

    def open_file(self, file_type, filename=None):

        title = 'Open Video / Images' if file_type == 'video' else 'Open Annotation'
        file_types = "Video Files (*.avi *.wmv *.mp4 *.mov);; Images Files (*.jpg *.bmp *.tif *.tiff *.png)" \
                     if file_type == 'video' else 'Annotation File (*.atc)'

        # if working on unsaved annotation
        if self.annotation and not self.annotation.is_file_saved():
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
            self.annotation.close()

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
            self.annotation = Annotation.Annotation(filename)

            # Connect scene to annotation
            self.scene.set_annotation(self.annotation)

            # update slider maximum
            self.frameSlider.setMaximum(self.annotation.num_frames - 1)

            # enable GUI
            self.enable_gui(True)

            # load classes to GUI comboBox
            self.populate_class_combobox(self.annotation.classes())

            # save filename to last video used file (check first that it is not the temporary workspace)
            if self.annotation.is_file_saved():
                pickle.dump(self.annotation.filename(), open(CURRENT_ANNOTATION_FILENAME, "wb"))

            # set window title
            self.setWindowTitle('Video Annotation Tool' +
                                ('*' if file_type == 'video' else self.annotation.filename()))

            # update
            self.update()

        except Annotation.VideoLoadVideoNotFound as e:
            message_box = QtWidgets.QMessageBox()
            message_box.setText(str(e))
            message_box.setInformativeText("Would you like to navigate to the new location of the video file?")
            message_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            message_box.setDefaultButton(QtWidgets.QMessageBox.Yes)
            ret = message_box.exec_()
            if ret == QtWidgets.QMessageBox.Yes:
                filename = self.provide_video_location()
                annotation_file = Annotation.Annotation.update_video_filename_in_annotation(e.filename, filename)

                if self.annotation:
                    self.annotation.close()
                    del self.annotation
                self.annotation = None

                self.open_file('annotation', annotation_file)
                # self.annotation = Annotation.Annotation(annotation_file)
                # self.update()

        # file reading failed
        except (Annotation.AnnotationFileError, Annotation.VideoLoadError) as e:
            message_box = QtWidgets.QMessageBox()
            message_box.setText(str(e))
            message_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
            message_box.setDefaultButton(QtWidgets.QMessageBox.Ok)
            message_box.exec_()

    def provide_video_location(self):
        title = 'Open Video / Images'
        file_types = "Video Files (*.avi *.wmv *.mp4 *.mov);; Images Files (*.jpg *.bmp *.tif *.tiff *.png)"

        # open file (the 'str' - some versions of pyqt return a QString instead of a normal string)
        filename = str(QtWidgets.QFileDialog.getOpenFileName(QtWidgets.QFileDialog(),
                                                             title, QtCore.QDir.currentPath(), file_types)[0])

        # if user presses 'cancel' in dialog, null string is returned
        return filename

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
            self.annotation.save(filename)

            # update window title
            self.setWindowTitle('Video Annotation Tool - ' + self.annotation.filename())

            # save filename as last video used
            if self.annotation.is_file_saved():
                pickle.dump(self.annotation.filename(), open(CURRENT_ANNOTATION_FILENAME, "wb"))

        except ValueError:
            pass

    def frame_slider_update(self):
        """ update after slider release """
        self.annotation.set_frame(self.frameSlider.value())

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
            self.annotation.set_frame(frame_number)

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
        if not self.annotation:
            return

        # move back one frame
        if event.key() == QtCore.Qt.Key_Left and self.annotation.current_frame > 1:
            self.annotation.set_frame(self.annotation.current_frame - 1)
            self.update()

        # move forward one frame
        elif event.key() == QtCore.Qt.Key_Right and self.annotation.current_frame < self.annotation.num_frames:
            self.annotation.set_frame(self.annotation.current_frame + 1)
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
        if self.annotation is None:
            return

        # block signals to avoid recursive calls
        self.frameSlider.blockSignals(True)
        self.frameEdit.blockSignals(True)

        # set current frame number in slider
        self.frameSlider.setValue(self.annotation.current_frame)

        # set text in edit box according to slider
        self.frameEdit.setText(str(self.annotation.current_frame))

        # release signals
        self.frameSlider.blockSignals(False)
        self.frameEdit.blockSignals(False)

        frame = self.annotation.get_frame_image()

        # deal with opencv's BGR abomination; create Qt image (width, height)
        image = QtGui.QImage(frame.tostring(), frame.shape[1], frame.shape[0],
                             QtGui.QImage.Format_RGB888).rgbSwapped()

        # clear scene from previous drawn elements
        self.scene.clear()

        # load image to scene (set as background)
        self.scene.set_background(image)

        # load objects for current frame
        self.scene.load(self.annotation.current_frame, self.annotation.get(self.annotation.current_frame))

        #   display image on graphicsView (canvas)
        self.graphicsView.setScene(self.scene)

        #   set graphics view to scene
        self.graphicsView.show()

    def closeEvent(self, event=None):
        """ overloaded closeEvent to allow quitting by closing window.
            save current draw and quit """

        if self.annotation and not self.annotation.is_file_saved():
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
            self.annotation.exit()

        # Qt quit
        QtWidgets.qApp.quit()

    def user_guide_event(self):
        pass

    @staticmethod
    def about_event():
        msg_box = QtWidgets.QMessageBox()
        msg_box.setWindowTitle('About Annotation Tool')
        msg_box.setText('Video ground truth annotation tool for manual object marking.\nVersion ' + str(VERSION))
        msg_box.exec_()

    def export(self):
        # TODO: frames selection...
        frames = list(range(1, self.annotation.num_frames))

        filename = str(QtWidgets.QFileDialog.getSaveFileName(QtWidgets.QFileDialog(), "Save as...",
                                                             QtCore.QDir.currentPath(),
                                                             "color png (*.png);;16-bit ID image(*.tiff)")[0])
        if not filename:
            return

        self.annotation.export((self.scene.width(), self.scene.height()), os.path.dirname(filename),
                               os.path.splitext(os.path.basename(str(filename)))[0], frames,
                               self.scene.colormap, self.scene.inverse_colormap,
                               os.path.splitext(os.path.basename(str(filename)))[1])

    def combine_objects(self):

        # generate dialog that gets the objects ID's to combine
        dialog_text_browser = CombineObjectsDialog(self)
        dialog_text_browser.exec_()

        if dialog_text_browser.yes:
            # check if 'from_id' exists in current frame
            record = self.annotation.get(self.scene.frame_number, dialog_text_browser.from_id)

            try:
                # combine objects in DB file
                self.annotation.combine_objects(dialog_text_browser.from_id, dialog_text_browser.target_id)
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
                    color = self.scene.get_color(self.scene.colormap[:, dialog_text_browser.target_id])

                    # remove old contour
                    self.scene.remove_contour(record[1])

                    # add new contour
                    self.scene.add_contour([int(s) for s in record[3].split()], record[1], record[2], record[4], color)

    def load_classes(self):
        """
        Read whitespace separated list of classes from text file
        A class name can not contain whitespaces.
        :return:
        """
        # open file (the 'str' - some versions of pyqt return a QString instead of a normal string)
        filename = str(QtWidgets.QFileDialog.getOpenFileName(QtWidgets.QFileDialog(),
                                                             'Please select valid text file', QtCore.QDir.currentPath(),
                                                             'Text Files *.txt')[0])

        # if user presses 'cancel' in dialog, null string is returned
        if not filename:
            return

        # try parsing the file:
        try:
            # read file
            with open(filename) as f:
                class_list = f.read().split()

            # add classes
            for class_name in class_list:
                self.annotation.add_class(str(class_name).strip())

            # re populate class combo box
            self.populate_class_combobox(self.annotation.classes())
        except RuntimeError:
            msg_box = QtWidgets.QMessageBox()
            msg_box.setText('Failed to load class.')
            msg_box.exec_()

    def zoom_on(self, obj, frame=None):
        # move to frame if needed
        if frame:
            self.annotation.set_frame(frame)

            # update
            self.update()

        # get the annotation item of the object
        annotation_item = self.scene.obj2contour[obj]

        # fit him to view
        self.graphicsView.fitInView(annotation_item.boundingRect(), QtCore.Qt.KeepAspectRatio)

        # zoom out very little
        self.graphicsView.scale(0.5, 0.5)

    def find_annotations(self):

        #   create Find window
        find = FindDialog(self)
        find.show()


class FindDialog(QtWidgets.QDialog):

    FIND_ALL = 'Find All in Frame'

    def __init__(self, parent=None):
        super(FindDialog, self).__init__(parent)
        self.parent = parent

        # iterator placeholder
        self.annotation_iter = None

        # init UI
        # Search mode - radio button - By Class / By ID
        self.search_mode_radio_class = QtWidgets.QRadioButton("By Class", self)
        self.search_mode_radio_id = QtWidgets.QRadioButton("By ID", self)

        # Button to search the document for something
        self.search_name = QtWidgets.QComboBox()
        self.search_name.focusInEvent = lambda e: self.search_mode_radio_class.setChecked(True)

        self.search_id = QtWidgets.QLineEdit()
        self.search_id.focusInEvent = lambda e: self.search_mode_radio_id.setChecked(True)

        # Add existing class names to search options.
        class_names = self.parent.annotation.classes()
        self.search_name.addItems([FindDialog.FIND_ALL] + class_names)

        self.find_button = QtWidgets.QPushButton("Find", self)
        self.find_button.clicked.connect(self.find_stuff)

        self.next_button = QtWidgets.QPushButton("Next", self)
        self.next_button.setEnabled(False)
        self.next_button.clicked.connect(self.next_annotation)

        self.back_button = QtWidgets.QPushButton('Back', self)
        self.back_button.setEnabled(False)
        self.back_button.clicked.connect(self.prev_annotation)

        self.status = QtWidgets.QStatusBar()
        self.status.showMessage('Press Find to find annotations.')

        layout = QtWidgets.QGridLayout()
        layout.addWidget(self.search_mode_radio_class, 0, 0)
        layout.addWidget(self.search_mode_radio_id, 1, 0)
        layout.addWidget(self.search_name, 0, 1, 1, 2)
        layout.addWidget(self.search_id, 1, 1, 1, 2)
        layout.addWidget(self.find_button, 2, 0)
        layout.addWidget(self.back_button, 2, 1)
        layout.addWidget(self.next_button, 2, 2)
        layout.addWidget(self.status, 3, 0, 1, 3)

        self.setGeometry(450, 450, 150, 150)
        self.setWindowTitle('Find annotation')
        self.setLayout(layout)

        # By default the class mode is activated
        self.search_mode_radio_class.setChecked(True)
        # Done init ui

    def next_annotation(self):
        try:
            next_item, index = self.annotation_iter.next()
            item_class = next_item[2]
            item_id = next_item[1]
            frame = next_item[0]
            self.parent.zoom_on(item_id, frame)
        except StopIteration:
            # display message to user
            msg_box = QtWidgets.QMessageBox()
            msg_box.setText('No annotation found.')
            msg_box.exec_()

            # disable the 'Next' button
            self.next_button.setEnabled(False)
            self.back_button.setEnabled(False)
        else:
            self.update_status_bar(index, item_id, item_class)

    def update_status_bar(self, index, s_id, s_class):
        self.status.showMessage(
            'Search result {current} out of {total}.\n {a_id} - {a_class}'.format(
                    current=index,
                    total=self.annotation_iter.len(),
                    a_class=str(s_class),
                    a_id=str(s_id)))
        self.next_button.setEnabled(False if index == self.annotation_iter.len() else True)
        self.back_button.setEnabled(False if index == 1 else True)

    def prev_annotation(self):
        try:
            prev_item, index = self.annotation_iter.prev()
            item_class = prev_item[2]
            item_id = prev_item[1]
            frame = prev_item[0]
            self.parent.zoom_on(item_id, frame)
        except StopIteration:
            # display message to user
            msg_box = QtWidgets.QMessageBox()
            msg_box.setText('No annotation found.')
            msg_box.exec_()

            # disable the 'Back' button
            self.back_button.setEnabled(False)
        else:
            self.update_status_bar(index, item_id, item_class)

    def find_stuff(self):
        # work mode is by Class
        annotations = []
        if self.search_mode_radio_class.isChecked():
            # get text
            selected = self.search_name.currentText()

            # if user wants to search all annotation in frame - do not provide specific class to 'get' function
            selected = None if selected == FindDialog.FIND_ALL else selected

            # relevant annotations
            annotations = self.parent.annotation.get(self.parent.annotation.current_frame, class_name=selected)
        elif self.search_mode_radio_id.isChecked():
            # Get input text
            search_id = self.search_id.text()

            # Error handling
            try:
                number = int(search_id)
            except ValueError:
                msg_box = QtWidgets.QMessageBox()
                msg_box.setWindowTitle('Error')
                msg_box.setText('ID can only be a number')
                msg_box.exec_()
                return

            # get relevant annotations
            annotations = self.parent.annotation.get_annotations_of_id(number)

        # create iterator for annotations in search result
        self.annotation_iter = TwoWayIterator(annotations)

        # enable the 'Next' button
        self.next_button.setEnabled(True)
        self.back_button.setEnabled(True)

        # find the first annotation
        self.next_annotation()


class TwoWayIterator(object):

    def __init__(self, data):
        self.data = data
        self.index = 0

    def next(self):
        try:
            next = self.data[self.index]
            self.index += 1
        except IndexError:
            raise StopIteration
        else:
            return next, self.index

    def prev(self):
        if self.index == 0 or self.index == 1:
            raise StopIteration
        self.index -= 1
        prev = self.data[self.index - 1]
        return prev, self.index

    def len(self):
        return len(self.data)


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
    logging.basicConfig(filename=LOG_FILENAME, level=logging.INFO, filemode='w')
    logging.info('start application.')

    try:
        app = QtWidgets.QApplication(sys.argv)

        annotation_tool = AnnotationTool()

        annotation_tool.show()
        sys.exit(app.exec_())

    except (Annotation.VideoLoadError, FrameReadError) as err:
        # message box
        msgBox = QtWidgets.QMessageBox()
        msgBox.setText(repr(err))
        msgBox.exec_()
