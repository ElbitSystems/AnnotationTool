import Tracker
import numpy as np
import weakref

from itertools import chain
from PyQt5 import QtCore, QtGui, QtWidgets

# constants
TRANSPARENCY = 150
MODIFY_TRANSPARENCY = 0.3  # visual cure for modification
UNDO_LIMIT = 20


class AddCommand(QtWidgets.QUndoCommand):
    """ add new object to scene and DB """

    def __init__(self, annotation_scene, frame_number, obj_id, class_name, points):
        # call parent
        super(AddCommand, self).__init__()

        self.annotation_scene = annotation_scene
        self.annotation = annotation_scene.annotation()
        self.frame_number = frame_number
        self.obj_id = obj_id
        self.class_name = class_name
        self.points = points
        # hold contour item
        self.contour = None

    def redo(self):
        # add to database
        self.annotation.add(self.frame_number, self.obj_id, self.class_name, self.points, True)

        # prediction for next frame will be identical since this is first frame for object
        self.annotation.add(self.frame_number + 1, self.obj_id, self.class_name,
                            self.annotation_scene.tracker.track(self.points, self.frame_number, self.obj_id),
                            False)

        # draw contour
        self.contour = self.annotation_scene.add_contour(self.points, self.obj_id, self.class_name, True)

    def undo(self):
        # remove graphics item (notice this is not necessarily the same 'physical'
        # graphics item as the 'redo' one since MoveCommands might have been made)
        self.annotation_scene.removeItem(self.annotation_scene.obj2contour[self.obj_id])

        # remove from DB
        self.annotation.remove(self.obj_id, self.frame_number)

        # remove prediction from DB
        self.annotation.remove(self.obj_id, self.frame_number + 1)


class DeleteCommand(QtWidgets.QUndoCommand):
    def __init__(self, annotation_scene, frame_number, obj_id, class_name):
        # call parent
        super(DeleteCommand, self).__init__()

        self.annotation_scene = annotation_scene
        self.annotation = annotation_scene.annotation()
        self.frame_number = frame_number
        self.obj_id = obj_id
        self.class_name = class_name

        # save position for undo
        record = self.annotation.get(self.frame_number, self.obj_id)
        self.points = [int(s) for s in record[0][3].split()]

        # save old prediction for undo
        old_pred = self.annotation.get(self.frame_number + 1, self.obj_id)
        if old_pred:
            self.old_pred_points = [int(s) for s in old_pred[0][3].split()]

            # has the user actively confirmed the object in next frame
            self.final_in_next_frame = old_pred[0][4]
        else:
            self.old_pred_points = None
            self.final_in_next_frame = None

    def redo(self):
        # remove contour
        self.annotation_scene.remove_contour(self.obj_id)

        # remove from DB
        self.annotation.remove(self.obj_id, self.frame_number)

        # remove prediction from DB if not finalized by user
        if not self.final_in_next_frame:
            self.annotation.remove(self.obj_id, self.frame_number + 1)

    def undo(self):
        # redraw contour
        self.annotation_scene.add_contour(self.points, self.obj_id, self.class_name, True)

        # restore data
        self.annotation.add(self.frame_number, self.obj_id, self.class_name, self.points, True)

        # if the object that was deleted and then returned doesn't exist in other frame, need to allocate ID
        id_frames = self.annotation.get_frames_indexes_of_id(self.obj_id)
        id_frames.remove(self.frame_number)

        # attempt to track object in next frame
        next_frame_record = self.annotation.get(self.frame_number + 1, self.obj_id)
        if len(next_frame_record) > 0:
            #   check if what we have in _annotation is a prediction or already a user-finalized object
            finalized = next_frame_record[0][4]
        else:
            # if no prediction exists, object is trivially not finalized
            finalized = False

        if not finalized:
            #   remove prediction (to be replaced with new moved object prediction)
            self.annotation.remove(self.obj_id, self.frame_number + 1)

            # add prediction in next frame at tracker generated location (non-final)
            self.annotation.add(self.frame_number + 1, self.obj_id, self.class_name,
                                self.annotation_scene.tracker.track(self.points, self.frame_number, self.obj_id), False)


class ModifyCommand(QtWidgets.QUndoCommand):
    """ modify existing object """

    def __init__(self, annotation_scene, frame_number, obj_id, class_name, points):
        # call parent
        super(ModifyCommand, self).__init__()

        self.annotation_scene = annotation_scene
        self.annotation = annotation_scene.annotation()
        self.frame_number = frame_number
        self.obj_id = obj_id
        self.class_name = class_name
        self.points = points

        # save old position for undo
        old = self.annotation.get(self.frame_number, self.obj_id)
        self.old_points = [int(s) for s in old[0][3].split()]

        # save old prediction for undo
        old_pred = self.annotation.get(self.frame_number + 1, self.obj_id)
        if old_pred:
            self.old_pred_points = [int(s) for s in old_pred[0][3].split()]

            # has the user actively confirmed the object in next frame
            self.final_in_next_frame = old_pred[0][4]
        else:
            self.old_pred_points = None
            self.final_in_next_frame = None

    def redo(self):
        # remove contour
        self.annotation_scene.removeItem(self.annotation_scene.obj2contour[self.obj_id])

        # remove from DB
        self.annotation.remove(self.obj_id, self.frame_number)

        # add new contour
        self.annotation_scene.add_contour(self.points, self.obj_id, self.class_name, True)

        # add new data
        self.annotation.add(self.frame_number, self.obj_id, self.class_name, self.points, True)

        # attempt to track object in next frame
        next_frame_record = self.annotation.get(self.frame_number + 1, self.obj_id)
        if len(next_frame_record) > 0:
            #   check if what we have in _annotation is a prediction or already a user-finalized object
            finalized = next_frame_record[0][4]
        else:
            # if no prediction exists, object is trivially not finalized
            finalized = False

        if not finalized:
            #   remove prediction (to be replaced with new moved object prediction)
            self.annotation.remove(self.obj_id, self.frame_number + 1)

            # add prediction in next frame at tracker generated location (non-final)
            self.annotation.add(self.frame_number + 1, self.obj_id, self.class_name,
                                self.annotation_scene.tracker.track(self.points, self.frame_number, self.obj_id), False)

    def undo(self):
        # remove from DB
        self.annotation.remove(self.obj_id, self.frame_number)

        # remove contour
        self.annotation_scene.removeItem(self.annotation_scene.obj2contour[self.obj_id])

        # move contour to old
        self.annotation_scene.add_contour(self.old_points, self.obj_id, self.class_name, True)

        # restore data
        self.annotation.add(self.frame_number, self.obj_id, self.class_name, self.old_points, True)

        # undo prediction if user hasn't finalized object in next frame
        if not self.final_in_next_frame:
            # remove existing prediction if exists
            self.annotation.remove(self.obj_id, self.frame_number + 1)

            # if there is an "old" prediction, restore it
            if self.old_pred_points:
                self.annotation.add(self.frame_number + 1, self.obj_id, self.class_name,
                                    self.old_pred_points, False)


class MoveCommand(QtWidgets.QUndoCommand):
    """ add new object to scene and DB """

    def __init__(self, annotation_scene, frame_number, obj_id, class_name, contour):
        """
        :param annotation_scene: scene to perform actions on
        :param frame_number: current frame
        :param obj_id: object moved
        :param class_name: class of object
        :param contour: new contour (graphicsItem) to move to
        :return:
        """
        # call parent
        super(MoveCommand, self).__init__()

        self.annotation_scene = annotation_scene
        self.annotation = annotation_scene.annotation()
        self.frame_number = frame_number
        self.obj_id = obj_id
        self.class_name = class_name
        self.contour = contour

        # save old position for undo
        old = self.annotation.get(self.frame_number, self.obj_id)
        self.old_points = [int(s) for s in old[0][3].split()]

        # save old prediction for undo. check if object is "final" in next frame
        old_pred = self.annotation.get(self.frame_number + 1, self.obj_id)
        if old_pred:
            self.old_pred_points = [int(s) for s in old_pred[0][3].split()]

            # has the user actively confirmed the object in next frame
            self.final_in_next_frame = old_pred[0][4]
        else:
            self.old_pred_points = None
            self.final_in_next_frame = None

    def redo(self):
        # remove old object from DB
        self.annotation.remove(self.obj_id, self.frame_number)

        # move contour from old to new
        points = self.annotation_scene.move_contour(self.contour, self.obj_id, self.class_name)

        # add new data
        self.annotation.add(self.frame_number, self.obj_id, self.class_name, points, True)

        # attempt to track object in next frame
        next_frame_record = self.annotation.get(self.frame_number + 1, self.obj_id)
        if len(next_frame_record) > 0:
            # check if what we have in _annotation is a prediction or already a user-finalized object
            finalized = next_frame_record[0][4]
        else:
            # if no prediction exists, object is trivially not finalized
            finalized = False

        if not finalized:
            # remove prediction (to be replaced with new moved object prediction)
            self.annotation.remove(self.obj_id, self.frame_number + 1)

            # add prediction in next frame at tracker generated location (non-final)
            self.annotation.add(self.frame_number + 1, self.obj_id, self.class_name,
                                self.annotation_scene.tracker.track(points, self.frame_number, self.obj_id), False)

    def undo(self):
        # remove from DB
        self.annotation.remove(self.obj_id, self.frame_number)

        # remove contour
        self.annotation_scene.removeItem(self.annotation_scene.obj2contour[self.obj_id])

        # move contour to old
        self.annotation_scene.add_contour(self.old_points, self.obj_id, self.class_name, True)

        # restore data
        self.annotation.add(self.frame_number, self.obj_id, self.class_name, self.old_points, True)

        # undo move prediction if user hasn't finalized object in next frame
        if not self.final_in_next_frame:
            # remove old prediction
            self.annotation.remove(self.obj_id, self.frame_number + 1)

            # if there is an "old" prediction, restore it
            if self.old_pred_points:
                self.annotation.add(self.frame_number + 1, self.obj_id, self.class_name, self.old_pred_points, False)


class AnnotationObject(QtWidgets.QGraphicsPolygonItem):
    def __init__(self, qpolygonf, pen, color, final, parent=None):
        # call parent ctor
        super(AnnotationObject, self).__init__(qpolygonf, parent)

        # set pen
        self.setPen(pen)

        # save color and final
        self.color = color
        self.final = final

        # set different brush behaviour for final/predicted object
        if not self.final:
            brush = QtGui.QBrush(self.color, QtCore.Qt.Dense5Pattern)
        else:
            brush = QtGui.QBrush(self.color)
        self.setBrush(brush)

        # make movable and selectable
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, True)

        # draw
        self.state = None
        self.modified_points = []

        self.original_pos = None

        self.lines = []

    def finalize(self):
        #   change final draw to True
        self.final = True

        #   update brush
        brush = QtGui.QBrush(self.color)
        self.setBrush(brush)

    def mousePressEvent(self, event):

        # disable middle-mouse button press
        if event.button() == QtCore.Qt.MiddleButton:
            self.state = None
            return

        # Call parent's event handler
        super(AnnotationObject, self).mousePressEvent(event)

        # where the mouse press is
        p = event.scenePos().toPoint()

        # right click is for modifying the contour
        if event.button() == QtCore.Qt.RightButton:

            # set draw
            self.state = 'modify'

            # keep the new contour points
            self.modified_points = [p.x(), p.y()]

            #   visual cue
            self.setBrush(QtGui.QBrush(QtCore.Qt.cyan, QtCore.Qt.CrossPattern))
            self.setOpacity(MODIFY_TRANSPARENCY)

        # Left Button Click is for dragging the contour
        elif event.button() == QtCore.Qt.LeftButton:
            self.state = 'drag'
            self.original_pos = event.scenePos()

    def mouseMoveEvent(self, event):
        # disable middle-mouse button press
        if event.button() == QtCore.Qt.MiddleButton:
            self.state = None
            return

        # Call parent's event handler
        super(AnnotationObject, self).mouseMoveEvent(event)
        # self.setSelected(True)

        if self.state == 'modify':
            # Modifying the contour -> collecting points
            p = event.scenePos().toPoint()
            self.modified_points += [p.x(), p.y()]

            # current line
            l = QtWidgets.QGraphicsLineItem(QtCore.QLineF(self.modified_points[-4], self.modified_points[-3],
                                                          self.modified_points[-2], self.modified_points[-1]))
            l.setPen(self.pen())
            self.lines.append(l)

            #   draw current line
            self.scene().addItem(self.lines[-1])

    def mouseReleaseEvent(self, event):

        # disable middle-mouse button press
        if event.button() == QtCore.Qt.MiddleButton:
            self.state = None
            return

        # Call parent's event handler
        super(AnnotationObject, self).mouseReleaseEvent(event)

        # pointer to scene object
        s = self.scene()

        # if finished modifying an object
        if self.state == 'modify':

            # check if we've moved since right-mouse click; if not abort modify
            if len(self.modified_points) < 4:
                self.state = None
            #   otherwise - perform modification
            else:

                for line in self.lines:
                    self.scene().removeItem(line)

                s.command_stack.push(
                    ModifyCommand(s,                                    # scene
                                  s.frame_number,                       # frame number
                                  self.scene().contour2obj[self][0],    # object id
                                  self.scene().contour2obj[self][1],    # object class
                                  self.modified_points))                # new contour

        # if finished dragging an object
        elif self.state == 'drag':

            # modify the contour based on the difference from original .pos()
            pos = event.scenePos()

            # how much was dragged
            diff = pos - self.original_pos

            # if we move less then 1 it is as if we didn't move
            if (diff.x() ** 2 + diff.y() ** 2) ** 0.5 < 1:
                return

            # the new place that should be
            new_contour = [p + diff for p in self.polygon()]

            # get id
            (obj_id, class_name) = s.contour2obj[self]

            # push command on stack
            s.command_stack.push(
                MoveCommand(s, s.frame_number, obj_id, class_name,
                            AnnotationObject(QtGui.QPolygonF(new_contour), self.pen(), self.color, self.final)))

            # mark as a changed item (avoid tracking it again on frame change)
            s.changed_items.append(obj_id)

            # abort for click and drag
            self.state = None
            return


class AnnotationScene(QtWidgets.QGraphicsScene):
    """ graphics scene for marking and associated database """

    def __init__(self, parent=None):
        """ class holding all information pertaining to the scene: a database
        of past objects, graphics items and markers for current object
        :param parent:
        :return:
        """

        # call parent
        super(AnnotationScene, self).__init__(parent)
        self.parent = parent

        # start with empty list of points in current marker
        self.points = []

        # initialize colormap (calm PEP first by initializing in constructor)
        self.colormap = self.inverse_colormap = None
        self.set_colormap()

        # pen and color
        self.pen = []
        self.color = []

        # default class to none
        self.class_name = 'None'

        # start at frame 1
        self.frame_number = 1

        # background image
        self.background = None

        #   lines for concurrent drawing
        self.lines = []

        #   database
        self.annotation = None

        #   current ID
        self.current_id = 0

        #   hashtable of polygons to (obj_id, class) - reverse of DB
        self.contour2obj = {}

        #   hashtable of id's to contours
        self.obj2contour = {}

        #   drawing on/off
        self.draw = True

        #   initialize command stack
        self.command_stack = QtWidgets.QUndoStack(self)
        self.command_stack.setUndoLimit(UNDO_LIMIT)

        #   initialize tracker
        self.tracker = None

        #   items changed in current frame
        self.changed_items = []

        #   DB information for current frame at load time
        self.records = []

    def set_background(self, image):
        # add image; TODO: find a way to use self.backgroundBrush
        self.background = self.addPixmap(QtGui.QPixmap.fromImage(image))

    def set_colormap(self):
        # seed pseudo-random number generator for repeatable colormap
        np.random.seed(1)
        self.colormap = np.random.randint(low=0, high=255, size=(3, 2 ** 16))

        # calculate inverse colormap (drek follows)
        d = {obj_id: row for (obj_id, row) in enumerate([r for r in self.colormap.T])}
        self.inverse_colormap = {tuple(v): k for k, v in d.items()}

    def set_annotation(self, annotation):

        # weak reference to annotation
        self.annotation = weakref.ref(annotation)

        # assign tracker to this database
        self.tracker = Tracker.Tracker(self.annotation())

        # reset the selected class
        self.class_name = None

    def get_color(self, rgb):
        # sanity check
        if (rgb < 0).any() or (rgb > 255).any():
            return

        # set color with default transparency
        color = QtGui.QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]), TRANSPARENCY)

        # set pen
        self.pen = QtGui.QPen(color, 2, QtCore.Qt.SolidLine)

        # return color
        return color

    def load(self, frame_number, records):
        """
        :param frame_number: load all objects from this frame and add their contours
        :param records:      the records to load
        :return:
        """

        # set current frame number
        self.frame_number = frame_number

        # get contours and data from database
        self.records = records  # self._annotation.get(frame_number)

        # iterate over polygons and draw
        for r in self.records:
            # draw polygon
            self.add_contour([int(s) for s in r[3].split()], r[1], r[2], r[4])

        # clear undo stack after frame change
        self.command_stack.clear()

        # clear changed items
        self.changed_items = []

    def add_contour(self, points, obj_id, class_name, final, color=None):
        """ draw contour for given object on scene """
        if not points:
            return

        # set appropriate color
        if not color:
            color = self.get_color(self.colormap[:, obj_id])

        # extract (x, y) couples from list of points
        points = list(zip(points[::2], points[1::2]))

        # create list of Qt.QPointF from (x, y) lists
        points = [QtCore.QPointF(*p) for p in points]

        # draw current polygon
        contour = AnnotationObject(QtGui.QPolygonF(points), self.pen, color, final)

        # insert the AnnotationObject to the scene
        self.addItem(contour)

        # set tool tip
        tooltip_text = 'Object ID: {0}, class: {1}'.format(obj_id, class_name)
        if not final:
            tooltip_text += ', prediction'
        contour.setToolTip(tooltip_text)

        # save object id and class of this contour
        self.contour2obj[contour] = (obj_id, class_name)
        self.obj2contour[obj_id] = contour

        return contour

    def remove_contour(self, obj_id):
        """
        :param obj_id: to remove
        :return:
        """

        # remove graphic item
        c = self.obj2contour[obj_id]
        self.removeItem(c)

        # remove from hashtables
        self.contour2obj.pop(c)
        self.obj2contour.pop(obj_id)

    def move_contour(self, contour, obj_id, class_name):
        """
        :param contour: new contour to move to
        :param obj_id: to be moved
        :param class_name retain class
        :return:
        """

        # remove old contour
        self.removeItem(self.obj2contour[obj_id])

        # get vertices of new contour
        vertices = [contour.mapToScene(p).toPoint() for p in contour.polygon().toPolygon()]

        # get points from polygon
        points = [[vertices[i].x(), vertices[i].y()] for i in range(len(vertices))]

        # clip to image
        points = [self.clip_to_image(px, py) for [px, py] in points]

        # flatten (get rid of brackets)
        points = list(chain.from_iterable(points))

        #   re-draw
        self.add_contour(points, obj_id, class_name, True)

        return points

    def change_class(self, to_class):
        """ change class of selected items to to_class """

        # do nothing if no objects selected
        if len(self.selectedItems()) == 0:
            return

        # ask for user confirmation
        reply = QtWidgets.QMessageBox.question(QtWidgets.QMessageBox(), 'Confirm',
                                               'Change class of selected objects to ' + to_class + '?',
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                               QtWidgets.QMessageBox.No)

        if reply == QtWidgets.QMessageBox.No:
            return

        # iterate over selected items
        for contour in self.selectedItems():
            # get id
            (obj_id, class_name) = self.contour2obj[contour]

            #   change class in DB
            self.annotation().change_class(obj_id, to_class)

            # update hashtable
            self.contour2obj[contour] = (obj_id, to_class)

            # update
            contour.setToolTip('Object ID: ' + str(obj_id) + ', class ' + to_class)

    def mousePressEvent(self, event):

        # disable middle-mouse button press
        if event.button() == QtCore.Qt.MiddleButton:
            self.draw = False
            return

        p = event.scenePos().toPoint()

        # call parent event
        super(AnnotationScene, self).mousePressEvent(event)

        # if not on image do nothing
        if not self.in_image(p.x(), p.y()):
            self.draw = False
            return

        # if mouse press is over some annotation objects: TODO better way
        if isinstance(self.itemAt(event.scenePos(), self.views()[0].transform()), AnnotationObject):
            self.draw = False
            return

        # otherwise - draw polygon; set first point
        self.draw = True

        # Collect the 'drawn' points
        self.points = [p.x(), p.y()]

        # lines for concurrent drawing
        self.lines = []

        # get new ID
        self.current_id = self.annotation().get_max_id() + 1

        #   mark as a changed item (avoid tracking it again on frame change)
        self.changed_items.append(self.current_id)

        #   set color
        self.get_color(self.colormap[:, self.current_id])

    def mouseMoveEvent(self, event):

        # disable middle-mouse button press
        if event.button() == QtCore.Qt.MiddleButton:
            self.draw = False
            return

        # call parent event
        super(AnnotationScene, self).mouseMoveEvent(event)

        # if in drawing mode
        if self.draw:

            # add to points
            p = event.scenePos().toPoint()

            # clip to image size
            x, y = self.clip_to_image(p.x(), p.y())

            self.points.append(x)
            self.points.append(y)

            # current line
            l = QtWidgets.QGraphicsLineItem(QtCore.QLineF(self.points[-4], self.points[-3],
                                                          self.points[-2], self.points[-1]))
            l.setPen(self.pen)
            self.lines.append(l)

            #   draw current line
            self.addItem(self.lines[-1])

    def mouseReleaseEvent(self, event):

        # disable middle-mouse button press
        if event.button() == QtCore.Qt.MiddleButton:
            self.draw = False
            return

        # call parent event
        super(AnnotationScene, self).mouseReleaseEvent(event)

        # otherwise: new item, draw polygon
        if self.draw:
            # ignore random mouse clicks - "contours" of less than 8 points
            if len(self.points) >= 8:
                self.command_stack.push(AddCommand(self, self.frame_number, self.current_id,
                                                   self.class_name, self.points))

            # remove lines
            for l in self.lines:
                self.removeItem(l)

        # default to drawing off
        self.draw = False

    def clip_to_image(self, px, py):
        """
        :param px: x coordinate
        :param py: y coordinate
        :return: clipped x and y
        """
        bounding_rect = self.background.boundingRect()
        [x, y] = [max(0, i) for i in [px, py]]
        x = min(x, int(bounding_rect.right()))
        y = min(y, int(bounding_rect.bottom()))

        return x, y

    def in_image(self, x, y):
        bounding_rect = self.background.boundingRect()
        if x < 0 or y < 0 or x > bounding_rect.right() or y > bounding_rect.bottom():
            return False
        return True

    def delete(self):
        """ modify (redraw) current selected object (one and only one) """
        for contour in self.selectedItems():
            # get id and class
            (obj_id, class_name) = self.contour2obj[contour]

            # push delete event on stack
            self.command_stack.push(DeleteCommand(self, self.frame_number, obj_id, class_name))

            # append to changed items
            self.changed_items.append(obj_id)

    def finalize(self):
        """  mark objects that have been predicted for this frame as 'final' """
        self.annotation().finalize_frame(self.frame_number)

    def track(self):
        """ track all objects that haven't been 'touched' this frame
        :return:
        """

        # iterate over object records (note: these are from load time; it doesn't matter since
        # by definition this function only tracks objects that were untouched)

        if self.records is None:
            return

        for r in self.records:
            # don't do anything for moved items (that have already been tracked)
            if r[1] not in self.changed_items:

                # ensure object doesn't already exist in next frame (don't affect future if it already happened)
                if len(self.annotation().get(self.frame_number + 1, r[1])) == 0:
                    #   draw polygon
                    points = [int(s) for s in r[3].split()]

                    #   track. NOTE: with current tracker is superfluous since objects haven't moved by definition
                    prediction = self.tracker.track(points, self.frame_number, r[1])

                    #   add to _annotation. TODO: add as a batch (more efficient)
                    self.annotation().add(self.frame_number + 1, r[1], r[2], prediction, False)
