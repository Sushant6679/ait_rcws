#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>

#ifdef _WIN32
    #include <windows.h>
    typedef HANDLE SerialHandle;
#else
    #include <unistd.h>
    #include <fcntl.h>
    #include <termios.h>
    #include <errno.h>
    typedef int SerialHandle;
#endif

#include "TinyFrame.h"

// Global variables
SerialHandle serial_handle = -1;
TinyFrame *tf = NULL;

// Forward declarations
void TF_WriteImpl(TinyFrame *tf, const uint8_t *buff, uint32_t len);

/**
 * Open serial port
 * 
 * @param port_name COM port name (e.g., "COM1" on Windows, "/dev/ttyUSB0" on Linux)
 * @param baud_rate Baud rate (e.g., 9600, 115200)
 * @return true if successful, false otherwise
 */
bool serial_open(const char *port_name, int baud_rate) 
{
    if (serial_handle != -1) {
        printf("Serial port already open\n");
        return false;
    }

#ifdef _WIN32
    // Windows implementation
    char full_path[32] = {0};
    snprintf(full_path, sizeof(full_path), "\\\\.\\%s", port_name);
    
    serial_handle = CreateFileA(
        full_path,
        GENERIC_READ | GENERIC_WRITE,
        0,
        NULL,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        NULL
    );
    
    if (serial_handle == INVALID_HANDLE_VALUE) {
        printf("Failed to open port %s. Error: %lu\n", port_name, GetLastError());
        serial_handle = -1;
        return false;
    }
    
    DCB dcb = {0};
    dcb.DCBlength = sizeof(DCB);
    if (!GetCommState(serial_handle, &dcb)) {
        printf("Failed to get comm state. Error: %lu\n", GetLastError());
        CloseHandle(serial_handle);
        serial_handle = -1;
        return false;
    }
    
    dcb.BaudRate = baud_rate;
    dcb.ByteSize = 8;
    dcb.Parity = NOPARITY;
    dcb.StopBits = ONESTOPBIT;
    
    if (!SetCommState(serial_handle, &dcb)) {
        printf("Failed to set comm state. Error: %lu\n", GetLastError());
        CloseHandle(serial_handle);
        serial_handle = -1;
        return false;
    }
    
    COMMTIMEOUTS timeouts = {0};
    timeouts.ReadIntervalTimeout = 50;
    timeouts.ReadTotalTimeoutConstant = 50;
    timeouts.ReadTotalTimeoutMultiplier = 10;
    timeouts.WriteTotalTimeoutConstant = 50;
    timeouts.WriteTotalTimeoutMultiplier = 10;
    
    if (!SetCommTimeouts(serial_handle, &timeouts)) {
        printf("Failed to set comm timeouts. Error: %lu\n", GetLastError());
        CloseHandle(serial_handle);
        serial_handle = -1;
        return false;
    }
#else
    // Linux/Unix implementation
    serial_handle = open(port_name, O_RDWR | O_NOCTTY | O_NDELAY);
    if (serial_handle < 0) {
        printf("Failed to open port %s. Error: %d (%s)\n", port_name, errno, strerror(errno));
        serial_handle = -1;
        return false;
    }
    
    struct termios options;
    tcgetattr(serial_handle, &options);
    
    // Set baud rate
    speed_t baud;
    switch (baud_rate) {
        case 9600:   baud = B9600;   break;
        case 19200:  baud = B19200;  break;
        case 38400:  baud = B38400;  break;
        case 57600:  baud = B57600;  break;
        case 115200: baud = B115200; break;
        default:
            printf("Unsupported baud rate: %d\n", baud_rate);
            close(serial_handle);
            serial_handle = -1;
            return false;
    }
    
    cfsetispeed(&options, baud);
    cfsetospeed(&options, baud);
    
    // 8N1
    options.c_cflag &= ~PARENB;
    options.c_cflag &= ~CSTOPB;
    options.c_cflag &= ~CSIZE;
    options.c_cflag |= CS8;
    
    // No flow control
    options.c_cflag &= ~CRTSCTS;
    
    // Set up for non-canonical mode
    options.c_iflag &= ~(IGNBRK | BRKINT | PARMRK | ISTRIP | INLCR | IGNCR | ICRNL | IXON);
    options.c_lflag &= ~(ECHO | ECHONL | ICANON | ISIG | IEXTEN);
    options.c_oflag &= ~OPOST;
    
    // Fetch bytes as they become available
    options.c_cc[VMIN] = 0;
    options.c_cc[VTIME] = 1;
    
    tcsetattr(serial_handle, TCSANOW, &options);
#endif
    
    printf("Serial port %s opened successfully\n", port_name);
    return true;
}

/**
 * Close serial port
 */
void serial_close() 
{
    if (serial_handle != -1) {
#ifdef _WIN32
        CloseHandle(serial_handle);
#else
        close(serial_handle);
#endif
        serial_handle = -1;
        printf("Serial port closed\n");
    }
}

/**
 * Read data from serial port
 * 
 * @param buffer Buffer to read data into
 * @param max_len Maximum number of bytes to read
 * @return Number of bytes read, -1 on error
 */
int serial_read(uint8_t *buffer, size_t max_len) 
{
    if (serial_handle == -1) {
        return -1;
    }
    
#ifdef _WIN32
    DWORD bytes_read = 0;
    if (!ReadFile(serial_handle, buffer, max_len, &bytes_read, NULL)) {
        printf("Failed to read from serial port. Error: %lu\n", GetLastError());
        return -1;
    }
    return (int)bytes_read;
#else
    return (int)read(serial_handle, buffer, max_len);
#endif
}

/**
 * Implementation of TF_WriteImpl for serial communication
 */
void TF_WriteImpl(TinyFrame *tf, const uint8_t *buff, uint32_t len)
{
    if (serial_handle == -1) {
        printf("Serial port not open\n");
        return;
    }
    
#ifdef _WIN32
    DWORD bytes_written = 0;
    if (!WriteFile(serial_handle, buff, len, &bytes_written, NULL)) {
        printf("Failed to write to serial port. Error: %lu\n", GetLastError());
    }
#else
    ssize_t bytes_written = write(serial_handle, buff, len);
    if (bytes_written < 0) {
        printf("Failed to write to serial port. Error: %d (%s)\n", errno, strerror(errno));
    }
#endif
}

/**
 * Initialize TinyFrame for serial communication
 * 
 * @param peer Peer type (TF_MASTER or TF_SLAVE)
 * @return Pointer to TinyFrame instance, NULL on failure
 */
TinyFrame* tf_init(TF_Peer peer)
{
    if (tf != NULL) {
        // Already initialized
        return tf;
    }
    
    tf = TF_Init(peer);
    if (tf == NULL) {
        printf("Failed to initialize TinyFrame\n");
        return NULL;
    }
    
    return tf;
}

/**
 * Clean up TinyFrame
 */
void tf_cleanup()
{
    if (tf != NULL) {
        TF_DeInit(tf);
        tf = NULL;
    }
    serial_close();
}

/**
 * Read and process data from serial port
 * 
 * @return Number of bytes processed, -1 on error
 */
int tf_process()
{
    if (serial_handle == -1 || tf == NULL) {
        return -1;
    }
    
    uint8_t buffer[256];
    int bytes_read = serial_read(buffer, sizeof(buffer));
    
    if (bytes_read > 0) {
        TF_Accept(tf, buffer, bytes_read);
    }
    
    return bytes_read;
}

/**
 * Register a listener for a specific type ID
 * 
 * @param type_id Type ID to listen for
 * @param callback Callback function to call when a matching frame is received
 * @return ID of the registered listener, -1 on failure
 */
int tf_register_type(uint8_t type_id, TF_Listener callback)
{
    if (tf == NULL) {
        return -1;
    }
    
    return TF_AddTypeListener(tf, type_id, callback);
}

/**
 * Register a generic listener for all frames
 * 
 * @param callback Callback function to call for any frame
 * @return ID of the registered listener, -1 on failure
 */
int tf_register_generic(TF_Listener callback)
{
    if (tf == NULL) {
        return -1;
    }
    
    return TF_AddGenericListener(tf, callback);
}

/**
 * Remove a registered listener
 * 
 * @param id ID of the listener to remove
 * @return true if successful, false otherwise
 */
bool tf_remove_listener(int id)
{
    if (tf == NULL) {
        return false;
    }
    
    return TF_RemoveListener(tf, id);
}

/**
 * Send a frame
 * 
 * @param type_id Type ID of the frame
 * @param data Data to send
 * @param len Length of the data
 * @return true if successful, false otherwise
 */
bool tf_send(uint8_t type_id, const uint8_t *data, uint32_t len)
{
    if (tf == NULL) {
        return false;
    }
    
    return TF_Send(tf, type_id, data, len);
}

/**
 * Send a frame and wait for a response
 * 
 * @param type_id Type ID of the frame
 * @param data Data to send
 * @param len Length of the data
 * @param timeout_ms Timeout in milliseconds
 * @param callback Callback function to call when a response is received
 * @return Frame ID if successful, 0 otherwise
 */
uint16_t tf_query(uint8_t type_id, const uint8_t *data, uint32_t len, uint32_t timeout_ms, TF_Listener callback)
{
    if (tf == NULL) {
        return 0;
    }
    
    return TF_Query(tf, type_id, data, len, timeout_ms, callback);
}

// Callback trampoline function - needed for Python callbacks
typedef struct {
    int type_id;
    void (*py_callback)(int, const uint8_t*, uint32_t);
} PyCallbackInfo;

static PyCallbackInfo *py_callbacks = NULL;
static int num_py_callbacks = 0;

static TF_Result trampoline_callback(TinyFrame *tf, TF_Msg *msg)
{
    for (int i = 0; i < num_py_callbacks; i++) {
        if (py_callbacks[i].type_id == msg->type || py_callbacks[i].type_id == -1) {
            py_callbacks[i].py_callback(msg->type, msg->data, msg->len);
        }
    }
    return TF_STAY;
}

/**
 * Register a Python callback for a specific type ID
 * 
 * @param type_id Type ID to listen for (-1 for all types)
 * @param callback Python callback function
 * @return ID of the registered callback, -1 on failure
 */
int tf_register_py_callback(int type_id, void (*callback)(int, const uint8_t*, uint32_t))
{
    // Expand the callbacks array
    PyCallbackInfo *new_callbacks = realloc(py_callbacks, (num_py_callbacks + 1) * sizeof(PyCallbackInfo));
    if (new_callbacks == NULL) {
        return -1;
    }
    py_callbacks = new_callbacks;
    
    // Store the callback
    py_callbacks[num_py_callbacks].type_id = type_id;
    py_callbacks[num_py_callbacks].py_callback = callback;
    
    // Register with TinyFrame
    int id;
    if (type_id == -1) {
        id = TF_AddGenericListener(tf, trampoline_callback);
    } else {
        id = TF_AddTypeListener(tf, type_id, trampoline_callback);
    }
    
    if (id >= 0) {
        num_py_callbacks++;
    }
    
    return id;
}