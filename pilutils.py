import Image, ImageDraw
from math import atan2, hypot, sin, cos, pi

def arrow(img, head, tail, color):
	draw = ImageDraw.Draw(img)
	# draw the shaft
	draw.line([head, tail], fill=color)
	
	# determine head coordinates
	a = atan2(head[1]-tail[1],head[0]-tail[0])
	h = hypot(head[0]-tail[0], head[1]-tail[1])
	t1 = (head[0] - h/3 * cos(a + pi/6), head[1] - h/3 * sin(a + pi/6))
	t2 = (head[0] - h/3 * cos(a - pi/6), head[1] - h/3 * sin(a - pi/6))
	draw.line([head, t1], fill=color)
	draw.line([head, t2], fill=color)