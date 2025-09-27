import pytesseract
from PIL import Image
pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
with Image.open("receipt23.jpg") as ext:
    print(pytesseract.image_to_string(ext))