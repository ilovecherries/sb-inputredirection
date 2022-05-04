from enum import IntEnum
import socket
from struct import pack
from time import sleep
from queue import Queue
from threading import Thread

HOST = "[REDACTED]"
PORT = 4950
BUFFER_TIME = 0.2

def BIT(x):
	return 1 << x

class HidButtonCodes(IntEnum):
	"""
	https://github.com/Stary2001/InputClient-SDL/blob/5cff8ce431c55b40ff5e8710374402a04bb94b4e/src/main.c#L159
	"""
	A = BIT(0)
	B = BIT(1)
	SELECT = BIT(2)
	START = BIT(3)
	RIGHT = BIT(4)
	LEFT = BIT(5)
	UP = BIT(6)
	DOWN = BIT(7)
	R = BIT(8)
	L = BIT(9)
	X = BIT(10)
	Y = BIT(11)

class SpecialButtonCodes(IntEnum):
	"""
	https://github.com/Stary2001/InputClient-SDL/blob/5cff8ce431c55b40ff5e8710374402a04bb94b4e/src/main.c#L175
	"""
	HOME = 0
	POWER = 1
	POWER_LONG = 2

class NeutralValues(IntEnum):
	"""
	https://github.com/LumaTeam/Luma3DS/blob/3afecb064c03c26776e21aa54e30ec13e6674787/sysmodules/rosalina/source/input_redirection.c#L50
	"""
	# HID = 0x00000FFF
	HID = 0xfffff000
	TOUCH_SCREEN = 0x02000000
	CIRCLE_STICK = 0x007FF7FF
	CSTICK = 0x80800081

class ButtonMask:
	def __init__(self, enum: IntEnum):
		self.buttons = [False] * len(enum)
	
	def set_button(self, button: IntEnum, value: bool):
		self.buttons[button] = value
	
	def get_mask(self):
		mask = 0
		for i, v in enumerate(self.buttons):
			value = 1 if v else 0
			mask |= value << i
		return mask

class HidButtons():
	def __init__(self):
		self.reset()
	
	def set_button(self, button: HidButtonCodes, value: bool):
		if value:
			self.mask |= button
		else:
			self.mask &= ~button
	
	def reset(self):
		self.mask = NeutralValues.HID
	
	def get_mask(self):
		return (~self.mask) & 0xFFFFFFFF

class SpecialButtons(ButtonMask):
	def __init__(self):
		super().__init__(SpecialButtonCodes)

class TouchScreen:
	def __init__(self):
		self.reset()
	
	def reset(self):
		self.touching = False
		# range of 4096
		self.x = 0
		self.y = 0
	
	def get_mask(self):
		if self.touching:
			return self.x | (self.y << 12) | (0x01 << 24)
		else:
			return NeutralValues.TOUCH_SCREEN

class CircleStick:
	def __init__(self):
		self.x = 0
		self.y = 0
	
	def get_mask(self):
		if self.x != 0 or self.y != 0:
			return 0
		else:
			return NeutralValues.CIRCLE_STICK

class CStick:
	def __init__(self):
		self.x = 0
		self.y = 0
	
	def get_mask(self):
		if self.x != 0 or self.y != 0:
			return 0
		else:
			return NeutralValues.CSTICK

class Connection:
	def __init__(self, host: str):
		self.buttons = HidButtons()
		self.special_buttons = SpecialButtons()
		self.touch = TouchScreen()
		self.stick = CircleStick()
		self.cstick = CStick()
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.socket.connect((host, PORT))
		self.queue = Queue()
		def loop(q):
			while True:
				ev = q.get()
				print(ev)
				if ev["type"] == "clear_touch":
					self.touch.reset()
					self.send_buffer()
				elif ev["type"] == "touch":
					self.touch.reset()
					self.touch.x = ev["x"]
					self.touch.y = ev["y"]
					self.touch.touching = True
					self.send_buffer()
				if ev["type"] == "clear_button":
					sleep(BUFFER_TIME)
					self.touch.reset()
					self.send_buffer()
				elif ev["type"] == 'button':
					self.buttons.reset()
					self.buttons.set_button(ev['button'], True)
					self.send_buffer()
		self.thread = Thread(target=loop, args = (self.queue, ))
		self.thread.start()
	

	def get_buffer(self) -> bytearray:
		buf = bytearray(20)
		buf[0:4] = pack('I', self.buttons.get_mask())
		buf[4:8] = pack('I', self.touch.get_mask())
		buf[8:12] = pack('I', self.stick.get_mask())
		buf[12:16] = pack('I', self.cstick.get_mask())
		buf[16:20] = pack('I', self.special_buttons.get_mask())
		return buf
	
	def send_buffer(self):
		self.socket.send(self.get_buffer())
	
	def send_button_oneshot(self, button: HidButtonCodes):
		self.queue.put({
			"type": "button",
			"button": button
		})
	
	def send_touch(self, x: int, y: int):
		"""
		x and y is of the range 0-4096
		"""
		print(x, y)
		self.queue.put({
			"type": "touch",
			"x": x,
			"y": y
		})

	def clear_touch(self):
		"""
		x and y is of the range 0-4096
		"""
		self.queue.put({
			"type": "clear_touch",
		})

connection = Connection(HOST)

if __name__ == '__main__':
	import pygame
	import json
	from pathlib import Path
	input_binding = json.loads(Path('inputs.json').read_text())
	(width, height) = (300, 200)
	screen = pygame.display.set_mode((width, height))
	pygame.display.flip()
	running = True
	while running:
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				running = False
			if event.type == pygame.KEYDOWN:
				keys = pygame.key.get_pressed()
				for k, v in input_binding.items():
					if keys[pygame.key.key_code(k)]:
						connection.send_touch(
							int(v['x'] / 320 * 4096),
							int(v['y'] / 240 * 4096)
						)
						break
			if event.type == pygame.KEYUP:
				connection.clear_touch()

	pygame.quit()