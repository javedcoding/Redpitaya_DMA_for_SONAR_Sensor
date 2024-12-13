# -*- coding: utf-8 -*-
"""
Created on Wed Sep  4 19:34:43 2024

@author: Abdur Rahim
"""

import traceback, sys
from PyQt6.QtCore import QSize, Qt, QRunnable, pyqtSlot, QThreadPool, QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QMainWindow, QGridLayout, QHBoxLayout, QVBoxLayout, QCheckBox, QLabel, QLineEdit
from PyQt6.QtGui import QPixmap, QImage
import socket, struct
import pandas as pd
import pyqtgraph as pg
import time
import os
import paramiko
import logging
from camera_detection_test import YOLOCamera
import cv2
from collections import deque

class RedPitayaSensor:
    def __init__(self):
        self.size_of_raw_adc = 25000
        self.buffer_size = (self.size_of_raw_adc + 6) * 4 
        self.msg_from_client = "-i 1"
        self.hostIP = "192.168.128.1"
        self.data_port = 61231    
        self.ssh_port = 22
        self.server_address_port = (self.hostIP, self.data_port)
        # Create a UDP socket at client side
        self.sensor_status_message = "Waiting to Connect with RedPitaya UDP Server!"
        print(self.sensor_status_message)
        self.udp_client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.header_length = None
        # Initialize counter for data received
        self.data_counter = 0
        
        
    def give_ssh_command(self, command):
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
        self.msg_from_client = message
        
    def get_sensor_status_message(self):
        return self.sensor_status_message    

    def send_msg_to_server(self):
        bytes_to_send = str.encode(self.msg_from_client)
        print("Sending message")
        self.udp_client_socket.sendto(bytes_to_send, self.server_address_port)
        
    def get_data_info_from_server(self):
        self.msg_from_client = "-i 1"
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
        self.local_time_sync = time.time() * 1000  # in milliseconds
        self.first_synced_time = synced_time
        return synced_time, header_data
 
        
    def get_data_from_server(self, start_time):   
        ultrasonic_data = []
        total_duration = 0
        for i in range(self.total_data_blocks):
            time.sleep(1/1000)
            self.msg_from_client = "-a 1"
            # Record the time before sending the first message
            send_time = time.time()
            self.send_msg_to_server()
            
            #if(i == 0):
            current_time = time.time() * 1000  # in milliseconds
            elapsed_time = current_time - self.local_time_sync + start_time
            elapsed_time = current_time - self.local_time_sync + self.first_synced_time - start_time
           
            packet1 = self.udp_client_socket.recv(self.buffer_size)
            
            receive_time = time.time()
            duration = (receive_time - send_time)*1000
            total_duration += duration
            #self.sensor_status_message =f"Total round trip time for all blocks: {duration:.6f} ms"
            current_data_block_number = int(struct.unpack('@f', packet1[12:16])[0])
            if(i != current_data_block_number):
                print(f"Error:Expected block{i} but recieved block{current_data_block_number}")
                break
            
            redpitaya_acq_time_stamp = int(struct.unpack('@f', packet1[20:24])[0])
            self.sensor_status_message = f"{current_data_block_number+1} numbered block Successfully received at {self.server_address_port} at {elapsed_time}ms of client and {redpitaya_acq_time_stamp}ms of redpitaya!"
            ultrasonic_data_length = int(struct.unpack('@f', packet1[4:8])[0])
            for i in struct.iter_unpack('@h', packet1[self.header_length:]):
                ultrasonic_data.append(i[0])
                
            # Increment the data received counter
            self.data_counter += 1
        
        # Record the time after receiving the final block
        print(f"Total duration for all send-receive cycles: {total_duration:.6f} ms")
        print(f"Total ultrasonic data packets received: {self.data_counter}")
        #self.sensor_status_message = f"Total round trip time for all blocks: {total_duration:.6f} ms"
        
        # Calculate the total duration


        #current_time = time.time() * 1000  # in milliseconds
        #elapsed_time = current_time - self.local_time_sync + start_time
        print(f"Length of Ultrasonic Data : {len(ultrasonic_data)}")
        
        if (len(ultrasonic_data) != 25000*self.total_data_blocks):
            return None
        
        df = pd.DataFrame(ultrasonic_data, columns=['raw_adc'])
        
        return df['raw_adc'], self.data_counter



class PlotWorker(QRunnable):
    '''
    Worker thread for plotting and signal taking
    '''
    def __init__(self, func_is_button_checked, rp_sensor, *args, **kwargs) -> None:
        super().__init__()
        # self.realtime_checked = realtime_checked
        self.func_is_button_checked = func_is_button_checked
        self.rp_sensor = rp_sensor
        self.dataFilePath = None
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.is_running = True
        self.saved_signals_count = 0
        self.sensor_data_buffer = deque(maxlen=10)  # Store the last 10 sensor readings
        self.total_signals_count = 0

    @pyqtSlot()
    def run(self):
        print("Start of thread")
        while self.func_is_button_checked(*self.args, **self.kwargs) and self.is_running:
            # self.fn(*self.args, **self.kwargs)
            try:
                (result, data_counter) = self.rp_sensor.get_data_from_server(window.start_time)
                self.total_signals_count = data_counter
                self.signals.total_signals_count_updated.emit(self.total_signals_count)  # Emit signal
                
                if result is None:
                    print("No valid data recieved, skipping plot and saving")
                    continue
                #put a condition to save the data inside file
                else:
                    sensor_timestamp = time.time()
                    self.sensor_data_buffer.append({"timestamp": sensor_timestamp, "data": result})
                    print(f"Stored sensor data with timestamp {sensor_timestamp}")
                    self.save_data(result)
                    self.saved_signals_count += 1
                    print(f"Saved {self.saved_signals_count} signals")
                    self.signals.signals_count_updated.emit(self.saved_signals_count)  # Emit signal

                        
                
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
        df = pd.DataFrame(data)
        print("Before transposing data shape", df.shape)
        df = df.set_index('raw_adc').transpose()
        print("After transposing data shape", df.shape)
        file_path = f"{self.dataFilePath}/signal.csv"
        if not os.path.exists(self.dataFilePath):
            os.makedirs(self.dataFilePath)
        df.to_csv(file_path, mode='a', index=False)
        print(f"Data saved to {file_path}")
        
        
    def set_dataFilePath(self, dataFilePath):
        self.dataFilePath = dataFilePath
        
    
    def stop(self):
        self.is_running = False
        
        
class YOLODetectionWorker(QRunnable):
    '''
    YOLO Detection Task to be executed in a separate thread.
    Inherits from QRunnable to handle worker thread setup, signals, and wrap-up.
    '''
    def __init__(self):
        super().__init__()
        self.camera = YOLOCamera(model_path="C:/models/yolo/yolov8n.pt") #the model path later to be removed
        self.signals = WorkerSignals()
        self.is_running = True  # Add a flag to control the loop
        
        
    @pyqtSlot()
    def run(self):
        '''
        Run the detection task. This method will be executed when the task is started by the QThreadPool.
        '''
        while self.is_running:
            success, img = self.camera.cap.read()
            
            if not success:
                print("Failed to capture image.")
                break
            
            # Process the frame using YOLOCamera
            detection_data = self.camera.run_person_detection_step(img)
            
            # Check if detection_data is valid
            if detection_data:
                person_detected = detection_data["person_detected"]
                distance_to_person = detection_data["distance"]  if detection_data["distance"] is not None else 0.0
                processed_image = detection_data["image"]
                timestamp = detection_data["timestamp"]
                
                if person_detected:
                    print(f"Person detected! Distance: {distance_to_person:.2f} m")
                else:
                    print("No person detected.")
                    
                # Emit a signal to notify detection result
                self.signals.person_detected.emit(person_detected, distance_to_person,timestamp)
            else:
                print("Detection data is None.")
                person_detected = False
                distance_to_person = 0.0
                processed_image = img
                
                # Emit a signal to notify detection result
                self.signals.person_detected.emit(person_detected, distance_to_person,timestamp)
                
           
                    
            # Convert the processed image to QImage
            height, width, channel = processed_image.shape
            bytes_per_line = 3 * width
            qimg = QImage(processed_image.data, width, height, bytes_per_line, QImage.Format.Format_BGR888)
            
            # Emit the frame to update the UI
            self.signals.update_frame.emit(qimg)
            
            
            if not self.is_running:
                break
                        
                    
            #if cv2.waitKey(1) & 0xFF == ord('q'):
            #    break
             
        # Release resources
        self.camera.cap.release()
        cv2.destroyAllWindows()
        
    def stop(self):
        self.is_running = False  # Method to stop the thread
        
            
class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.

    Supported Signals are : 

    result
        data returned from rp sensor to plot on GUI
    '''

    result = pyqtSignal(object)
    error = pyqtSignal(tuple)
    finished = pyqtSignal()
    progress = pyqtSignal(int)
    signals_count_updated = pyqtSignal(int)
    total_signals_count_updated = pyqtSignal(int)
    
    #These are added newly for YOLODetectionWorker signaling
    person_detected = pyqtSignal(bool, float, float)
    update_frame = pyqtSignal(object)  # This will emit the QImage for frame updates
    
    


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
# =============================================================================
#         #Initiation of required variables
# =============================================================================
        self.rp_sensor = RedPitayaSensor()
        self.start_time = None
        self.header_info = None
        self.yolo_worker = None
        self.plotWorker = None
        self.threadpool = QThreadPool()
        self.sensor_status_message = self.rp_sensor.get_sensor_status_message()
        self.app_status_message = "App Started"
        self.previous_distance = 0.0
        self.previous_detection_state = False
        self.app_status_message = QLabel("App Started")
        
        
        self.button_is_checked = True
        self.realtime_chkbox_checked = False
        self.show_region_to_select = False
        self.raw_adc_data = None
        self.previous_range_selector_region = (100, 1000)
        #main_layout.addWidget(self.app_status_message, 2, 1)  # or wherever appropriate

        self.setWindowTitle("Sensor Data Analyser")

        self.plot_widget = pg.PlotWidget()
        
        # YOLO video feed label
        self.video_label = QLabel(self)
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Create a horizontal layout to hold both plot_widget and video_label
        self.plot_video_layout = QHBoxLayout()
        self.plot_video_layout.addWidget(self.plot_widget)
        self.plot_video_layout.addWidget(self.video_label)
        
        main_layout = QGridLayout()
        main_layout.addLayout(self.plot_video_layout, 0, 0)
        

        # for button
        self.button = QPushButton("Press Me!")
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

        self.confirm_region_btn = QPushButton("Confirm")
        self.controls_mid_layout.addWidget(self.confirm_region_btn)

        main_layout.addLayout(self.controls_mid_layout, 1, 0)

        
        # Server Working Progress Message showing section 
        self.message_bottom_layout = QHBoxLayout()

        self.server_message_widget = QLabel(self.sensor_status_message)
        self.message_bottom_layout.addWidget(self.server_message_widget)
        
        # Application Working Progress Messase showing section
        self.app_message_widget = QLabel(self.app_status_message_get())
        self.message_bottom_layout.addWidget(self.app_message_widget)

        main_layout.addLayout(self.message_bottom_layout, 2, 0)
        
        self.sensor_status_message = self.rp_sensor.get_sensor_status_message()
        self.server_message_widget.setText(self.sensor_status_message)
        #self.app_message_widget.setText(self.app_status_message)
        # Make sure you add self.app_status_message to the layout
        main_layout.addWidget(self.app_status_message, 2, 1)  # or wherever appropriate
        
        # Data Saving Path section
        self.dataFilePath = 'savedData'
        
        # Number of Signals to record section
        self.saving_number_of_signals = None
            # 1. Create a QLabel
        self.signal_numbers_label = QLabel("0 Signals have been recorded")
            # 3. Add a button for saving
        self.save_data_btn = QPushButton("Save")
            # 4. Add the QLabel, QLineEdit and Save button to the Box layout and then to Main Layout
        self.signal_numbers_save_layout = QHBoxLayout()
        self.signal_numbers_save_layout.addWidget(self.signal_numbers_label)
        
        # Number of Signals to record section
        self.total_number_of_signals = None
            # 1. Create a QLabel
        self.total_signal_numbers_label = QLabel("0 Signals have been recieved")
            # 3. Add the QLabel, QLineEdit and Save button to the Box layout and then to Main Layout
        self.signal_numbers_save_layout.addWidget(self.total_signal_numbers_label)
        
        self.signal_numbers_save_layout.addWidget(self.save_data_btn)
        
        main_layout.addLayout(self.signal_numbers_save_layout, 3, 0)
            
        #SSH command related buttons
        #1. Start Sensor Button
        self.start_sensor_btn = QPushButton("Sart Sensor")
        #2. Stop Sensor pid Button
        self.stop_sensor_btn = QPushButton("Stop Sensor")
        
        #Add the buttons to the Box layout and then to Main Layout
        self.ssh_command_layout = QHBoxLayout()
        
        self.ssh_command_layout.addWidget(self.start_sensor_btn)
        self.ssh_command_layout.addWidget(self.stop_sensor_btn)
        
        main_layout.addLayout(self.ssh_command_layout, 4, 0)        
        
        
        # YOLO video feed label and open button
        self.open_yolo_button = QPushButton("Start YOLO Detection")
        main_layout.addWidget(self.open_yolo_button, 5, 0)
        
        
        self.widget = QWidget()
        self.widget.setLayout(main_layout)
        self.setCentralWidget(self.widget)
        
        self.range_selector = pg.LinearRegionItem()
        

        
        # add Signal Handlers and Button clicking functions
        
        self.show_region_chkbox.stateChanged.connect(self.show_region_handler)
        self.realtime_chkbox.stateChanged.connect(self.realtime_checkbox_handler)
        self.confirm_region_btn.clicked.connect(self.confirm_region_selection_btn_handler)
        
# =============================================================================
#         self.save_data_btn.clicked.connect(self.save_data_btn_handler)
# =============================================================================
        self.start_sensor_btn.clicked.connect(self.start_sensor_btn_handler)
        self.stop_sensor_btn.clicked.connect(self.stop_sensor_btn_handler)
        
        # YOLO Detection
        self.open_yolo_button.clicked.connect(self.start_yolo_detection)
        
        
        
    def start_yolo_detection(self):
        if not self.yolo_worker:  # Start only if YOLO is not running
            self.yolo_worker = YOLODetectionWorker()
            self.yolo_worker.signals.update_frame.connect(self.update_video_feed)
            self.yolo_worker.signals.person_detected.connect(self.handle_person_detected)
            self.threadpool.start(self.yolo_worker)
            self.open_yolo_button.setText("Stop YOLO Detection")
            self.app_status_message.setText("YOLO Detection has started")
        else:
            self.stop_yolo_detection()

    def stop_yolo_detection(self):
        if self.yolo_worker:
            self.yolo_worker.stop()
            self.threadpool.waitForDone()
            self.yolo_worker = None
            self.open_yolo_button.setText("Start YOLO Detection")

    def update_video_feed(self, qimg):
        pixmap = QPixmap.fromImage(qimg)
        self.video_label.setPixmap(pixmap)

    
    def handle_person_detected(self, detected, distance,timestamp):
        selected_dataFilePath = self.dataFilePath
        if self.plotWorker is not None:
            if self.plotWorker.sensor_data_buffer:
                # Find the sensor data from 1 second earlier (since the sensor has a 1s delay)
                adjusted_detection_time = timestamp - 1  # Adjust YOLO time to match delayed sensor data
                sensor_data_buffer = self.plotWorker.sensor_data_buffer
                closest_sensor_data = min(sensor_data_buffer, key=lambda x: abs(x["timestamp"] - adjusted_detection_time))
                sensor_timestamp_diff = abs(closest_sensor_data["timestamp"] - adjusted_detection_time)
                print(f"YOLO detection timestamp: {adjusted_detection_time}")
                print(f"Closest sensor data timestamp: {closest_sensor_data['timestamp']}")
                print(f"Timestamp difference: {sensor_timestamp_diff}")
                if sensor_timestamp_diff < 0.5:
                    if abs(distance - self.previous_distance) > 0.2: #this is the disstance sensitivity
                        selected_dataFilePath = os.path.join(selected_dataFilePath, 'Doubt')
                        self.plotWorker.set_dataFilePath(selected_dataFilePath)
                    else:
                        if detected:
                            # Person detected
                            if 0 < distance < 1.7:
                                selected_dataFilePath = os.path.join(selected_dataFilePath, 'Person')
                                self.plotWorker.set_dataFilePath(selected_dataFilePath)
                            else:
                                selected_dataFilePath = os.path.join(selected_dataFilePath, 'Object')
                                self.plotWorker.set_dataFilePath(selected_dataFilePath)
                        else:
                            # No person detected, could be an object or nothing
                            selected_dataFilePath = os.path.join(selected_dataFilePath, 'Object')
                            self.plotWorker.set_dataFilePath(selected_dataFilePath)
                        

                else:
                    print("No sensor data sync within threshold, skipping save.")
                    #selected_dataFilePath = os.path.join(selected_dataFilePath, 'Object')
                    # Update the path for saving data
                
                print(f"Data saved in: {selected_dataFilePath}")
        else:
            #selected_dataFilePath = os.path.join(selected_dataFilePath, 'Object')
            print("Sensor data buffer is empty, skipping save.")


        self.previous_distance = distance


    def show_region_handler(self,state):
        self.server_message_widget.setText(self.rp_sensor.get_sensor_status_message())
        if state == Qt.CheckState.Checked.value:
            print("Region select checked !")
            self.realtime_chkbox.setDisabled(True)
            self.confirm_region_btn.setDisabled(False)
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
        
        if state == Qt.CheckState.Checked.value:
            self.realtime_chkbox_checked = True
            print("Go Realtime!")
            self.show_region_chkbox.setDisabled(True)
            self.confirm_region_btn.setDisabled(True)
            self.plotWorker = PlotWorker(self.func_is_realtime_checked, self.rp_sensor)
            self.plotWorker.signals.result.connect(self.plot_adc_data)
            self.plotWorker.signals.total_signals_count_updated.connect(self.update_total_signal_numbers)
            self.plotWorker.signals.signals_count_updated.connect(self.update_saved_signal_numbers)
            # start_index, end_index = self.range_selector.getRegion()
            self.threadpool.start(self.plotWorker)
        else:
            self.realtime_chkbox_checked = False
            self.reset_btn_view()
        
    
    def func_is_realtime_checked(self):
        print("Checked : ", self.realtime_chkbox_checked)
        return self.realtime_chkbox_checked
            
            
    def app_status_message_set(self, text):
        self.app_status_message = text
        
        
    def app_status_message_get(self):  
        return self.app_status_message
    
    
    def save_data_btn_handler(self):
        self.dataFilePath = self.file_path_line_edit.text()
        self.plotWorker.set_dataFilePath(self.dataFilePath)
        
        self.saving_number_of_signals = int(self.signal_numbers_line_edit.text())
        self.plotWorker.set_saving_number_of_signals(self.saving_number_of_signals)
        self.app_status_message_set(f"Saving {self.saving_number_of_signals} data in {self.dataFilePath}")
        self.app_message_widget.setText(self.app_status_message_get())
        
        #Clear both QLineEdit and disable the save button
        self.file_path_line_edit.clear()
        self.signal_numbers_line_edit.clear()
        self.save_data_btn.setDisabled(True)
        
    def start_sensor_btn_handler(self):
        commands = ["cd /usr/RedPitaya/Examples/C", "./dma_with_udp"]
        full_command = " && ".join(commands)
        self.rp_sensor.give_ssh_command(full_command)
        time.sleep(3)        
        self.start_time, self.header_info = self.rp_sensor.get_data_info_from_server() # Start time in milliseconds
        time.sleep(1)
        
    def stop_sensor_btn_handler(self):
        command = "pidof dma_with_udp"
        pid = self.rp_sensor.give_ssh_command(command)
        command1 = f"kill {pid}"
        self.rp_sensor.give_ssh_command(command1)
        
    def update_saved_signal_numbers(self, count):
        # Enable the save button if saved_signals_count exceeds saving_number_of_signals
        self.signal_numbers_label.setText(f"{count} signals saved")
        
    def update_total_signal_numbers(self, count):
        # Enable the save button if saved_signals_count exceeds saving_number_of_signals
        self.total_signal_numbers_label.setText(f"{count} signals received")
        
    #Below functions are all for YOLO window
    def open_yolo_window(self):
        self.yolo_window.show()
        

    def closeEvent(self, event):
        if self.yolo_worker:
            self.stop_yolo_detection()
        if self.plotWorker:
            self.plotWorker.stop()
            self.threadpool.waitForDone()
        event.accept()
        
        
            



if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Create and show the main window
    window = MainWindow()
    window.show()
    
    
    sys.exit(app.exec())