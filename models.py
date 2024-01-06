from fastapi import UploadFile, File, Form
from pydantic import BaseModel

# class ManualAssetForm(BaseModel):
#     dish_name: str
#     restaurant_name: str
#     video: File

class InstaAssetForm(BaseModel):
    dish_name: str
    restaurant_name: str
    post_url: str
    




class Restaurant(BaseModel):
    name: str