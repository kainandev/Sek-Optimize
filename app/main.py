from app.fetch import FastFetch
from app.files import Files
from app.network import Network
from app.optimize import Optmize

class MainApp(
        FastFetch,
        Files,
        Network,
        Optmize
    ):
    def __init__(self):
        super().__init__()