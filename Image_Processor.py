"""
Image Processor

Runs a series of actions of image files found in a list of directories

- When executed without arguments, the tool opens with the UI.
- If the optional '-headless' argument is supplied, it will automatically run on the supplied directory list.
"""



# IMPORTS
import sys
import os
import stat
import time

import wx
import xml.dom.minidom
import xml.etree.cElementTree as ET
import  wx.lib.rcsizer as rcs
from PIL import Image



# Set up Perforce API stuff
try:
    import P4
    p4 = P4.P4( )
except:
    p4 = None



# CONSTANTS
ARG_HEADLESS				= '-headless'
ARG_DIRS					= '-dirs='
ARG_LOG_FILEPATH			= '-logfile='
ARG_EXTENTIONS				= '-exts='
ARG_ACTIONS					= '-actions='
LOG_FILE_DEFAULT_NAME		= 'Batch_Image_Processor_Report'
IMAGE_EXTENSTIONS			= [ 'tga', 'png', 'bmp', 'jpg' ]
IMAGE_EXTENSTIONS.sort( )


class Base_Image_Action( object ):
    """
    A Simple base class that all image actions should subclass from.
    Simply subclass this, populate the class attributes, and then
    fill out the test functionality logic in the execute method and
    the UI will auto scoop up these into the Optional Actions section.
    """

    action_name		= 'base_image_action'
    widget_class	= wx.CheckBox
    widget_title	= 'Base Image Action'
    status_msg 		= 'Performing empty action on'
    add_to_ui		= True
    can_execute		= False


    @classmethod
    def update_can_execute( *args, **kwargs ):
        # Find the class object
        cls = None
        for arg in args:
            try:
                if issubclass( arg, Base_Image_Action ):
                    cls = arg
            except:
                pass

        # Find an event object
        event = None
        for arg in args:
            if isinstance( arg, wx._core.CommandEvent ):
                event = arg

        if cls and event:
            cls.process_event_can_execute( event )


    @classmethod
    def process_event_can_execute( cls, event ):
        """
        If the widget is anything other then a wx.CheckBox,
        override this class method to know how to process
        that widget class's event to determine if this test
        class should be performed.
        """

        if cls.widget_class == wx.CheckBox:
            cls.can_execute = event.IsChecked( )


    @classmethod
    def execute( cls, image_obj ):
        pass
        # Enter your action logic here.
        # Return a bool to indicate if the test passed or failed.
        # Return a results string with info on the test result

        return False, "Failed, no test run on file"



#======================================================================================
#======================================================================================
#======================================================================================
"""
Add new image actions here by subclassing the Base_Image_Action class and overriding
the classmethods with testing logic that suits your needs.

Every new class derived from Base_Image_Action will automatically be added to the
UI's "Optional Actions" section. This makes it extremly simple to add a new action
and have it automatically added to the UI without updating the UI code.

It's possible to make an action required and something that does not show up in the UI,
always running on the files by setting the 'add_to_ui' class attribute to False and
setting the 'can_execute' class attribute to True.
"""

class Action_Compress_PNG( Base_Image_Action ):
    """
    Simple action that will resave any PNG file in its compressed state
    to save memory on disk.

    Any image object handed to the execute method will be ignored unless
    it's a PNG file.
    """

    action_name		= 'compress_png'
    widget_title	= 'Compress PNGs'
    status_msg 		= 'Compressing '
    add_to_ui		= True
    can_execute		= True

    @classmethod
    def execute( cls, image_obj ):
        # First check to make sure the file we're operating on is actually a PNG.
        # Otherwise, ignore this file.
        if image_obj.filename.lower( ).endswith( '.png' ):
            success		= False
            report_msg	= "Failed to complete the action for unknown reasons"

            # First, before opening the image, get it's current on disk file size
            file_stats = os.stat( image_obj.filename )
            original_file_size = file_stats.st_size

            if not image_obj.is_open:
                image_obj.open( )

            # Currently, PIL's image.save( ) method ignores the optional 'optimize' argument,
            # always saving the image in a compressed size. Now this still essentially gets
            # the job done of compressing a png on disk. But it seems like a broken implimentation
            # that I'd like to investigate in the future and fix if possible.
            image_obj.save( optimize = True )

            # After the file has been saved again, check it's file size once more to get a difference
            file_stats = os.stat( image_obj.filename )
            new_file_size = file_stats.st_size
            file_size_diff = original_file_size - new_file_size

            # If the file size has changed, report the action as passed
            if file_size_diff > 0:
                success = True
                kb_raw = str( int( float( file_size_diff ) / 1024.0 * 100 ) )
                kb_str = "{0}.{1}".format( kb_raw[ 0:-2 ], kb_raw[ -2:len( kb_raw ) ] )
                report_msg = "Compression saved {0} kbs on disk".format( kb_str )
            # Otherwise, no compression happened so the action failed
            elif file_size_diff == 0:
                success = False
                report_msg = "Compression did not save any memory on disk"
        else:
            success = False
            report_msg = "{0} is not a PNG file".format( os.path.basename( image_obj.filename )	)

        return success, report_msg



class Action_Check_Power_Of_2( Base_Image_Action ):
    """
    Simple action for make sure the image is a power of 2.
    Meaning its width and height are divisible by 2.
    """

    action_name		= 'check_power_of_2'
    widget_title	= 'Check Power of 2'
    status_msg 		= 'Checking Power of 2 on'

    @classmethod
    def execute( cls, image_obj ):
        if not image_obj.is_open:
            image_obj.open( )

        w, h = image_obj.image.size

        w_pow = w != 0 and ( ( w & ( w - 1 ) ) == 0 )

        h_pow = h != 0 and ( ( h & ( h - 1 ) ) == 0 )

        if w_pow and h_pow:
            success = True
            report_msg = "Width:{0} and Height:{1} are both a proper power of 2".format( w, h )
        else:
            success = False
            report_msg = "Either Width:{0} or Height:{1} is NOT a proper power of 2".format( w, h )

        return success, report_msg



class Action_Verify_PBR_Values( Base_Image_Action ):
    """
    Action that will perform a series of tests to ensure the image file
    meets proper PBR authoring standards of the studio.
    """

    action_name		= 'verify_pbr_values'
    widget_title	= 'Verify PBR Values'
    status_msg 		= 'Verifying PBR Values on'

    @classmethod
    def execute( cls, image_obj ):
        success		= True
        report_msg	= "Passed all PBR validation tests"

        # Open the image with PIL if it hasn't already been opened
        if not image_obj.is_open:
            image_obj.open( )

        # Split out the image's channels for furthur examination
        if image_obj.image.mode == 'RGB':
            red, green, blue = image_obj.image.split( )
            alpha = None
        if image_obj.image.mode == 'RGBA':
            red, green, blue, alpha = image_obj.image.split( )

        # Metal (Red Channel) Check
        if image_obj.filename.lower( ).endswith( '_mra.png' ):
            bad_pixels = 0 # A count of pixels that are neither 0 or 255 in value
            for pixel in red.getdata( ):
                if pixel > 0 and pixel < 255:
                    bad_pixels += 1

            if bad_pixels > 0:
                success		= False

                perc_str = "{0:.0f}".format( float( bad_pixels ) / float( len( red.getdata( ) ) ) * 100.0 )
                if perc_str == '0':
                    perc_str	= 'Less than {0}'.format( perc_str )
                report_msg	= "{0}% of the pixels in the red channel are not valid METAL values".format( perc_str )

            if bad_pixels == 0:
                success = True

        return success, report_msg

#======================================================================================
#======================================================================================
#======================================================================================


class Log_File( object ):
    """
    A simple class to handle the duties of writing to and saving
    of the log file generated by the tool.
    """

    def __init__( self, filename ):
        self.filename		= filename
        self.file_results = { }
        self.file_fails	= { }
        self.save_log		= True

        self.start_time = 0
        self.end_time = 0
        self.completed = False


    def clear( self ):
        self.file_results.clear( )
        self.file_fails.clear( )


    def set_filename( self, filename ):
        self.filename = filename


    def add_file_fail( self, filename, action_name, results ):
        """
        Add to the file_fails list
        """

        if filename in self.file_fails:
            self.file_fails[ filename ].append( ( action_name, results ) )
        else:
            self.file_fails[ filename ] = [ ( action_name, results ) ]


    def add_file_result( self, filename, action_name, success, results ):
        if filename in self.file_results:
            self.file_results[ filename ].append( ( action_name, success, results ) )
        else:
            self.file_results[ filename ] = [ ( action_name, success, results ) ]


    def save( self ):
        if self.save_log:
            root_element = ET.Element( 'root' )
            failed_element = ET.SubElement( root_element, 'failed' )
            complete_element = ET.SubElement( root_element, 'complete_results' )

            # Write out all of the filed actions first
            for filename in self.file_fails:
                file_element = ET.SubElement( failed_element, 'file' )
                file_element.set( 'filename', filename )

                for results in self.file_fails[ filename ]:
                    action_element = ET.SubElement( file_element, 'action' )
                    action_element.set( 'name', str( results[ 0 ] ) )		# Action name
                    action_element.set( 'report', str( results[ 1 ] ) )	# Any reporting info

            # Write out all the results
            for filename in self.file_results:
                file_element = ET.SubElement( complete_element, 'file' )
                file_element.set( 'filename', filename )

                for results in self.file_results[ filename ]:
                    action_element = ET.SubElement( file_element, 'action' )
                    action_element.set( 'name', str( results[ 0 ] ) )		# Action name
                    action_element.set( 'passed', str( results[ 1 ] ) )	# Did the action pass or fail
                    action_element.set( 'report', str( results[ 2 ] ) )	# Any reporting info

            # Reformat the xml string using the minidom toprettystring so the file is human readable
            xml_str = ET.tostring( root_element, 'utf-8' )
            parse_str = xml.dom.minidom.parseString( xml_str )
            xml_str = parse_str.toprettyxml( indent = "\t" )

            # Save the contents to disk
            f = open( self.filename, 'w' )
            f.write( xml_str )
            f.close( )



class Image_Object( object ):
    """
    This class is responsible for the handeling of the image file.

    It performs standard duties like open (in PIL), save, checkout
    and submit from Perforce.

    This class is handed to an Image_Action class so the class can
    perform its execute method on this object.
    """

    def __init__( self, filename ):

        # First check that the file path exists. Assert if not
        if not os.path.exists( filename ):
            assert 0, "Filename cannot be found"

        self.filename		= filename
        self.image			= None
        self.is_editable	= False
        self.is_open		= False


    def _update_is_editable( self ):
        self.is_editable = False

        file_att = os.stat( self.filename )[ 0 ]
        if ( file_att & stat.S_IWRITE ):
            self.is_editable = True


    def open( self ):
        self.image = Image.open( self.filename )
        self.is_open = True


    def save( self, filename = None, *args, **kwargs ):
        self._update_is_editable( )

        if self.is_editable and self.is_open:
            if not filename:
                filename = self.filename

            self.image.save( filename, *args, **kwargs )


    def checkout( self ):
        #if p4:
            #p4.connect( )

            #p4.run_edit( self.filename ) # This filename will have to be converted into a depot path in order to work

            #p4.disconnect( )

        self._update_is_editable( )

        return self.is_editable


    def submit( self ):
        #if p4:
            #p4.connect( )

            #new_change_list						= p4.fetch_change( )
            #new_change_list[ 'Files' ]			= [ self.filename ] # This filename will have to be converted into a depot path in order to work
            #new_change_list[ 'Description' ]	= 'Image Processor Batch Operations'

            #p4.run_submit( new_change_list )

            #p4.disconnect( )

        self._update_is_editable( )

        return self.is_editable



class Image_Batch( object ):
    """
    This is the main class for handeling the duties of performing the batch operation.

    Given a list of folders and file extensions, this will go thru each file and perform
    a list of actions on each file.
    """

    def __init__( self, headless = False, frame = None, dirs = [ ], log_filepath = None, extensions = [ ], actions = None, auto_start = False, status_bar = None, status_bar_title = None ):

        self.set_log_filepath( log_filepath )

        self.headless		= headless
        self.frame			= frame
        self.dirs			= dirs
        self.extensions	= extensions
        self.actions		= actions
        self.log				= Log_File( self.log_filepath )
        self.save_log		= True

        self.status_value	= 0
        self.status_incr	= 0

        if auto_start:
            self.start( )


    def set_save_log( self, value ):
        self.save_log = value
        self.log.save_log = value

    def get_dirs( self ):
        return self.dirs


    def set_dirs( self, dirs ):
        self.dirs = dirs


    def get_extensions( self ):
        return self.extensions


    def set_extensions( self, extensions ):
        self.extensions = extensions


    def get_log_filepath( self ):
        return self.log_filepath


    def set_log_filepath( self, log_filepath ):
        # If no log filename was supplied, or the filename is supplied but its path doesn't exist,
        # then create a log in the same path as this script.
        if not log_filepath or not os.path.exists( os.path.dirname( log_filepath ) ):
            self.log_filepath = os.path.join( os.path.dirname( __file__ ), "{0}.xml".format( LOG_FILE_DEFAULT_NAME ) )
        else:
            self.log_filepath	= log_filepath

        if hasattr( self, 'log' ):
            self.log.set_filename( self.log_filepath )


    def get_image_files( self, directory ):
        # Go thru all of the directories and pull out image files whose extensions
        # match the list of extensions this batch is running
        files = [ ]

        if os.path.exists( directory ):
            all_files	= [ os.path.join( directory, f ) for f in os.listdir( directory ) if os.path.isfile( os.path.join( directory, f ) ) ]
            files			= [ f for f in all_files if os.path.splitext( f )[ -1 ].replace( '.', '' ) in self.extensions ]

        return files


    def update_status_incr( self ):
        file_count = 0
        for directory in self.dirs:
            file_count += len( self.get_image_files( directory ) )

        self.status_incr = 100.0 / float( file_count )


    def update_status_value( self, value = None ):
        if value == None:
            value = self.status_value + self.status_incr

        self.status_value = value

        if self.headless:
            print "{0}% ....".format( value )
        elif self.frame:
            if hasattr( self.frame, 'update_status_value' ):
                self.frame.update_status_value( value )


    def update_status_msg( self, msg ):
        if self.headless:
            print msg
        elif self.frame:
            if hasattr( self.frame, 'update_status_msg' ):
                self.frame.update_status_msg( msg )


    def get_subclass_actions_to_perform( self ):
        """
        Will go thruogh the list of Image Actions and return only
        the ones that are set to can_export or actions that are
        in the command line's -actions= argument.
        """

        actions = [ ]

        for sub_class in Base_Image_Action.__subclasses__( ):
            # Check to see if the item is in the actions list supplied by the command line
            if self.actions:
                if sub_class.action_name in self.actions:
                    actions.append( sub_class )

            else:
                if sub_class.can_execute:
                    actions.append( sub_class )

        return list( set( actions ) )


    def start( self ):
        # Clear the log file incase the batch is being run in the same tool instance
        self.log.clear( )

        # Figure out the status incrimental values
        self.update_status_incr( )
        self.update_status_value( value = 0 )

        # Record the start time of the batch operation
        self.log.start_time = time.time( )

        # Get the list of actions to perform on this batch process
        actions = self.get_subclass_actions_to_perform( )

        for directory in self.dirs:
            image_files = self.get_image_files( directory )
            for image in image_files:
                # Update the status
                self.update_status_value( )

                # Create our image image to perform operations on it
                image_obj = Image_Object( image )

                # Now go thru all of the extras and perform that test on the file
                for sub_class in actions:
                    self.update_status_msg( "{0}: {1}".format( sub_class.status_msg, os.path.basename( image_obj.filename ) ) )

                    success, results = sub_class.execute( image_obj )

                    # Log the results of the extra test
                    self.log.add_file_result( image_obj.filename, sub_class.action_name, success, results )

                    # If the test failed, add it to the log's list of failed results
                    if not success:
                        self.log.add_file_fail( image_obj.filename, sub_class.action_name, results )

        # Batch is done, record the end time
        self.log.end_time = time.time( )
        self.log.completed = True
        self.log.save( )

        self.update_status_value( 100.0 )
        self.update_status_msg( "Batch Completed" )



class Image_Processor_Frame( wx.Frame ):
    """
    The main UI for the tool
    """

    def __init__( self, parent, headless = False, dirs = [ ], extensions = [ 'png' ], log_filepath = '' ):
        wx.Frame.__init__ ( self, parent, id = wx.ID_ANY, title = "Image Processor", pos = wx.DefaultPosition,
                            size = ( 450, 500 ), style = wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL )

        # ATTRIBUTES
        self.dirs			= dirs
        self.extensions	= extensions
        self.log_filepath	= log_filepath


        # BUILD UI
        #=======================================================
        side_buffer = 8

        # Main Sizer
        self.main_sizer = wx.BoxSizer( wx.VERTICAL )
        self.SetSizer( self.main_sizer )


        # CheckListBox to allow the user to specify image extension types
        self.main_sizer.AddSpacer( 5 )
        self.main_sizer.Add( wx.StaticText( self, wx.ID_ANY, "Image Extensions to Process:" ), 0, wx.LEFT, side_buffer + 2 )
        self.clb_extensions = wx.CheckListBox( self, wx.ID_ANY, ( -1, -1 ), ( -1, 72 ), IMAGE_EXTENSTIONS )
        self.main_sizer.Add( self.clb_extensions, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, side_buffer )
        self.clb_extensions.Bind( wx.EVT_CHECKLISTBOX, self.on_exts_changed )


        # Listbox for multiple directories to run the batch on
        self.main_sizer.AddSpacer( 5 )
        self.main_sizer.Add( wx.StaticText( self, wx.ID_ANY, "Directories to Process:" ), 0, wx.LEFT, side_buffer + 2 )

        self.lst_dirs = wx.ListBox( self, wx.ID_ANY, choices = self.dirs, style = wx.LB_MULTIPLE )
        self.main_sizer.Add( self.lst_dirs, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, side_buffer )


        # Listbox Add\Remove buttons
        self.main_sizer.AddSpacer( 3 )
        btn_sizer = wx.BoxSizer( wx.HORIZONTAL )

        self.btn_add_dir = wx.Button( self, wx.ID_ANY, "Add Directories", size = ( -1, 20 ) )
        btn_sizer.Add( self.btn_add_dir, 1, wx.EXPAND )
        self.btn_add_dir.Bind( wx.EVT_BUTTON, self.on_add_dir_pressed )

        self.btn_rem_dir = wx.Button( self, wx.ID_ANY, "Remove Directories", size = ( -1, 20 ) )
        btn_sizer.Add( self.btn_rem_dir, 1, wx.EXPAND )
        self.btn_rem_dir.Bind( wx.EVT_BUTTON, self.on_rem_dir_pressed )

        self.main_sizer.Add( btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, side_buffer )


        # Extra Options
        #=====================================
        self.main_sizer.AddSpacer( 10 )
        box = wx.StaticBox( self, wx.ID_ANY, "Optional Actions:" )
        self.box_sizer = wx.StaticBoxSizer( box, wx.VERTICAL )
        grid_sizer = rcs.RowColSizer( )
        grid_sizer.AddGrowableCol( 0 )
        grid_sizer.AddGrowableCol( 1 )
        self.box_sizer.Add( grid_sizer, 1, wx.EXPAND )
        self.main_sizer.Add( self.box_sizer, 0,  wx.EXPAND | wx.LEFT | wx.RIGHT, 15 )

        # Loop thru all of the Base_Image_Action subclasses and add a widget to the options panel
        row = 0
        col = 0
        idx = 0
        for sub_class in Base_Image_Action.__subclasses__( ):
            if sub_class.add_to_ui:
                widget = sub_class.widget_class( self, wx.ID_ANY, sub_class.widget_title )
                widget.SetValue( sub_class.can_execute )
                grid_sizer.Add( widget, 0, wx.LEFT | wx.BOTTOM, side_buffer, row = row, col = col )
                widget.Bind( wx.EVT_CHECKBOX, sub_class.update_can_execute )

                if idx % 2 == 0:
                    col += 1
                else:
                    row += 1
                    col = 0

                idx += 1


        # Output log file
        self.main_sizer.AddSpacer( 10 )
        self.use_log = wx.CheckBox( self, wx.ID_ANY, "Create Output Log" )
        self.use_log.Bind( wx.EVT_CHECKBOX, self.on_use_log_checked )
        self.use_log.SetValue( True )
        self.main_sizer.Add( self.use_log, 0, wx.LEFT, side_buffer + 2 )
        self.main_sizer.AddSpacer( 2 )

        log_sizer = wx.BoxSizer( wx.HORIZONTAL )
        self.main_sizer.Add( log_sizer, 0, wx.EXPAND )

        self.txt_log_filename = wx.StaticText( self, wx.ID_ANY, "Filename:" )
        log_sizer.Add( self.txt_log_filename, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, side_buffer )
        self.txt_log_path = wx.TextCtrl( self, wx.ID_ANY, self.log_filepath )
        log_sizer.Add( self.txt_log_path, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 4 )
        log_sizer.AddSpacer( 1 )
        self.txt_log_path.Bind( wx.EVT_TEXT, self.on_log_path_changed )

        self.btn_browse_log_path = wx.Button( self, wx.ID_ANY, "...", size = ( 33, -1 ) )
        log_sizer.Add( self.btn_browse_log_path, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4 )
        self.btn_browse_log_path.Bind( wx.EVT_BUTTON, self.on_browse_log_pressed )


        # Start Button
        self.main_sizer.AddSpacer( 10 )
        self.btn_start_batch = wx.Button( self, wx.ID_ANY, "Start Processor", size = ( -1, 33 ) )
        self.btn_start_batch.Enable( False )
        self.main_sizer.Add( self.btn_start_batch, 0, wx.EXPAND | wx.ALL, 5 )
        self.btn_start_batch.Bind( wx.EVT_BUTTON, self.on_start_pressed )


        # Status Bar
        self.txt_status_msg = wx.StaticText( self, wx.ID_ANY, "Status: <inactive>" )
        self.main_sizer.Add( self.txt_status_msg, 0, wx.LEFT | wx.RIGHT, side_buffer + 2 )
        self.status_bar = wx.Gauge( self, wx.ID_ANY )
        self.main_sizer.Add( self.status_bar, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, side_buffer )
        self.main_sizer.AddSpacer( 5 )
        #=======================================================

        # Create the batch class
        self.batch = Image_Batch( headless = headless, frame = self, log_filepath = self.log_filepath, status_bar = self.status_bar, status_bar_title = self.txt_status_msg )

        # Get the log filepath after the batch has had a chance to validate it
        self.log_filepath = self.batch.get_log_filepath( )

        # Other random UI stuff
        self.SetBackgroundColour( wx.Colour( 225, 225, 225 ) )

        self.refresh_ui( )


    def on_use_log_checked( self, event ):
        self.batch.set_save_log( event.IsChecked( ) )

        self.refresh_ui( )

        event.Skip( )


    def on_browse_log_pressed( self, event ):
        dlg = wx.FileDialog(
            self, message = "Choose a filepath to save your log output",
            defaultDir = os.path.dirname( self.log_filepath ),
            defaultFile = "",
            wildcard = "XML File (*.xml)|*.xml",
            style = wx.OPEN | wx.CHANGE_DIR
        )

        # Show the dialog and retrieve the user response. If it is the OK response,
        # process the data.
        if dlg.ShowModal( ) == wx.ID_OK:
            self.log_filepath = dlg.GetPaths( )[ 0 ]

        self.refresh_ui( )

        event.Skip( )


    def update_status_value( self, value ):
        self.status_bar.SetValue( value )


    def update_status_msg( self, msg ):
        self.txt_status_msg.SetLabelText( "Status: {0}".format( msg ) )
        self.txt_status_msg.Update( )


    def on_log_path_changed( self, event ):
        self.log_filepath = self.txt_log_path.GetValue( )
        event.Skip( )


    def on_exts_changed( self, event ):
        self.extensions = self.clb_extensions.GetCheckedStrings( )

        self.refresh_ui( )

        event.Skip( )


    def on_add_dir_pressed( self, event ):
        dir_to_add = [ ]

        dlg = wx.DirDialog( self, "Choose a directory:", style = wx.DD_DEFAULT_STYLE )

        if dlg.ShowModal( ) == wx.ID_OK:
            dir_to_add.append( dlg.GetPath( ) )

        dlg.Destroy( )

        if dir_to_add:
            self.dirs.extend( dir_to_add )
            self.dirs = list( set( self.dirs ) )
            self.dirs.sort( )
            self.lst_dirs.SetItems( self.dirs )

        self.refresh_ui( )

        event.Skip( )


    def on_rem_dir_pressed( self, event ):
        sel_dirs = [ ]

        for idx in self.lst_dirs.GetSelections( ):
            path = self.lst_dirs.GetItems( )[ idx ]
            if path in self.dirs:
                self.dirs.remove( path )

        self.lst_dirs.SetItems( self.dirs )
        self.refresh_ui( )

        event.Skip( )


    def on_start_pressed( self, event ):
        self.batch.set_dirs( self.dirs )
        self.batch.set_log_filepath( self.log_filepath )
        self.batch.set_extensions( self.extensions )

        self.batch.start( )

        event.Skip( )


    def refresh_ui( self ):
        # Update the extensions check list
        for ext in self.extensions:
            idx = [ f_ext.lower( ) for f_ext in IMAGE_EXTENSTIONS ].index( ext.lower( ) )
            if idx > 0:
                self.clb_extensions.Check( idx, True )
            else:
                self.clb_extensions.Check( idx, False )

        # Refresh the start button. If there are no current dirs, then disbale it
        self.btn_start_batch.Enable( False )
        if self.dirs:
            self.btn_start_batch.Enable( True )

        # Refresh the remove dirs button. If there are no dirs in the current list, then disable it
        self.btn_rem_dir.Enable( False )
        if self.dirs:
            self.btn_rem_dir.Enable( True )

        # Disable the start button if there are no extensions checked
        if len( self.clb_extensions.GetChecked( ) ) == 0:
            self.btn_start_batch.Enable( False )

        # Update the log path controls
        if self.use_log.GetValue( ):
            self.txt_log_filename.Enable( True )
            self.txt_log_path.Enable( True )
            self.btn_browse_log_path.Enable( True )
        else:
            self.txt_log_filename.Enable( False )
            self.txt_log_path.Enable( False  )
            self.btn_browse_log_path.Enable( False )
        self.txt_log_path.SetValue( self.log_filepath )


#-actions='check_power_of_2','verify_pbr_values'
def run( arguments ):
    """
    First entry point for the application.

    Pulls out any possible arguments supplied by the command line
    and feeds them into the tool.

    If the tool was not started by the command line, then there
    should be no arguments to gather and the tool's frame will
    open up with no values filled out.
    """
    headless			= False
    dirs				= [ ]
    extensions		= [ ]
    actions			= None
    log_filepath	= ''

    # First pull out any arguments that may have been passed
    if ARG_HEADLESS in arguments:
        headless	= True

    for arg in arguments:
        ARG_EXTENTIONS
        # Directories to perform the batch on
        if arg.startswith( ARG_DIRS ):
            dirs = arg[ len( ARG_DIRS ):len( arg ) ].split( ',' )

        # Extensions to perform the batch on
        if arg.startswith( ARG_EXTENTIONS ):
            extensions = arg[ len( ARG_EXTENTIONS ):len( arg ) ].split( ',' )

        # Image Actions to perform the batch on
        if arg.startswith( ARG_ACTIONS ):
            actions = arg[ len( ARG_ACTIONS ):len( arg ) ].split( ',' )

        # Log file to report data to
        if arg.startswith( ARG_LOG_FILEPATH ):
            log_filepath = arg.lstrip( ARG_LOG_FILEPATH )

    # If running in headless mode, immediatly start the batch function
    if headless:
        Image_Batch( headless = headless, dirs = dirs, extensions = extensions, actions = actions, log_filepath = log_filepath, auto_start = True )

    # Otherwise, present the UI to the user
    else:
        app = wx.App( False )

        frame = Image_Processor_Frame( None, headless = headless, dirs = dirs, extensions = extensions, log_filepath = log_filepath )
        frame.Show( True )

        app.MainLoop( )



if __name__ == '__main__':
    run( sys.argv )
