""" Commands for Midea appliance """
from __future__ import annotations

from midea_beautiful_dehumidifier.midea import MideaCommand
from midea_beautiful_dehumidifier.crypto import crc8

import logging

_LOGGER = logging.getLogger(__name__)

_order = 0


class DehumidifierStatusCommand(MideaCommand):
    def __init__(self):
        # Command structure
        self.data = bytearray(
            [
                # 0 header
                0xAA,
                # 1 command lenght: N+10
                0x20,
                # 2 appliance type 0xAC - airconditioning, 0xA1 - dehumidifier
                0xA1,
                # 3 Frame SYN CheckSum
                0x00,
                # 4-5 Reserved
                0x00,
                0x00,
                # 6 Message ID
                0x00,
                # 7 Frame Protocol Version
                0x00,
                # 8 Device Protocol Version
                0x03,
                # 9 Message Type: querying is 0x03; setting is 0x02
                0x03,
                # Byte0 - Data request/response type:
                # 0x41 - check status;
                # 0x40 - Set up
                0x41,
                # Byte1
                0x81,
                # Byte2 - operational_mode
                0x00,
                # Byte3
                0xFF,
                # Byte4
                0x03,
                # Byte5
                0xFF,
                # Byte6
                0x00,
                # Byte7 - Room Temperature Request:
                # 0x02 - indoor_temperature,
                # 0x03 - outdoor_temperature
                # when set, this is swing_mode
                0x02,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                # Message ID
                0x00,
                # CRC8
                0x00,
                # Checksum
                0x00,
            ]
        )

    def finalize(self) -> bytes:
        global _order
        _order = (_order + 1) & 0xFF
        self.data[30] = _order
        # Add the CRC8
        self.data[31] = crc8(self.data[10:31])
        # Add checksum
        self.data[32] = (~sum(self.data[1:32]) + 1) & 0xFF

        return bytes(self.data)


class DehumidifierSetCommand(MideaCommand):
    def __init__(self: DehumidifierSetCommand):
        self.data = bytearray(
            [
                0xAA,
                # Length
                0x20,
                # Dehumidifier
                0xA1,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x03,
                # Message Type: querying is 0x03; setting is 0x02
                0x02,
                # Payload
                # Data request/response type:
                # 0x41 - check status
                # 0x48 - write
                0x48,
                # Flags: On bit0 (byte 11)
                0x00,
                # Mode (byte 12)
                0x01,
                # Fan (byte 13)
                0x32,
                0x00,
                0x00,
                0x00,
                # Humidity (byte 17)
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
            ]
        )

    def finalize(self: DehumidifierSetCommand) -> bytes:
        global _order
        _order = (_order + 1) & 0xFF
        # Add the CRC8
        self.data[30] = _order
        # Add the CRC8
        self.data[31] = crc8(self.data[10:31])
        # Add checksum
        self.data[32] = (~sum(self.data[1:32]) + 1) & 0xFF
        # Set the length of the command data
        return bytes(self.data)

    @property
    def is_on(self):
        return self.data[11] & 0x01 != 0

    @is_on.setter
    def is_on(self, state: bool):
        self.data[11] &= ~0x01  # Clear the power bit
        self.data[11] |= 0x01 if state else 0

    @property
    def ion_mode(self) -> bool:
        return self.data[19] & 0x60 != 0

    @ion_mode.setter
    def ion_mode(self, mode: bool):
        self.data[19] &= ~0x60  # Clear the power bit
        self.data[19] |= 0x60 if mode else 0

    @property
    def target_humidity(self):
        return self.data[17] & 0x7F

    @target_humidity.setter
    def target_humidity(self, humidity: int):
        self.data[17] &= ~0x7F  # Clear the power bit
        self.data[17] |= humidity

    @property
    def mode(self):
        return self.data[12] & 0x0F

    @mode.setter
    def mode(self, mode: int):
        self.data[12] &= ~0x0F  # Clear the power bit
        self.data[12] |= mode

    @property
    def fan_speed(self):
        return self.data[13] & 0x7F

    @fan_speed.setter
    def fan_speed(self, speed: int):
        self.data[13] &= ~0x7F  # Clear the power bit
        self.data[13] |= speed


class DehumidifierResponse:
    def __init__(self: DehumidifierResponse, data: bytes):

        # self.faultFlag = (data[1] & 0x80) >> 7

        self._is_on = data[0x04] & 1 != 0

        # self.quickChkSts = (data[1] & 32) >> 5
        # self.mode_FC_return = (data[2] & 240) >> 4
        self._mode = data[0x02] & 15
        self._fan_speed = data[0x03] & 0x7F
        self.on_timer_value = data[0x04]
        self.on_timer_minutes = data[0x06]
        self.off_timer_value = data[0x05]
        self.off_timer_minutes = data[0x06]

        self._target_humidity = data[0x07]
        if self._target_humidity > 100:
            self._target_humidity = 99

        # self.humidity_set_dot = data[8] & 15
        # self.mode_FD_return = data[10] & 7
        # self.filterShow = (data[9] & 0x80) >> 7
        self._ion_mode = (data[0x09] & 64) >> 6 != 0
        # self.sleepSwitch = (data[9] & 32) >> 5
        # self.pumpSwitch_flag = (data[9] & 16) >> 4
        # self.pumpSwitch = (data[9] & 8) >> 3
        # self.displayClass = data[9] & 7
        # self.defrostingShow = (data[10] & 0x80) >> 7
        self._tank_full = data[0x0A] & 0x7F >= 100
        # self.dustTimeShow = data[11] * 2
        # self.rareShow = (data[12] & 56) >> 3
        # self.dustShow = data[12] & 7
        # self.pmLowValue = data[13]
        # self.pmHighValue = data[14]
        # self.rareValue = data[15]
        self._current_humidity = data[0x10]

        # self.indoorTmp = data[17]
        # self.humidity_cur_dot = data[18] & 240
        # self.indoorTmpT1_dot = (data[18] & 15) >> 4
        # self.lightClass = data[19] & 240
        # self.upanddownSwing = data[19]
        # self.leftandrightSwing = (data[19] & 32) >> 4
        # self.lightValue = data[20]
        self._err_code = data[0x15]
        for i in range(len(data)):
            _LOGGER.debug("%2d %2x %3d", i, data[i], data[i])

    @property
    def is_on(self):
        return self._is_on

    @property
    def fan_speed(self):
        return self._fan_speed

    @property
    def mode(self):
        return self._mode

    @property
    def tank_full(self):
        return self._tank_full

    @property
    def ion_mode(self):
        return self._ion_mode

    @property
    def current_humidity(self):
        return self._current_humidity

    @property
    def target_humidity(self):
        return self._target_humidity

    @property
    def err_code(self):
        return self._err_code

    # Byte 0x04 + 0x06
    @property
    def on_timer(self):
        return {
            "status": (self.on_timer_value & 0x80) != 0,
            "set": self.on_timer_value != 0x7F,
            "hour": (
                (self.on_timer_value & 0x7C) >> 2
                if self.on_timer_value != 0x7F
                else 0
            ),
            "minutes": (
                (self.on_timer_value & 0x3)
                | (
                    ((self.on_timer_minutes & 0xF0) >> 4)
                    if self.on_timer_value != 0x7F
                    else 0
                )
            ),
            "on_timer_value": self.on_timer_value,
            "on_timer_minutes": self.on_timer_minutes,
        }

    # Byte 0x05 + 0x06
    @property
    def off_timer(self):
        return {
            "status": (self.off_timer_value & 0x80) != 0,
            "set": self.off_timer_value != 0x7F,
            "hour": (self.off_timer_value & 0x7C) >> 2,
            "minutes": (
                (self.off_timer_value & 0x3) | (self.off_timer_minutes & 0xF)
            ),
            "off_timer_value": self.off_timer_value,
            "off_timer_minutes": self.off_timer_minutes,
        }

    def __str__(self):
        return str(self.__dict__)
