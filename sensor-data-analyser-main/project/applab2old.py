import traceback, sys
from PyQt6.QtCore import QSize, Qt, QRunnable, pyqtSlot, QThreadPool, QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QMainWindow, QGridLayout, QHBoxLayout, QCheckBox, QLabel, QLineEdit
import socket, struct
import pandas as pd
import pyqtgraph as pg
import time
import os
import paramiko



class RedPitayaSensor:
    """
    This is the class for communicating with the C program of Redpitaya

    Attributes:
        no attributes to initiate 
    """
    def __init__(self):
        self.size_of_raw_adc = 25000
        self.buffer_size = (self.size_of_raw_adc + 6) * 4 
        self.msg_from_client = "-i 1"
        self.hostIP = "169.254.77.124" #this is the default IP address of redpitaya ethernet connection 
        self.data_port = 61231 #this data port is set
        self.ssh_port = 22 #this port is for commanding via ssh using paramiko
        self.server_address_port = (self.hostIP, self.data_port)
        # Create a UDP socket at client side
        self.sensor_status_message = "Waiting to Connect with RedPitaya UDP Server!"
        print(self.sensor_status_message)
        self.udp_client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.header_length = None
        #Below is the paramiko ssh setting
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        
    def give_ssh_command(self, command):
        """
        Method for executing command through ssh on Redpitaya

        Attributes:
            command(string): full command to be executed 
        """
        try:
            # Connect to the Redpitaya device
            self.client.connect(self.hostIP, self.ssh_port, "root", "root")
            self.set_sensor_message(f"Connected to Redpitaya {self.hostIP}")
            
            # Execute the command
            stdin, stdout, stderr = self.client.exec_command(command)
            
            # Read the command 
            output = stdout.read().decode()
            error = stderr.read().decode()
            
            # Print the output and error (if any)
            self.set_sensor_message(f"Output: {output}")
            
            if error:
                self.set_sensor_message(f"Error: {error}")
                
            if output:
                return output
                
        finally:
            # Close the SSH connection
            self.client.close()
            self.set_sensor_message("Connection closed")
        
        
    def set_sensor_message(self, message):
        """
        Method for setting message for the C program on Redpitaya

        Attributes:
            message(string): currently messages can be '-a 1' or '-i 1', a for ADC data i for header-info 
        """
        self.msg_from_client = message
        
    def get_sensor_status_message(self):
        """
        Method for getting message from the C program on Redpitaya

        Attributes:
            no attribute 
        """
        return self.sensor_status_message    

    def send_msg_to_server(self):
        """
        Method for sending message to the C program on Redpitaya

        Attributes:
            no attribute 
        """
        bytes_to_send = str.encode(self.msg_from_client)
        print("Sending message")
        self.udp_client_socket.sendto(bytes_to_send, self.server_address_port)
        
    def get_data_info_from_server(self):
        """
        Method for getting Header data from the C program on Redpitaya
        Currently not saving in csv file.

        Attributes:
            no attribute 
        """
        self.msg_from_client = "-i 1" #this message is for the header info which is not saved if required save to the csv file
        self.send_msg_to_server()
        packet = self.udp_client_socket.recv(self.buffer_size)
        self.sensor_status_message = f"Sensor Connected Successfully at {self.server_address_port}!"
        print(self.sensor_status_message)
        print(f"Total Received : {len(packet)} Bytes.")
        self.header_length = int(struct.unpack('@f', packet[:4])[0])
        self.total_data_blocks = int(struct.unpack('@f', packet[8:12])[0])
        synced_time = int(struct.unpack('@f', packet[20:24])[0])
        header_data = []
        for i in struct.iter_unpack('@f', packet[:self.header_length]):
            header_data.append(i[0])
        print(f"Length of Header : {len(header_data)}")
        #below is for time sync checking
        self.local_time_sync = time.time() * 1000  # in milliseconds
        self.first_synced_time = synced_time
        return synced_time, header_data
 
        
    def get_data_from_server(self, start_time):
        """
        Method for getting ADC data from the C program on Redpitaya

        Attributes:
            start_time(time): time synchronization to dump broken signals in UDP 
        """   
        ultrasonic_data = []
        for i in range(self.total_data_blocks):
            time.sleep(1/1000)
            self.msg_from_client = "-a 1"
            self.send_msg_to_server()
            if(i == 0):
                current_time = time.time() * 1000  # in milliseconds
                elapsed_time = current_time - self.local_time_sync + start_time
                #elapsed_time = current_time - self.local_time_sync + self.first_synced_time - start_time
            packet1 = self.udp_client_socket.recv(self.buffer_size)
            current_data_block_number = int(struct.unpack('@f', packet1[12:16])[0])
            if(i != current_data_block_number):
                print(f"Error:Expected block{i} but recieved block{current_data_block_number}")
                break
            
            redpitaya_acq_time_stamp = int(struct.unpack('@f', packet1[20:24])[0])
            self.sensor_status_message = f"{current_data_block_number+1} numbered block Successfully received at {self.server_address_port} at {elapsed_time}ms of client and {redpitaya_acq_time_stamp}ms of redpitaya!"
            ultrasonic_data_length = int(struct.unpack('@f', packet1[4:8])[0])
            for i in struct.iter_unpack('@h', packet1[self.header_length:]):
                ultrasonic_data.append(i[0])

        #current_time = time.time() * 1000  # in milliseconds
        #elapsed_time = current_time - self.local_time_sync + start_time
        print(f"Length of Ultrasonic Data : {len(ultrasonic_data)}")
        
        if (len(ultrasonic_data) != 25000*self.total_data_blocks):
            return None
        
        df = pd.DataFrame(ultrasonic_data, columns=['raw_adc'])
        
        return df['raw_adc']



class Worker(QRunnable):
    """
    Class for Worker Thread

        Attributes:
            no attribute 
    """
    def __init__(self, func_is_button_checked, rp_sensor, *args, **kwargs) -> None:
        """
        Constructor for actual data recieving thread from the C program on Redpitaya

        Attributes:
            func_is_button_checked (bool): real time check box status 
            rp_sensor (RedpitayaSensorObj): RedpitayaSensor class object 
        """
        super().__init__()
        # self.realtime_checked = realtime_checked
        self.func_is_button_checked = func_is_button_checked #till realtime check-box is not checked it will not take data
        self.rp_sensor = rp_sensor
        self.dataFilePath = None
        self.saving_number_of_signals = None
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.is_running = True
        self.saved_signals_count = 0
        self.total_signals_count = 0
        self.broken_signala_count = 0

    @pyqtSlot()
    def run(self):
        """
        Main runnable method for actual data recieving thread from the C program on Redpitaya

        Attributes:
            no attribute 
        """
        print("Start of thread")
        while self.func_is_button_checked(*self.args, **self.kwargs) and self.is_running:
            # self.fn(*self.args, **self.kwargs)
            try:
                result = self.rp_sensor.get_data_from_server(window.start_time)
                self.total_signals_count += 1
                self.signals.total_signals_count_updated.emit(self.total_signals_count)
                if result is None:
                    print("No valid data recieved, skipping plot and saving")
                    self.broken_signala_count += 1
                    self.signals.broken_signals_count_updated.emit(self.broken_signala_count)
                    continue
                #put a condition to save the data inside file
                if self.saving_number_of_signals != None:
                    if self.saved_signals_count < self.saving_number_of_signals:
                        self.save_data(result)
                        self.saved_signals_count += 1
                        print(f"Saved {self.saved_signals_count} out of {self.saving_number_of_signals}")
                    else:
                        self.signals.saved_signals_count_updated.emit(self.saved_signals_count)  # Emit signal
                else:
                    self.saved_signals_count = 0
                    self.total_signals_count = 0
                    self.broken_signala_count = 0
                    #self.saving_number_of_signals = None
                        
                
            except:
                traceback.print_exc()
                exctype, value = sys.exc_info()[:2]
                self.signals.error.emit((exctype, value, traceback.format_exc()))
            else:
                self.signals.result.emit(result)
            finally:
                self.signals.finished.emit()
                print("One loop complete!")
            print(self.args, self.kwargs)
            # self.realtime_checked = self.func_is_button_checked(*self.args, **self.kwargs)
    
    
    def save_data(self, data):
        """
        Method for saving recieved data into csv file

        Attributes:
            data (numpy): actual data to be saved   
        """
        df = pd.DataFrame(data)
        print("Before transposing data shape", df.shape)
        df = df.set_index('raw_adc').transpose()
        print("After transposing data shape", df.shape)
        file_path = f"{self.dataFilePath}/signal_{self.saving_number_of_signals}.csv"
        if not os.path.exists(self.dataFilePath):
            os.makedirs(self.dataFilePath)
        df.to_csv(file_path, mode='a', index=False)
        print(f"Data saved to {file_path}")
        
    def set_saving_number_of_signals(self, saving_number_of_signals):
        """
        Method for setting number of saving data

        Attributes:
            saving_number_of_signals (int): Give the numbers of data to be saved in current shot
                                            and also file name setting with number
        """
        self.saving_number_of_signals = saving_number_of_signals
        
    def set_dataFilePath(self, dataFilePath):
        """
        Method for setting recieved data saving file name

        Attributes:
            dataFilePath (string): Absolute data file path  
        """
        self.dataFilePath = dataFilePath
        
    
    def stop(self):
        """
        Method for destroying smoothly

        Attributes:
            dataFilePath (string): Absolute data file path  
        """
        self.is_running = False

class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.

    Supported Signals are : 
        result: recieved numpy data for plotting live
        error: any error occured
        finished: for giving hints that current numbers of signal has been reached
        progress = status of connection and data recieving state
        saved_signals_count_updated: number of already saved signals 
        broken_signals_count_updated: number of broken signals recieved
        total_signals_count_updated: number of total signals including broken ones
    '''
    result = pyqtSignal(object)
    error = pyqtSignal(tuple)
    finished = pyqtSignal()
    progress = pyqtSignal(int)
    saved_signals_count_updated = pyqtSignal(int)
    broken_signals_count_updated = pyqtSignal(int)
    total_signals_count_updated = pyqtSignal(int)


class MainWindow(QMainWindow):
    """
    Class for Main Program to attach all threads and GUI

    Attributes:
        no attributes required

    """
    def __init__(self):
        """
        Constructor of Main function of the program
        All initiation of GUI and classes are present here

        Attributes:
            no attributes required
        """
        super().__init__()
        self.rp_sensor = RedPitayaSensor()
        self.start_time = None
        self.header_info = None
        self.threadpool = QThreadPool()
        self.sensor_status_message = self.rp_sensor.get_sensor_status_message()
        self.app_status_message = "App Started"
        
        self.button_is_checked = True #this is something else button for plotting area
        self.realtime_chkbox_checked = False #this is the checkbox to start the main algorithm
        self.show_region_to_select = False
        self.raw_adc_data = None
        self.previous_range_selector_region = (100, 1000)

        self.setWindowTitle("Sensor Data Analyser")

        self.plot_widget = pg.PlotWidget() #live graph plotting area
        
        
        main_layout = QGridLayout() #main layout where all child GUI components has to be registered
        main_layout.addWidget(self.plot_widget, 0, 0)
        

        # for button make sure you attach a correct function with every buttons
        self.button = QPushButton("Press Me!") #this button is for the plotting area not visible
        self.button.setCheckable(True)
        self.button.clicked.connect(self.the_button_was_toggled)
        self.button.setChecked(self.button_is_checked)
        self.button.setFixedSize(QSize(40,40))
        
        
        # Control Box section Real Time & Region-Select check box and Confirm Button
        self.controls_mid_layout = QHBoxLayout()
        
        self.realtime_chkbox = QCheckBox("Realtime")
        self.controls_mid_layout.addWidget(self.realtime_chkbox)

        self.show_region_chkbox = QCheckBox("Region-Select")
        self.controls_mid_layout.addWidget(self.show_region_chkbox)

        self.confirm_region_btn = QPushButton("Confirm") #this is for taking a window for FFT calculation
        self.controls_mid_layout.addWidget(self.confirm_region_btn)

        main_layout.addLayout(self.controls_mid_layout, 1, 0)

        
        # Server Working Progress Message showing section 
        self.message_bottom_layout = QHBoxLayout()

        self.server_message_widget = QLabel(self.sensor_status_message)
        self.message_bottom_layout.addWidget(self.server_message_widget)
        
        # Application Working Progress Messase showing section
        self.app_message_widget = QLabel(self.app_status_message_get())
        self.message_bottom_layout.addWidget(self.app_message_widget)

        # Application Working Progress Messase showing section
        self.total_signal_count_message_widget = QLabel("Total Signals Received: 0")
        self.message_bottom_layout.addWidget(self.total_signal_count_message_widget)

        # Application Working Progress Messase showing section
        self.broken_signal_count_message_widget = QLabel("Broken Signals: 0")
        self.message_bottom_layout.addWidget(self.broken_signal_count_message_widget)

        main_layout.addLayout(self.message_bottom_layout, 2, 0)
        
        self.sensor_status_message = self.rp_sensor.get_sensor_status_message()
        self.server_message_widget.setText(self.sensor_status_message)
        self.app_message_widget.setText(self.app_status_message)
        
        
        # Data Saving Path section
        self. dataFilePath = 'savedData.csv'
        self.saving_path_mid_layout = QHBoxLayout()
            # 1. Create a QLabel
        self.path_label = QLabel("Enter Saving absolute Path:")
            # 2. Create a QLineEdit
        self.file_path_line_edit = QLineEdit()
            # 3. Add the QLabel and QLineEdit to the Box layout and then to Main Layout
        self.saving_path_mid_layout.addWidget(self.path_label)
        self.saving_path_mid_layout.addWidget(self.file_path_line_edit)

        main_layout.addLayout(self.saving_path_mid_layout, 3, 0) 
            
        
        
        # Number of Signals to record section
        self.saving_number_of_signals = None
            # 1. Create a QLabel
        self.signal_numbers_label = QLabel("Enter number of signals to be saved:")
            # 2. Create a QLineEdit
        self.signal_numbers_line_edit = QLineEdit()
            # 3. Add a button for saving
        self.save_data_btn = QPushButton("Save")
            # 4. Add the QLabel, QLineEdit and Save button to the Box layout and then to Main Layout
        self.signal_numbers_layout = QHBoxLayout()
        self.signal_numbers_layout.addWidget(self.signal_numbers_label)
        self.signal_numbers_layout.addWidget(self.signal_numbers_line_edit)
        self.signal_numbers_layout.addWidget(self.save_data_btn)
        
        main_layout.addLayout(self.signal_numbers_layout, 4, 0)
            
        #SSH command related buttons
        #1. Start Sensor Button
        self.start_sensor_btn = QPushButton("Sart Sensor")
        #2. Stop Sensor pid Button
        self.stop_sensor_btn = QPushButton("Stop Sensor")
        
        #Add the buttons to the Box layout and then to Main Layout
        self.ssh_command_layout = QHBoxLayout()
        
        self.ssh_command_layout.addWidget(self.start_sensor_btn)
        self.ssh_command_layout.addWidget(self.stop_sensor_btn)
        
        main_layout.addLayout(self.ssh_command_layout, 5, 0)        
        
        
        self.widget = QWidget()
        self.widget.setLayout(main_layout)
        self.setCentralWidget(self.widget)
        
        self.range_selector = pg.LinearRegionItem()
        

        
        # add Signal Handlers and Button clicking functions
        
        self.show_region_chkbox.stateChanged.connect(self.show_region_handler)
        self.realtime_chkbox.stateChanged.connect(self.realtime_checkbox_handler)
        self.confirm_region_btn.clicked.connect(self.confirm_region_selection_btn_handler)
        
        self.worker = None
        self.save_data_btn.clicked.connect(self.save_data_btn_handler)
        self.start_sensor_btn.clicked.connect(self.start_sensor_btn_handler)
        self.stop_sensor_btn.clicked.connect(self.stop_sensor_btn_handler)


    def show_region_handler(self,state):
        """
        Method of region selection for FFT calculation

        Attributes:
            state (bool): PyQT6 program state for real_time checkbox status running and true
        """
        self.server_message_widget.setText(self.rp_sensor.get_sensor_status_message())
        if state == Qt.CheckState.Checked.value:
            print("Region select checked !")
            self.realtime_chkbox.setDisabled(True)
            self.confirm_region_btn.setDisa--bled(False)
            self.show_region_to_select = True
            # print(self.show_region_to_select)
            self.range_selector = pg.LinearRegionItem()
            self.range_selector.sigRegionChangeFinished.connect(self.region_changed_on_linear_region)
            self.range_selector.setRegion(self.previous_range_selector_region)
            print(self.range_selector.getRegion())
            self.plot_widget.addItem(self.range_selector)
        elif state == Qt.CheckState.Unchecked.value:
            self.reset_btn_view()
            self.plot_widget.removeItem(self.range_selector)

    def confirm_region_selection_btn_handler(self):
        if self.show_region_to_select:
            print("Confirmed Region : ", self.range_selector.getRegion())
            self.previous_range_selector_region = self.range_selector.getRegion()
            self.plot_adc_data()
            self.show_region_handler(self.show_region_chkbox.checkState().value)
            

    def reset_btn_view(self):
        self.realtime_chkbox.setDisabled(False)
        self.show_region_chkbox.setDisabled(False)
        self.confirm_region_btn.setDisabled(True)

    def region_changed_on_linear_region(self):
        print("Region Changed!")
        print(self.range_selector.getRegion())

    def the_button_was_toggled(self, checked):
        self.button_is_checked = checked
        print("Checked", self.button_is_checked)
        self.button.setText(f"Status: {self.button_is_checked}")
        self.plot_adc_data()

    def plot_adc_data(self, data=None):
        """
        Method for plotting the recieved data live

        Attributes:
            data (numpy): recived data, if none then nothing will be plotted
        """
        print(self.rp_sensor.get_sensor_status_message(), "------------------------------")
        self.server_message_widget.setText(self.rp_sensor.get_sensor_status_message())
        self.plot_widget.clear()
       
        x = [i for i in range(self.rp_sensor.size_of_raw_adc * self.rp_sensor.total_data_blocks)]
        if data is not None:
            y = data
        #else:
            #y = self.rp_sensor.get_data_from_server().to_list()

        self.raw_adc_data = y

        # Plot the data
        self.plot = self.plot_widget.plot(x, y)
        self.plot_widget.setBackground('black')
        print("Show region to select : ", self.range_selector.getRegion())
        if self.realtime_chkbox_checked == False:
            return False


    def realtime_checkbox_handler(self, state):
        """
        Method for realtime_checkbox work
        This is the base of all type of activity of data receiving 

        Attributes:
            state (bool): PyQT6 program state for real_time checkbox status running and true
        """
        if state == Qt.CheckState.Checked.value:
            self.realtime_chkbox_checked = True
            print("Go Realtime!")
            self.show_region_chkbox.setDisabled(True)
            self.confirm_region_btn.setDisabled(True)
            self.worker = Worker(self.func_is_realtime_checked, self.rp_sensor)
            self.worker.signals.result.connect(self.plot_adc_data)
            self.worker.signals.saved_signals_count_updated.connect(self.update_save_button_state)
            self.worker.signals.total_signals_count_updated.connect(self.total_signal_status_message_set)
            self.worker.signals.broken_signals_count_updated.connect(self.broken_signal_status_message_set)
            # start_index, end_index = self.range_selector.getRegion()
            self.threadpool.start(self.worker)
        else:
            self.realtime_chkbox_checked = False
            self.reset_btn_view()
        
    
    def func_is_realtime_checked(self):
        print("Checked : ", self.realtime_chkbox_checked)
        return self.realtime_chkbox_checked
            
            
    def app_status_message_set(self, text):
        """
        Method for setting application's current status

        Attributes:
            text (string): message to be showed in the GUI
        """
        self.app_status_message = text
        
    def app_status_message_get(self):
        """
        Method for getting application's current status

        Attributes:
            no attribute required
        """
        return self.app_status_message
    
    def broken_signal_status_message_set(self, count):
        """
        Method for showing numbers of broken signals

        Attributes:
            count (int): current total number of broken signals 
        """
        self.broken_signal_count_message_widget.setText(f"Broken Signals: {count}")
    
    
    def total_signal_status_message_set(self, count):
        """
        Method for showing numbers of signals received

        Attributes:
            count (int): current total number of signals received
        """
        self.total_signal_count_message_widget.setText(f"Total Signals Received: {count}")
        
    
    def save_data_btn_handler(self):
        """
        Method for saving button to set file path number of signals
        (Put some try catch erros)

        Attributes:
            no attribute required 
        """
        self.dataFilePath = self.file_path_line_edit.text()
        self.worker.set_dataFilePath(self.dataFilePath)
        
        self.saving_number_of_signals = int(self.signal_numbers_line_edit.text())
        self.worker.set_saving_number_of_signals(self.saving_number_of_signals)
        self.app_status_message_set(f"Saving {self.saving_number_of_signals} data in {self.dataFilePath}")
        self.app_message_widget.setText(self.app_status_message_get())
        
        #Clear both QLineEdit and disable the save button
        self.file_path_line_edit.clear()
        self.signal_numbers_line_edit.clear()
        self.save_data_btn.setDisabled(True)
        
    def start_sensor_btn_handler(self):
        """
        Method for giving command to start the sensor C program of Redpitaya 

        Attributes:
            no attributes required 
        """
        commands = ["cd /usr/RedPitaya/Examples/C", "./dma_with_udp_faster"]
        full_command = " && ".join(commands)
        self.rp_sensor.give_ssh_command(full_command)
        time.sleep(3)        
        self.start_time, self.header_info = self.rp_sensor.get_data_info_from_server() # Start time in milliseconds
        time.sleep(1)
        
    def stop_sensor_btn_handler(self):
        """
        Method for giving command to stop the sensor C program of Redpitaya 

        Attributes:
            no attributes required 
        """
        command = "pidof dma_with_udp_faster"
        pid = self.rp_sensor.give_ssh_command(command)
        command1 = f"kill {pid}"
        self.rp_sensor.give_ssh_command(command1)
        
    def update_save_button_state(self, count):
        """
        Method for updating save button state while desired number of signals are received or to be saved

        Attributes:
            count (int): current numbers of signals saved 
        """
        # Enable the save button if saved_signals_count exceeds saving_number_of_signals
        self.save_data_btn.setDisabled(False)
        self.app_status_message_set(f"Successfully saved {self.saving_number_of_signals} data")
        self.app_message_widget.setText(self.app_status_message_get())
        self.saving_number_of_signals = None
        self.worker.set_saving_number_of_signals(self.saving_number_of_signals)
        self.dataFilePath = None
        self.worker.set_dataFilePath(self.dataFilePath)
        

    def closeEvent(self, event):
        """
        Method for destroying program smoothly 

        Attributes:
            event (PyQt6.event): currently running threads events
        """
        if self.worker:
            self.worker.stop()
            self.threadpool.waitForDone()
        event.accept()
            



if __name__ == "__main__":
    """
    Function for Main Program and for command line arguments handling  
    Attributes:
        no attributes required 
    """
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())