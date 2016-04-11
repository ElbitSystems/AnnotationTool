import sqlite3 as lite
import os
import shutil
import logging
import numpy as np
import cv2
import re
from PyQt5 import QtCore, QtGui, QtWidgets


class VideoLoadError(Exception):
    """ Exception class for video loading problems """
    pass


class VideoLoadVideoNotFound(Exception):
    """ Exception class for video loading problems """
    pass


class AnnotationFileError(Exception):
    pass


class Annotation(object):
    """ contains a database of the annotations and transient data pertaining to the annotation session
    """
    # _filename suffix for annotation files
    SUFFIX = '.atc'
    TEMP_WORKING_FILENAME = '.working' + SUFFIX

    def __init__(self, filename):
        """
        Creates a new annotation or loads an existing one from file
        :param filename: video / annotation filename
        :return:
        """

        # no filename as yet
        self._filename = None

        # annotated video filename
        self.video_filename = None

        # initialize video capture
        self.cap = None
        self.num_frames = 0
        self.current_frame = 0

        # initialize database handlers
        self.cursor = self.connection = None

        # if no such file exists don't create annotation
        if not os.path.exists(filename):
            logging.error('failed to open annotation file ' + filename)
            raise AnnotationFileError('failed to open annotation ' + filename)

        # split filename
        basename, extension = os.path.splitext(filename)

        # load existing annotation
        if Annotation.SUFFIX == extension:
            self.load(filename)

        #   create from video
        else:
            #   TODO find out exe path.
            #   check if for some reason the annotation tool workspace file already exists; if so delete
            temp_filename = os.path.join(os.getcwd(), Annotation.TEMP_WORKING_FILENAME)
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

            # create new annotation (using workspace temporary file)
            self.create(filename, temp_filename)

    @staticmethod
    def update_video_filename_in_annotation(annotation, video):
        # create database
        connection = lite.connect(annotation)

        # sqlite cursor
        cursor = connection.cursor()

        cursor.execute('UPDATE session SET video_file=(?)', (video,))
        connection.commit()
        connection.close()
        return annotation

    def get_max_id(self):

        self.cursor.execute('SELECT max(object) from frames')
        try:

            # [0] since db returns (int,)
            max_id = int(self.cursor.fetchone()[0])
        except TypeError:

            # if fails, there are no values in db
            max_id = 0
        return max_id

    def is_file_saved(self):
        return self._filename != os.path.abspath(Annotation.TEMP_WORKING_FILENAME)

    def exit(self):

        # commit changes
        self.connection.commit()

    def create(self, video_filename, annotation_filename):
        """ create new annotation for video in video_filename
        :param video_filename: *.mp4, *.avi, or whatever ffmpeg can read
        :param annotation_filename: to save annotation in
        :return:
        """

        logging.info('Trying to create new annotation for video ' + str(video_filename))
        # check for non-existent file
        if not os.path.isfile(video_filename):
            logging.error('Annotation.create(): no such file ' + video_filename)
            raise VideoLoadError('Video Read Error: no such file ' + video_filename)

        self._filename = annotation_filename

        # open video capture
        self.open_video(video_filename)

        # initialize to first frame
        self.current_frame = 1

        # update _filename
        self._filename = annotation_filename

        # create database
        self.connection = lite.connect(self._filename)

        # sqlite cursor
        self.cursor = self.connection.cursor()

        # annotation database
        self.cursor.execute('''CREATE TABLE frames
                  (frame integer, object integer, class text, contour text, final integer)''')

        # classes
        self.cursor.execute('''CREATE TABLE classes (class_name text unique)''')

        # session parameters
        self.cursor.execute('''CREATE TABLE session (video_file text, current_frame integer)''')
        self.cursor.execute('INSERT INTO session VALUES(?, ?)', (video_filename, 1))

        logging.info('Annotation ' + str(annotation_filename) + ' created successfully.')

    def load(self, filename):
        """
        :param filename: Existing annotation (SQL file)
        :return:
        """

        logging.info('Trying to load annotation ' + filename)

        try:

            # connect to SQL database
            self.connection = lite.connect(filename)
            logging.info('SQL database connection achieved')

            # get cursor
            self.cursor = self.connection.cursor()

            # get session parameters
            self.cursor.execute('SELECT * FROM session')
            params = self.cursor.fetchone()

            # video filename
            video_filename = params[0]
            logging.info('Got video filename from .atc file')

            # save filename
            self._filename = filename

            # attempt to open
            self.open_video(video_filename)

            # session parameters
            self.set_frame(params[1])

        except lite.DatabaseError:
            logging.error('error reading annotation ' + filename + '. file might be corrupted')
            raise AnnotationFileError('error reading annotation ' + filename + '. file might be corrupted')

    def save(self, filename):
        """ save annotation to filename
        :param filename: new filename for annotation
        :return:
        """
        # do nothing in case already working on requested filename
        if filename != self._filename:

            # can't use the temporary workspace filename
            if filename == Annotation.TEMP_WORKING_FILENAME:
                raise ValueError('Illegal filename')

            # commit any changes to be on the safe side
            self.connection.commit()

            # close old file
            self.close()

            # copy file
            shutil.copy(self._filename, filename)

            # delete temporary file in case we were working on it till now
            if self._filename == Annotation.TEMP_WORKING_FILENAME:
                os.remove(self._filename)

            # load new database
            self.load(filename)

            # delete temporary file
            if os.path.exists(Annotation.TEMP_WORKING_FILENAME):
                os.remove(Annotation.TEMP_WORKING_FILENAME)

    def close(self):
        if self.connection:
            self.connection.close()

    def set_frame(self, frame_number):
        """
        :param frame_number: to set position at
        :return:
        """

        if frame_number < 1 or frame_number > self.num_frames:
            logging.warning('Illegal frame number {0} requested '.format(frame_number))
            return

        self.current_frame = frame_number

        # save session
        self.cursor.execute('UPDATE session SET current_frame=(?)', (self.current_frame,))
        self.connection.commit()

    def get_frame_image(self):
        """
        :return: image at current frame; note reading current_frame-1 to account for 0-based opencv read as opposed to
        1-based user requests
        """

        if self.cap is None:
            return

        # read frame (annoying opencv version difference)
        if int(cv2.__version__[0]) < 3:
            self.cap.set(cv2.cv.CV_CAP_PROP_POS_FRAMES, self.current_frame - 1)
        else:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame - 1)

        # get from video capture
        ret, frame = self.cap.read()

        # check for failure
        if not ret:
            error_message = 'error reading frame ' + str(self.current_frame)
            logging.error(error_message)
            raise VideoLoadError(error_message)
        return frame

    def open_video(self, video_filename):
        """ open video capture
        :param video_filename: to open
        :return: set video capture, video filename and number of frames
        """
        logging.info('Attempt to open video ' + str(video_filename))

        # split filename
        basename, extension = os.path.splitext(video_filename)

        # handle image names
        if extension in ['.jpg', '.bmp', '.tiff', '.tif', '.png']:

            # find how many consecutive 0's in filename
            *_, b = basename.split('/')
            zeros = re.search('0+', b).group(0)
            pat = '%' + str(len(zeros)) + 'd'

            # python magic to replace last appearance of 'zeros' with 'pat'
            video_filename = video_filename[::-1].replace(zeros[::-1], pat[::-1], 1)[::-1]

        # attempt to open
        self.cap = cv2.VideoCapture(video_filename)

        # check for success
        if not self.cap.isOpened():
            # log
            logging.error('Annotation.open_video(): failed to open video ' + video_filename)

            # reset capture
            self.cap = None

            # raise exception
            e = VideoLoadVideoNotFound('failed to open video ' + video_filename + '. file might have been moved or corrupted')
            e.filename = self._filename
            raise e

        # get number of frames
        if int(cv2.__version__[0]) < 3:
            self.num_frames = int(np.round(self.cap.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT)))
        else:
            self.num_frames = int(np.round(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)))

        # update video filename
        self.video_filename = video_filename
        logging.info('Opened video ' + str(video_filename) + ' successfully.')

    def add_class(self, class_name):
        """
        :param class_name: new class to be added
        :return:
        """

        # check if duplicate
        if class_name in self.classes():
            return

        # insert to table
        self.cursor.execute('INSERT INTO classes VALUES (?)', (class_name,))

        # commit changes
        self.connection.commit()

    def add(self, frame_number, object_id, class_name, contour, final):
        """
        :param frame_number: video frame to which to add object (int)
        :param object_id: integer
        :param class_name: classification (int)
        :param contour: list of integers in format (y, x, y, x)
        :param final: predicted/final boolean
        :return:
        """

        # insert to table
        self.cursor.execute('INSERT INTO frames VALUES(?, ?, ?, ?, ?)',
                            (frame_number, object_id, class_name,
                             ' '.join([str(x) for x in contour]), final))

        # commit changes
        self.connection.commit()

    def remove(self, object_id, frame=None):
        """
        :param object_id: id of object to be removed (integer)
        :param frame: frame to remove object from. if None will remove from all
        :return:
        """
        if frame is None:
            # note trailing comma to create a tuple
            self.cursor.execute('DELETE from frames where object=(?)', (object_id,))
        else:
            self.cursor.execute('DELETE from frames where object=(?) and frame=(?)', (object_id, frame))

        # commit changes
        self.connection.commit()

    def get(self, frame_number, obj_id=None, class_name=None):
        """
        :param class_name: 
        :param frame_number: return objects (all or one) in this frame (integer)
        :param obj_id: ID's of object to return. if None return all (...)
        :return:
        """
        if obj_id is not None:
            self.cursor.execute('SELECT * FROM frames where frame=(?) and object=(?)', (frame_number, obj_id))
        elif class_name is not None:
            self.cursor.execute('SELECT * FROM frames where frame=(?) and class=(?) ORDER BY object', (frame_number, class_name))
        else:
            # note trailing comma to create a tuple
            self.cursor.execute('SELECT * FROM frames WHERE frame=(?) ORDER BY object', (frame_number,))

        return self.cursor.fetchall()

    def change_class(self, obj_id, class_name):
        """
        :param obj_id: object to change class for
        :param class_name: new class name
        :return:
        """
        # update class
        self.cursor.execute('UPDATE frames SET class=(?) WHERE object=(?)', (class_name, obj_id))

        # commit changes
        self.connection.commit()

    def finalize_object(self, obj_id, frame_number):
        """
        :param obj_id: set object as "final" (as opposed to predicted)
        :param frame_number: to set
        :return:
        """
        # update
        self.cursor.execute('UPDATE frames SET final=1 WHERE object=(?) AND frame=(?)', (obj_id, frame_number))

        # commit changes
        self.connection.commit()

    def finalize_frame(self, frame_number):
        """ finalize all objects in frame
        :param frame_number: to set
        :return:
        """
        # update
        self.cursor.execute('UPDATE frames SET final=1 WHERE frame=(?)', (frame_number,))

        # commit changes
        self.connection.commit()

    def combine_objects(self, from_id, to_id):
        """
        This function combine two objects. Gives both the id "to_id" and eliminates the id "from_id"
        :param from_id: integer
        :param to_id: integer
        :return:
        """

        # check if one of the id's is a negative number
        if (from_id <= 0) | (to_id <= 0):
            raise ValueError('object ID\'s must be positive integers')

        # check if from id not exist in DB
        self.cursor.execute('SELECT 1 FROM frames WHERE object = (?)', (from_id,))
        if not self.cursor.fetchall():
            raise ValueError('Error: "From ID" is not exist')

        # check if to id not exist in DB
        self.cursor.execute('SELECT 1 FROM frames WHERE object = (?)', (to_id,))
        if not self.cursor.fetchall():
            raise ValueError('Error: "To ID" is not exist')

        # check if from id and to id share same frame
        self.cursor.execute('SELECT 1 FROM frames WHERE object = (?) AND frame in'
                            '(SELECT frame FROM frames WHERE object = (?))', (from_id, to_id))
        if self.cursor.fetchall():
            raise ValueError('Error: There are frames with both objects')

        # get the class of the 'to_id' in DB
        self.cursor.execute('SELECT class FROM frames WHERE object = (?) LIMIT 1', (to_id,))

        # get the class of the "to_id"
        class_to_id = self.cursor.fetchall()[0][0]

        # combine objects
        self.cursor.execute('UPDATE frames SET object=(?), class=(?) WHERE object=(?)', (to_id, class_to_id, from_id))

        # commit changes
        self.connection.commit()

    def get_frames_indexes_of_id(self, obj_id):
        """
        This function return list of frames the given ID exists in annotation
        :param obj_id: integer
        """

        self.cursor.execute('SELECT * FROM frames where object=(?)', (obj_id,))
        data = self.cursor.fetchall()
        if not data:
            data_frames = []
        else:
            data_mat = np.array(data)
            data_frames = [int(x) for x in data_mat[:, 0]]

        return data_frames

    def get_annotations_of_id(self, obj_id):
        """
        This function returns entries relevant to obj_id from all frames
        :param obj_id: integer
        """

        # Get all data from frames table relevant to obj_id
        self.cursor.execute('SELECT * FROM frames where object=(?) ORDER BY frame', (obj_id,))
        return self.cursor.fetchall()

    def filename(self):
        """
        :return: annotation _filename
        """
        return self._filename

    def classes(self):
        """
        :return: list of available classes
        """
        self.cursor.execute('SELECT * FROM classes')
        return [c[0] for c in self.cursor.fetchall()]
