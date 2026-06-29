#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "TinyFrame.h"

#ifdef _WIN32
    #define EXPORT __declspec(dllexport)
    #include <windows.h>
#else
    #define EXPORT __attribute__((visibility("default")))
    #include <termios.h>
    #include <fcntl.h>
    #include <unistd.h>
    #include <errno.h>
#endif

// Global TinyFrame instance
static TinyFrame *tf = NULL;

// COM port handle
#ifdef _WIN32
    static HANDLE comHandle = INVALID_HANDLE_VALUE;
#else
    static int comHandle = -1;
#endif

// Python callback function pointers
typedef void (*PyListenerCallback)(uint8_t type, const uint8_t *data, uint32_t len, uint16_t frame_id);
static PyListenerCallback *type_callbacks = NULL;
static int max_type_id = 0;

// Forward declarations
static TF_Result generic_type_listener(TinyFrame *tf, TF_Msg *msg);
static void com_write_callback(const uint8_t *buff, uint32_t len);

// Initialize TinyFrame and set up callbacks
EXPORT bool tf_init(int max_types) {
    // Initialize TinyFrame if not already initialized
    if (tf == NULL) {
        tf = TF_Init(TF_MASTER);
        if (tf == NULL) {
            printf("Failed to initialize TinyFrame\n");
            return false;
        }
    }
    
    // Set up the write callback
    TF_SetWriteCallback(com_write_callback);
    
    // Allocate callback array for type listeners
    if (type_callbacks != NULL) {
        free(type_callbacks);
    }
    
    max_type_id = max_types;
    type_callbacks = (PyListenerCallback*)calloc(max_types, sizeof(PyListenerCallback));
    if (type_callbacks == NULL) {
        printf("Failed to allocate callback array\n");
        return false;
    }
    
    return true;
}

// Open COM port
EXPORT bool tf_open_port(const char *port_name, int baud_rate) {
#ifdef _WIN32
    char full_port_name[20];
    DCB dcb = {0};
    COMMTIMEOUTS timeouts = {0};
    
    // Close if already open
    if (comHandle != INVALID_HANDLE_VALUE) {
        CloseHandle(comHandle);
        comHandle = INVALID_HANDLE_VALUE;
    }
    
    // Prepend \\.\ if not already present (required for COM10 and above on Windows)
    if (strncmp(port_name, "\\\\.\\", 4) == 0) {
        snprintf(full_port_name, sizeof(full_port_name), "%s", port_name);
    } else {
        snprintf(full_port_name, sizeof(full_port_name), "\\\\.\\%s", port_name);
    }
    
    // Open the port
    comHandle = CreateFileA(
        full_port_name, 
        GENERIC_READ | GENERIC_WRITE,
        0,                          // No sharing
        NULL,                       // No security
        OPEN_EXISTING,              // Open existing port only
        0,                          // Non-overlapped I/O
        NULL                        // Null for comm devices
    );
    
    if (comHandle == INVALID_HANDLE_VALUE) {
        printf("Failed to open COM port %s, error: %lu\n", port_name, GetLastError());
        return false;
    }
    
    // Set up DCB structure
    dcb.DCBlength = sizeof(DCB);
    if (!GetCommState(comHandle, &dcb)) {
        printf("GetCommState failed, error: %lu\n", GetLastError());
        CloseHandle(comHandle);
        comHandle = INVALID_HANDLE_VALUE;
        return false;
    }
    
    // Configure serial parameters
    dcb.BaudRate = baud_rate;
    dcb.ByteSize = 8;
    dcb.Parity = NOPARITY;
    dcb.StopBits = ONESTOPBIT;
    dcb.fDtrControl = DTR_CONTROL_ENABLE;  // Enable DTR
    
    if (!SetCommState(comHandle, &dcb)) {
        printf("SetCommState failed, error: %lu\n", GetLastError());
        CloseHandle(comHandle);
        comHandle = INVALID_HANDLE_VALUE;
        return false;
    }
    
    // Set timeouts
    timeouts.ReadIntervalTimeout = 50;
    timeouts.ReadTotalTimeoutConstant = 50;
    timeouts.ReadTotalTimeoutMultiplier = 10;
    timeouts.WriteTotalTimeoutConstant = 50;
    timeouts.WriteTotalTimeoutMultiplier = 10;
    
    if (!SetCommTimeouts(comHandle, &timeouts)) {
        printf("SetCommTimeouts failed, error: %lu\n", GetLastError());
        CloseHandle(comHandle);
        comHandle = INVALID_HANDLE_VALUE;
        return false;
    }

#else
    // Linux implementation
    struct termios tty;
    
    // Close if already open
    if (comHandle >= 0) {
        close(comHandle);
        comHandle = -1;
    }
    
    // Open the port
    comHandle = open(port_name, O_RDWR | O_NOCTTY | O_SYNC);
    if (comHandle < 0) {
        printf("Error opening %s: %s\n", port_name, strerror(errno));
        return false;
    }
    
    // Get current port attributes
    if (tcgetattr(comHandle, &tty) != 0) {
        printf("Error from tcgetattr: %s\n", strerror(errno));
        close(comHandle);
        comHandle = -1;
        return false;
    }
    
    // Set baud rate
    speed_t speed;
    switch (baud_rate) {
        case 9600: speed = B9600; break;
        case 19200: speed = B19200; break;
        case 38400: speed = B38400; break;
        case 57600: speed = B57600; break;
        case 115200: speed = B115200; break;
        default:
            printf("Unsupported baud rate: %d\n", baud_rate);
            close(comHandle);
            comHandle = -1;
            return false;
    }
    
    cfsetospeed(&tty, speed);
    cfsetispeed(&tty, speed);
    
    // 8N1, no flow control
    tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8;  // 8-bit chars
    tty.c_iflag &= ~IGNBRK;         // Disable break processing
    tty.c_lflag = 0;                // No signaling chars, no echo, no canonical processing
    tty.c_oflag = 0;                // No remapping, no delays
    tty.c_cc[VMIN]  = 0;            // Read doesn't block
    tty.c_cc[VTIME] = 5;            // 0.5 seconds read timeout
    
    tty.c_iflag &= ~(IXON | IXOFF | IXANY); // Turn off s/w flow ctrl
    tty.c_cflag |= (CLOCAL | CREAD);       // Ignore modem controls, enable reading
    tty.c_cflag &= ~(PARENB | PARODD);     // No parity
    tty.c_cflag &= ~CSTOPB;                // 1 stop bit
    tty.c_cflag &= ~CRTSCTS;               // No hardware flowcontrol
    
    // Apply new settings
    if (tcsetattr(comHandle, TCSANOW, &tty) != 0) {
        printf("Error from tcsetattr: %s\n", strerror(errno));
        close(comHandle);
        comHandle = -1;
        return false;
    }
#endif
    
    printf("Successfully opened port %s at %d baud\n", port_name, baud_rate);
    return true;
}

// Close COM port
EXPORT void tf_close_port() {
#ifdef _WIN32
    if (comHandle != INVALID_HANDLE_VALUE) {
        CloseHandle(comHandle);
        comHandle = INVALID_HANDLE_VALUE;
    }
#else
    if (comHandle >= 0) {
        close(comHandle);
        comHandle = -1;
    }
#endif
}

// Callback function for TinyFrame to write data
static void com_write_callback(const uint8_t *buff, uint32_t len) {
#ifdef _WIN32
    if (comHandle != INVALID_HANDLE_VALUE) {
        DWORD written;
        if (!WriteFile(comHandle, buff, len, &written, NULL)) {
            printf("WriteFile failed, error: %lu\n", GetLastError());
        } else if (written != len) {
            printf("WriteFile: only wrote %lu of %u bytes\n", written, len);
        }
    }
#else
    if (comHandle >= 0) {
        ssize_t written = write(comHandle, buff, len);
        if (written < 0) {
            printf("Write failed: %s\n", strerror(errno));
        } else if ((size_t)written != len) {
            printf("Only wrote %zd of %u bytes\n", written, len);
        }
    }
#endif
    else {
        printf("COM port not open for writing\n");
    }
}

// Register a listener for a specific message type
EXPORT bool tf_register_listener(uint8_t type, PyListenerCallback callback) {
    if (tf == NULL) {
        printf("TinyFrame not initialized\n");
        return false;
    }
    
    if (type >= max_type_id) {
        printf("Type ID %d is out of range (max: %d)\n", type, max_type_id - 1);
        return false;
    }
    
    // Store the Python callback
    type_callbacks[type] = callback;
    
    // Register a generic listener for this type in TinyFrame
    return TF_AddTypeListener(tf, type, generic_type_listener);
}

// Generic type listener that forwards to appropriate Python callback
static TF_Result generic_type_listener(TinyFrame *tf, TF_Msg *msg) {
    uint8_t type = msg->type;
    
    if (type < max_type_id && type_callbacks[type] != NULL) {
        // Call the Python callback
        type_callbacks[type](type, msg->data, msg->len, msg->frame_id);
        return TF_STAY; // Keep the listener
    }
    
    return TF_NEXT; // No callback or invalid type, let others handle it
}

// Send a frame
EXPORT bool tf_send(uint8_t type, const uint8_t *data, uint32_t len) {
    if (tf == NULL) {
        printf("TinyFrame not initialized\n");
        return false;
    }
    
    return TF_SendSimple(tf, type, data, len);
}

// Process received data through TinyFrame
EXPORT void tf_accept(const uint8_t *data, uint32_t len) {
    if (tf == NULL) {
        printf("TinyFrame not initialized\n");
        return;
    }
    
    TF_Accept(tf, data, len);
}

// Read available data from COM port and process it
EXPORT int tf_read_and_process() {
    uint8_t buffer[256];
    int bytes_read = 0;
    
#ifdef _WIN32
    if (comHandle != INVALID_HANDLE_VALUE) {
        DWORD bytes;
        if (ReadFile(comHandle, buffer, sizeof(buffer), &bytes, NULL)) {
            if (bytes > 0) {
                TF_Accept(tf, buffer, bytes);
                bytes_read = bytes;
            }
        } else {
            printf("ReadFile failed, error: %lu\n", GetLastError());
        }
    }
#else
    if (comHandle >= 0) {
        ssize_t bytes = read(comHandle, buffer, sizeof(buffer));
        if (bytes > 0) {
            TF_Accept(tf, buffer, bytes);
            bytes_read = bytes;
        } else if (bytes < 0) {
            printf("Read failed: %s\n", strerror(errno));
        }
    }
#endif
    else {
        printf("COM port not open for reading\n");
    }
    
    return bytes_read;
}

// Cleanup resources
EXPORT void tf_cleanup() {
    tf_close_port();
    
    if (type_callbacks != NULL) {
        free(type_callbacks);
        type_callbacks = NULL;
    }
    
    if (tf != NULL) {
        TF_DeInit(tf);
        tf = NULL;
    }
}

// Helper function to get a list of available COM ports
// This is platform-dependent and should be handled by Python using pyserial