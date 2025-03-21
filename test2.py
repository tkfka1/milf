# 키마 세팅 클래스
import struct
import time

import serial
import win32api
import threading
import serial.tools.list_ports


class Keymouse():
    # Mouse basic commands and arguments
    MOUSE_CMD = 0xE0
    MOUSE_CALIBRATE = 0xE1
    MOUSE_PRESS = 0xE2
    MOUSE_RELEASE = 0xE3

    MOUSE_CLICK = 0xE4
    MOUSE_FAST_CLICK = 0xE5
    MOUSE_MOVE = 0xE6
    MOUSE_BEZIER = 0xE7

    # Mouse buttons
    MOUSE_LEFT = 0xEA
    MOUSE_RIGHT = 0xEB
    MOUSE_MIDDLE = 0xEC
    MOUSE_BUTTONS = [MOUSE_LEFT,
                     MOUSE_MIDDLE,
                     MOUSE_RIGHT]

    # Keyboard commands and arguments
    KEYBOARD_CMD = 0xF0
    KEYBOARD_PRESS = 0xF1
    KEYBOARD_RELEASE = 0xF2
    KEYBOARD_RELEASE_ALL = 0xF3
    KEYBOARD_PRINT = 0xF4
    KEYBOARD_PRINTLN = 0xF5
    KEYBOARD_WRITE = 0xF6
    KEYBOARD_TYPE = 0xF7

    # Arduino keyboard modifiers
    # http://arduino.cc/en/Reference/KeyboardModifiers
    LEFT_CTRL = 0x80
    LEFT_SHIFT = 0x81
    LEFT_ALT = 0x82
    LEFT_GUI = 0x83
    RIGHT_CTRL = 0x84
    RIGHT_SHIFT = 0x85
    RIGHT_ALT = 0x86
    RIGHT_GUI = 0x87
    UP_ARROW = 0xDA
    DOWN_ARROW = 0xD9
    LEFT_ARROW = 0xD8
    RIGHT_ARROW = 0xD7
    BACKSPACE = 0xB2
    TAB = 0xB3
    RETURN = 0xB0
    ESC = 0xB1
    INSERT = 0xD1
    DELETE = 0xD4
    PAGE_UP = 0xD3
    PAGE_DOWN = 0xD6
    HOME = 0xD2
    END = 0xD5
    CAPS_LOCK = 0xC1
    F1 = 0xC2
    F2 = 0xC3
    F3 = 0xC4
    F4 = 0xC5
    F5 = 0xC6
    F6 = 0xC7
    F7 = 0xC8
    F8 = 0xC9
    F9 = 0xCA
    F10 = 0xCB
    F11 = 0xCC
    F12 = 0xCD

    # etc.
    SCREEN_CALIBRATE = 0xFF
    COMMAND_COMPLETE = 0xFE


# 아두이노 제어 클래스

class Arduino(object):
    def __init__(self, port=None, baudrate=115200):
        """
		Args:
		  port (str, optional): Device name or port number number or None.
		  baudrate (str, optional): Baud rate such as 9600 or 115200 etc.

		Raises:
		  SerialException: In the case the device cannot be found.

		Note:
		  You should not have to specify any arguments when instantiating
		  this class. The default parameters should work out of the box.

		  However, if the constructor is unable to automatically identify
		  the Arduino device, a port name should be explicitly specified.

		  If you specify a baud rate other than the default 115200 baud, you
		  must modify the arduino sketch to match the specified baud rate.
		"""

        if port is None:
            port = self.__detect_port()

        self.serial = serial.Serial(port, baudrate)
        if not self.serial.isOpen():
            raise serial.SerialException("Arduino device not found.")

        # this flag denoting whether a command is has been completed
        # all module calls are blocking until the Arduino command is complete
        self.__command_complete = threading.Event()

        # read and parse bytes from the serial buffer
        serial_reader = threading.Thread(target=self.__read_buffer)
        serial_reader.daemon = True
        serial_reader.start()

    def press(self, button=Keymouse.MOUSE_LEFT):
        if button in Keymouse.MOUSE_BUTTONS:
            self.__write_byte(Keymouse.MOUSE_CMD)
            self.__write_byte(Keymouse.MOUSE_PRESS)
            self.__write_byte(button)

        elif isinstance(button, int):
            self.__write_byte(Keymouse.KEYBOARD_CMD)
            self.__write_byte(Keymouse.KEYBOARD_PRESS)
            self.__write_byte(button)

        elif isinstance(button, str) and len(button) == 1:
            self.__write_byte(Keymouse.KEYBOARD_CMD)
            self.__write_byte(Keymouse.KEYBOARD_PRESS)
            self.__write_byte(ord(button))

        else:
            raise ValueError("Not a valid mouse or keyboard button.")

        self.__command_complete.wait()

    def release(self, button=Keymouse.MOUSE_LEFT):
        if button in Keymouse.MOUSE_BUTTONS:
            self.__write_byte(Keymouse.MOUSE_CMD)
            self.__write_byte(Keymouse.MOUSE_RELEASE)
            self.__write_byte(button)

        elif isinstance(button, int):
            self.__write_byte(Keymouse.KEYBOARD_CMD)
            self.__write_byte(Keymouse.KEYBOARD_RELEASE)
            self.__write_byte(button)

        elif isinstance(button, str) and len(button) == 1:
            self.__write_byte(Keymouse.KEYBOARD_CMD)
            self.__write_byte(Keymouse.KEYBOARD_RELEASE)
            self.__write_byte(ord(button))

        else:
            raise ValueError("Not a valid mouse or keyboard button.")

        self.__command_complete.wait()

    def release_all(self):
        self.__write_byte(Keymouse.KEYBOARD_CMD)
        self.__write_byte(Keymouse.KEYBOARD_RELEASE_ALL)

        self.__command_complete.wait()

    def write(self, keys, endl=False):
        if isinstance(keys, int):
            self.__write_byte(Keymouse.KEYBOARD_CMD)
            self.__write_byte(Keymouse.KEYBOARD_WRITE)
            self.__write_byte(keys)

        elif isinstance(keys, str) and len(keys) == 1:
            self.__write_byte(Keymouse.KEYBOARD_CMD)
            self.__write_byte(Keymouse.KEYBOARD_WRITE)
            self.__write_byte(ord(keys))

        elif isinstance(keys, str):
            if not endl:
                self.__write_byte(Keymouse.KEYBOARD_CMD)
                self.__write_byte(Keymouse.KEYBOARD_PRINT)
                self.__write_str(keys)
            else:
                self.__write_byte(Keymouse.KEYBOARD_CMD)
                self.__write_byte(Keymouse.KEYBOARD_PRINTLN)
                self.__write_str(keys)

        else:
            raise ValueError(
                "Not a valid keyboard keystroke. "
                + "Must be type `int` or `char` or `str`."
            )

        self.__command_complete.wait()

    def type(self, message, wpm=80, mistakes=True, accuracy=96):
        if not isinstance(message, str):
            raise ValueError("Invalid keyboard message. " + "Must be type `str`.")

        if not isinstance(wpm, int) and wpm < 1 or wpm > 255:
            raise ValueError(
                "Invalid value for `WPM`. " + "Must be type `int`: 1 <= WPM <= 255."
            )

        if not isinstance(mistakes, bool):
            raise ValueError("Invalid value for `mistakes`. " + "Must be type `bool`.")

        if not isinstance(accuracy, int) and accuracy < 1 or accuracy > 100:
            raise ValueError(
                "Invalid value for `accuracy`. "
                + "Must be type `int`: 1 <= accuracy <= 100."
            )

        self.__write_byte(Keymouse.KEYBOARD_CMD)
        self.__write_byte(Keymouse.KEYBOARD_TYPE)
        self.__write_str(message)
        self.__write_byte(wpm)
        self.__write_byte(mistakes)
        self.__write_byte(accuracy)

        self.__command_complete.wait()

    def click(self, button=Keymouse.MOUSE_LEFT):
        if button not in Keymouse.MOUSE_BUTTONS:
            raise ValueError("Not a valid mouse button.")

        self.__write_byte(Keymouse.MOUSE_CMD)
        self.__write_byte(Keymouse.MOUSE_CLICK)
        self.__write_byte(button)

        self.__command_complete.wait()

    def fast_click(self, button):
        if button not in Keymouse.MOUSE_BUTTONS:
            raise ValueError("Not a valid mouse button.")

        self.__write_byte(Keymouse.MOUSE_CMD)
        self.__write_byte(Keymouse.MOUSE_FAST_CLICK)
        self.__write_byte(button)

        self.__command_complete.wait()

    def move(self, dest_x, dest_y):
        if not isinstance(dest_x, (int, float)) and not isinstance(
                dest_y, (int, float)
        ):
            raise ValueError(
                "Invalid mouse coordinates. " + "Must be type `int` or `float`."
            )

        self.__write_byte(Keymouse.MOUSE_CMD)
        self.__write_byte(Keymouse.MOUSE_MOVE)
        self.__write_short(dest_x)
        self.__write_short(dest_y)

        self.__command_complete.wait()

    def bezier_move(self, dest_x, dest_y):
        if not isinstance(dest_x, (int, float)) and not isinstance(
                dest_y, (int, float)
        ):
            raise ValueError(
                "Invalid mouse coordinates. " + "Must be `int` or `float`."
            )

        self.__write_byte(Keymouse.MOUSE_CMD)
        self.__write_byte(Keymouse.MOUSE_BEZIER)
        self.__write_short(dest_x)
        self.__write_short(dest_y)

        self.__command_complete.wait()

    def close(self):
        self.serial.close()
        return True

    def __detect_port(self):
        ports = serial.tools.list_ports.comports()
        arduino_port = None

        for port in ports:
            if "Arduino" in port[1]:
                arduino_port = port[0]

        return arduino_port

    def __read_buffer(self):
        while True:
            byte = ord(self.serial.read())

            if byte == Keymouse.MOUSE_CALIBRATE:
                self.__calibrate_mouse()

            elif byte == Keymouse.SCREEN_CALIBRATE:
                self.__calibrate_screen()

            elif byte == Keymouse.COMMAND_COMPLETE:
                self.__command_complete.set()
                self.__command_complete.clear()

    def __calibrate_screen(self):
        width, height = win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)

        self.__write_short(width)
        self.__write_short(height)

    def __calibrate_mouse(self):
        x, y = win32api.GetCursorPos()

        self.__write_short(x)
        self.__write_short(y)

    def __write_str(self, string):
        for char in string:
            self.__write_byte(ord(char))
        self.__write_byte(0x00)

    def __write_byte(self, byte):
        struct_pack = struct.pack("<B", byte)
        self.serial.write(struct_pack)

    def __write_short(self, short):
        struct_pack = struct.pack("<H", int(short))
        self.serial.write(struct_pack)



ardu = Arduino()

def ardui():
    global ardu
    print("sad")
    ardu.press(Keymouse.RIGHT_ARROW)


ardui()
time.sleep(3)
ardui()
time.sleep(0.1)
ardui()
time.sleep(0.1)
ardui()
ardui()
ardui()
ardui()
ardui()
i = 0
while True:
    if i == 15:
        ardu.release_all()
        break
    i += 1
    time.sleep(1)
    ardui()

print("sad")
time.sleep(3)
ardu.release_all()