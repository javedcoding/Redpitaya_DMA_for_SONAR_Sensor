/* This code is sued for starting continous ranging on SRF02 sensor
 *
 * (c) Red Pitaya  http://www.redpitaya.com
 *
 * This part of code is written in C programming language.
 * Please visit http://en.wikipedia.org/wiki/C_(programming_language)
 * for more details on the language used herein.
 * it is in /usr/RedPitaya/Examples/C
 * Possible decimations:
 * RP_DEC_1, RP_DEC_2, RP_DEC_4, RP_DEC_8, RP_DEC_16 , RP_DEC_32 , RP_DEC_64 ,
 * RP_DEC_128, RP_DEC_256, RP_DEC_512, RP_DEC_1024, RP_DEC_2048, RP_DEC_4096, RP_DEC_8192,
 * RP_DEC_16384, RP_DEC_32768, RP_DEC_65536
 */

// ***************************************************** //
// *************** Libray Integration ****************** //
// ***************************************************** //
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <linux/ioctl.h>
#include <sys/ioctl.h>
#include <linux/i2c-dev.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>

#include <stdint.h>
#include "rp.h"
#include <arpa/inet.h>

// ***************************************************** //
// ********* Static Global Variable Declaration ******** //
// ***************************************************** //

//Defining IsquareC protocol addresses (Start8bitSlaveAddr-Ack8bitInternalRegisterAddr-Ack8bitData-AckStop)
#define I2C_SLAVE_FORCE                 0x0706      // This is for the Forced Slave bus address
#define I2C_SLAVE                       0x0703      // This is for the Slave bus address
#define I2C_FUNCS                       0x0705      // This is for the I square C functions defining address
#define I2C_RDWR                        0x0707      // This is for I square C data Read and Write address

//Define Sensor frequency and other properties
#define V_SONIC_WAVE                    (float)(343.2)  // [m/s] Schallgeschwindigkeit in Luft
#define DECIMATION_FACTOR		        RP_DEC_64 	// This is the descimation factor or number of points channel 1 will take in 1 second

#define ADC_MAX_SAMPLE_FREQUENCY        125000000                                               // [Hz] --> 125 MHz
#define ADC_SAMPLE_DECIMATION           64                                                      // [-]
#define ADC_SAMPLE_FREQUENCY            ( ADC_MAX_SAMPLE_FREQUENCY / ADC_SAMPLE_DECIMATION )
#define ADC_SAMPLE_TIME                 8               // [ns]
#define ADC_SAMPLE_TIME_NS              (uint32_t)( ADC_SAMPLE_DECIMATION * ADC_SAMPLE_TIME )   // [ns] --> 8*64=512 ns / sample
#define ADC_START_DELAY_US              (uint32_t)( 0.30 * 2 * 1e6 / V_SONIC_WAVE )     // [µs] --> 2 * 0,30 m / 343,2 m/s = 1.748 µs
// #define ADC_BUFFER_DELAY_US             (uint32_t)(( ADC_BUFFER_SIZE * ADC_SAMPLE_TIME_NS ) / (1e3))    // [µs] --> (16.384 * 512 ns ) / 1000 = 8.388 µs
// #define ADC_MID_US                      (ADC_START_DELAY_US + ( ADC_BUFFER_DELAY_US / 2 ))


//Define the whole data size to capture through the SONAR sensor and the sending data size through UDP
#define DATA_SIZE                       60000
#define READ_DATA_SIZE                  20000

//Initiate all the Redpitaya board led state (from LED 7-9 is used by system)
#define LEDx_INIT()                     rp_DpinSetDirection( RP_LED0, RP_OUT ), \
                                        rp_DpinSetDirection( RP_LED1, RP_OUT ), \
                                        rp_DpinSetDirection( RP_LED2, RP_OUT ), \
                                        rp_DpinSetDirection( RP_LED3, RP_OUT ), \
                                        rp_DpinSetDirection( RP_LED4, RP_OUT ), \
					                    rp_DpinSetDirection( RP_LED5, RP_OUT ), \
					                    rp_DpinSetDirection( RP_LED6, RP_OUT ), \
                                        rp_DpinSetState( RP_LED0, RP_LOW ),     \
                                        rp_DpinSetState( RP_LED1, RP_LOW ),     \
                                        rp_DpinSetState( RP_LED2, RP_LOW ),     \
                                        rp_DpinSetState( RP_LED3, RP_LOW ),     \
                                        rp_DpinSetState( RP_LED4, RP_LOW ),     \
                                        rp_DpinSetState( RP_LED5, RP_LOW ),     \
					                    rp_DpinSetState( RP_LED6, RP_LOW )           

//Define LED
#define LED0_OFF                        rp_DpinSetState( RP_LED0, RP_LOW  )
#define LED1_OFF                        rp_DpinSetState( RP_LED1, RP_LOW  )
#define LED2_OFF                        rp_DpinSetState( RP_LED2, RP_LOW  )
#define LED3_OFF                        rp_DpinSetState( RP_LED3, RP_LOW  )
#define LED4_OFF                        rp_DpinSetState( RP_LED4, RP_LOW  )
#define LED5_OFF                        rp_DpinSetState( RP_LED4, RP_LOW  )
#define LED6_OFF                        rp_DpinSetState( RP_LED4, RP_LOW  )
#define LED0_ON                         rp_DpinSetState( RP_LED0, RP_HIGH )
#define LED1_ON                         rp_DpinSetState( RP_LED1, RP_HIGH )
#define LED2_ON                         rp_DpinSetState( RP_LED2, RP_HIGH )
#define LED3_ON                         rp_DpinSetState( RP_LED3, RP_HIGH )
#define LED4_ON                         rp_DpinSetState( RP_LED4, RP_HIGH )
#define LED5_ON                         rp_DpinSetState( RP_LED4, RP_HIGH )
#define LED6_ON                         rp_DpinSetState( RP_LED4, RP_HIGH )

//Define the IP address of the connected PC and the port to send data through UDP
#define UDP_IP                          "192.168.128.17"    // This is the connecting pc ip address by default DHCP
#define UDP_PORT                        61231               // This is the connecting UDP port of the PC



// ***************************************************** //
// ************ Enumerator Type Definations ************ //
// ***************************************************** //

/* Type definatons for global struct of iic */
struct iic_s
{
    int         fd;
    int         address;
    char        buf[4];
    char        *fileName;
}iic = {
    .address    = 0x70,
    .fileName   = "/dev/i2c-0"
};

/* Typedefs for data structs: Header and data */
typedef struct
{
	int16_t HeaderLength;
	int16_t SampleFrequency;
	int16_t ADCResolution;
	int16_t p_data[DATA_SIZE];
}Header_t;

/* Typedefs for data structs: Header and data */
typedef struct
{
	int         socket;
	socklen_t   length;
	char        command;
    struct      sockaddr_in serveraddr;
}udp_t;



// ***************************************************** //
// *************** Function Declarations *************** //
// ***************************************************** //
static udp_t    udp;



// ***************************************************** //
// *************** Function Declarations *************** //
// ***************************************************** //
void initiate_redpitaya_with_dma();
void initiate_iic();
void initiate_udp_connection();
void acquire_data();
void read_and_send_data();
void release_resources();



// ***************************************************** //
// ******************* Main Function ******************* //
// ***************************************************** //
int main(int argc, char **argv)
{
    initiate_redpitaya_with_dma();
    initiate_udp_connection();
    initiate_iic();
    acquire_data();
    read_and_send_data();
    release_resources();
    return 0;
}


// ***************************************************** //
// *************** Function Declarations *************** //
// ***************************************************** //

/*
*@brief     This is the function to initiate redpitaya
*           with deep memory acquisition 
*
*@details   This function initiates redpitaya, then 
*           initiates necessary steps for deep memory
*           acquisition
*
*
*/
void initiate_redpitaya_with_dma(){
    /* Initialise Red Pitaya */
    if (rp_InitReset(false) != RP_OK) {
        fprintf(stderr, "Rp api init failed!\n");
        return -1;
    }

    /* Set Datapin0 as low or no use */
    rp_DpinSetDirection( RP_DIO0_P, RP_IN);     // DIO0 as input
    rp_DpinSetState( RP_DIO0_P, RP_LOW);        // DIO0 set to low 


    /* Set up the Deep Memory Acquisition */ 
    uint32_t g_adc_axi_start, g_adc_axi_size;
    rp_AcqAxiGetMemoryRegion(&g_adc_axi_start, &g_adc_axi_size);
    printf("Reserved memory Start 0x%X Size 0x%X\n", g_adc_axi_start, g_adc_axi_size);

    /* Set decimation for both channels */
    if (rp_AcqAxiSetDecimationFactor(DECIMATION_FACTOR) != RP_OK) {
        fprintf(stderr, "rp_AcqAxiSetDecimationFactor failed!\n");
        return -1;
    }

    /* Set trigger delay for channel */
    if (rp_AcqAxiSetTriggerDelay(RP_CH_1, DATA_SIZE)  != RP_OK) {
       fprintf(stderr, "rp_AcqAxiSetTriggerDelay RP_CH_1 failed!\n");
       return -1;
    }

    /*
    Set-up the Channel 1 buffers to each work with half the available memory space.
    */
    if (rp_AcqAxiSetBufferSamples(RP_CH_1, g_adc_axi_start, DATA_SIZE) != RP_OK) {
        fprintf(stderr, "rp_AcqAxiSetBuffer RP_CH_1 failed!\n");
        return -1;
    }

    /* Enable DMA on channel 1 */
    if (rp_AcqAxiEnable(RP_CH_1, true)) {
        fprintf(stderr, "rp_AcqAxiEnable RP_CH_1 failed!\n");
        return -1;
    }
    printf("Enable CHA 1\n");

    /* Specify the acquisition trigger level*/
    rp_AcqSetTriggerLevel(RP_T_CH_1, 0);
}


/*
*@brief     This is the function to initiate I2C
*           communication with sensor 
*
*@details   This function initiates redpitaya's I square C 
*           communication with the SONAR sensor
*
*
*/
void initiate_iic(){
    /* Open I²C port for reading and writing and also turning on the sensor */ 
    if ((iic.fd = open(iic.fileName, O_RDWR)) < 0) {
        exit(1);
    }

    /* Set the port options and set the address of the device we wish to speak to through I2C protocol */ 
    if (ioctl(iic.fd, I2C_SLAVE_FORCE, iic.address) < 0) {
        exit(1);
    }
}


/*
*@brief     This is the function to initiate UDP connection 
*
*@details   This function initiates redpitaya's UDP
*           connection with necessary steps for socket 
*           binding
*
*
*/
void initiate_udp_connection(){

    memset(&udp.serveraddr, 0, sizeof(udp.serveraddr));
    /* Set up the UDP port with address */ 
    udp.socket = socket(AF_INET, SOCK_DGRAM, 0);
    if (udp.socket == -1) {
        perror("Error creating UDP socket");
        exit(EXIT_FAILURE);
    }

    udp.length = sizeof(udp.serveraddr);

    udp.serveraddr.sin_family = AF_INET;
    udp.serveraddr.sin_port = htons(UDP_PORT);
    inet_pton(AF_INET, UDP_IP, &udp.serveraddr.sin_addr);

}

/*
*@brief     This is the function to acquire sensor data 
*
*@details   This function acquires the data from the sensor
*
*
*/
void acquire_data(){
    // I²C programming - start ultrasonic
    iic.buf[0] = 0;             // measurement of distance
    iic.buf[1] = 0x52;          // measurement of time

    if ((write(iic.fd, iic.buf, 2)) != 2) {
        exit(1);
    }

    // need to sleep for passing by the sending pulses
    // usleep(ADC_START_DELAY_US * 2);

    /* Start the acquisition */
    if (rp_AcqStart() != RP_OK) {
        fprintf(stderr, "rp_AcqStart failed!\n");
        return -1;
    }
    printf("ACQ Started\n");

    /* Specify trigger source */
    rp_AcqSetTriggerSrc(RP_TRIG_SRC_CHA_PE);
    rp_acq_trig_state_t state = RP_TRIG_STATE_TRIGGERED;

    /* Wait for the triggering moment */
    while(1){
        rp_AcqGetTriggerState(&state);
        if(state == RP_TRIG_STATE_TRIGGERED){
            sleep(1);
            break;
        }
    }

    /* Wait until buffer is full/data is acquired */
    bool fillState = false;
    while (!fillState) {
        if (rp_AcqAxiGetBufferFillState(RP_CH_1, &fillState) != RP_OK) {
            fprintf(stderr, "rp_AcqAxiGetBufferFillState RP_CH_1 failed!\n");
            return -1;
        }
    }

    /* Stop the acquisition */
    rp_AcqStop();
    printf("Stop acq\n");
}


/*
*@brief     This is the function to read acquired data 
*           and send through the udp connection
*               
*@details   This function reads the data from the memory
*           and sends in a bluk to PC
*
*/
void read_and_send_data(int udp_socket){
    /* Get write pointer on the triggering location */
    uint32_t posChA;
    rp_AcqAxiGetWritePointerAtTrig(RP_CH_1, &posChA);

    /* Allocate memory for the data */
    int16_t *buff1 = (int16_t *)malloc(READ_DATA_SIZE * sizeof(int16_t));

    int read_size = 0;

    /* Writing data into a text file */
    //FILE *fp = fopen ("out.txt", "w");

    int line = 1;
    while (read_size < DATA_SIZE){
        uint32_t size1 = READ_DATA_SIZE;

        rp_AcqAxiGetDataRaw(RP_CH_1, posChA, &size1, buff1);

        for (int i = 0; i < READ_DATA_SIZE; i++) {
            //fprintf(fp,"%d:  %d\n",line++, buff1[i]);
            sendto(udp.socket, &buff1[i], sizeof(buff1[i]), 0,
                   (struct sockaddr*)&udp.serveraddr, sizeof(udp.serveraddr));
            
        }
	
        posChA += size1;
        read_size += READ_DATA_SIZE;
        //printf("Saved data size %d\n", read_size);
	    printf("Sent chunk %d to %s:%d\n", read_size, UDP_IP, UDP_PORT);
        usleep(100000);
    }
    free(buff1);
    // fclose(fp);
}


/*
*@brief     This is the function to release redpitaya memories 
*               
*@details   This function releases the redpitaya channel,
*           closes the udp socket, frees the memory and
*           release redpitaya initiation
*
*
*/
void release_resources(){

    /* Releasing resources */
    rp_AcqAxiEnable(RP_CH_1, false);
    //Close the udp_socket
    close(udp.socket);

    rp_Release();

    //fclose(fp);
}