import cv
from math import atan2, hypot, sin, cos, pi
	
def Arrow(img, head, tail, color, thickness=1, lineType=0):
	# draw the shaft
	cv.Line(img, head, tail, color, thickness, lineType)

	# determine head coordinates
	a = atan2(head[1]-tail[1],head[0]-tail[0])
	h = hypot(head[0]-tail[0], head[1]-tail[1])
	t1 = (int(head[0] - h/3 * cos(a + pi/6)), int(head[1] - h/3 * sin(a + pi/6)))
	t2 = (int(head[0] - h/3 * cos(a - pi/6)), int(head[1] - h/3 * sin(a - pi/6)))
	cv.Line(img, head, t1, color, thickness, lineType)
	cv.Line(img, head, t2, color, thickness, lineType)
	
def Quiver(img, heads, tails, color):
	for h, t in zip(heads, tails):
		Arrow(img, h, t, color)