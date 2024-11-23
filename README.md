# Redpitaya Deep Memory Acquisition Code for ADC Data collection and sending to Python Client Application [![Awesome](https://cdn.jsdelivr.net/gh/sindresorhus/awesome@d7305f38d29fed78fa85652e3a63e154dd8e8829/media/badge.svg)]

Basically this is a rapid data collection and sending program for Redpitaya built on OS 2.00.18
The Ultrasonic sensor is built By Michallic of Frankfurt University of Applied Sciences.

This data collection is usable for every student of Information Technology (M.Eng.) program of Frankfurt University of Applied Sciences.

First to turn on the sensor a program named ./dma_with_udp_faster

| Command | Description |
| --- | --- |
| DMA code repositoryin Redpitaya | cd /usr/RedPitaya/Examples/C |
| Cmake command to make new program | make dma_with_udp_faster |
| Start Sensor | ./dma_with_udp_faster |

The cmake file is created on top of basic Redpitaya example Cmake file. (Given in this repository)

These starting sensor and shutting down of sensor can also be done using the client application built on PyQt6.
![successfully taken 100 data](https://github.com/user-attachments/assets/2bc4f2d7-8530-43db-a030-aea853b68d24)

Make sure before taking data the Start Sensor button is pushed and the Red sensor light is on. After that check the Realtime checkbox and make sure the data is visible.
After that please remember almost first 5500 data points the sending pulse is present. While applying machine learning codes remove these.

Now to save the data put the saving folder's absolute path and number of signals. A csv file mentioning the number of signals will be created automatically.

