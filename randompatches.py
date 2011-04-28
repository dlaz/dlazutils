import Image
import glob
from random import randint, random
import sys
import os
import numpy as np

def gen_patch(im):
	scale  = random()/2 + 0.5
	width  = int(im.size[0] * scale)
	height = int(im.size[1] * scale)
	
	left   = randint(0, width -25)
	top    = randint(0, height-25)
	right  = left + 24
	bottom = top  + 24
	cropped = im.crop((left, top, right, bottom))
	cropped.load()
	return cropped
	
if __name__ == '__main__':
	outdir = sys.argv[-1]
	imdex = 0
	for f in sys.argv[1:-1]: #glob.glob(files):
		for i in range(10):
			im = Image.open(os.path.abspath(f)).convert('L')
			gen_patch(im).save(os.path.join(os.path.abspath(outdir), 'im%s.jpg' % imdex))
			imdex += 1