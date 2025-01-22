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

# Important Changing Points for Redpitaya DMA C Program

Change the DATA_SIZE in the below part to multiplications of 25k. Optimal reading and sending size in one chunk is around 27k over TCP and a little bit higher in UDP but 25k is the best option.  
```
#define DATA_SIZE                       25000
#define READ_DATA_SIZE                  25000
```

If You need to turn on logging uncomment the below part (The other part is how to put a new logging point), log.txt will be the file holding the logs:
```
// #define LOG_ACTIVITIES                  1                   // This value is 1 while debugging on points and logging otherwise put into comment

#ifdef LOG_ACTIVITIES == 1
  log_activities("rp_AcqStart failed", __LINE__);
#endif
}
```


# Link for downloading the client app of PC to recieve data in the Lab 
[https://drive.google.com/drive/folders/1wcdygnxtqzJEOLsDCntOaaj_m0lCJwOc?usp=sharing](https://drive.google.com/drive/folders/1XMiMW30eITwy5o7a4K11IW6ip89RFFfI?usp=sharing)
There are three files. 
- applab2: This handles the AP30 Redpitaya (you can check the sticker back of the Redpitaya Embedded System). So people who requires to take 75k data points use this one. 
- applab3: This handles the AP10 Redpitaya (you can check the sticker back of the Redpitaya Embedded System). So people who requires to take 50k data points use this one. 
- applab4: This handles the Unknown Redpitaya (you can check there is no sticker back of the Redpitaya Embedded System). So people who requires to take 25k data points use this one.

# Questions or Suggestions
Reach me through my Email: mashnunul.huq@hotmail.com
or By whatsapp.
