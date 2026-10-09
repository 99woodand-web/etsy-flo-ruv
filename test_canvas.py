from tkinter import Tk, Canvas
from PIL import Image

root = Tk()
c = Canvas(root, width=620, height=460, bg="black", highlightthickness=0)
c.pack()

img = Image.open("living_room_mockup.jpg").convert("RGB")
img.thumbnail((620, 460))
img.save("tm_test.png")          # PNG *is* natively supported
c.create_image(310, 230, image=__import__("tkinter").PhotoImage(file="tm_test.png"))

root.mainloop()
