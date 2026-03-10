from config import *
from app.fetch       import FastFetch
from app.files       import Files
from app.network     import Network
from app.optimize    import Optmize
from app.monitor     import Monitor
from app.security    import Security
from app.maintenance import Maintenance


class MainApp(FastFetch, Files, Network, Optmize, Monitor, Security, Maintenance):
    """
    Classe principal que une todos os modulos via heranca multipla.

    Ordem do MRO (Method Resolution Order):
      MainApp -> FastFetch -> Files -> Network -> Optmize
              -> Monitor -> Security -> Maintenance -> App

    Para adicionar um novo modulo:
      1. Crie app/meu_modulo.py herdando de App
      2. Importe-o aqui
      3. Adicione-o na lista de heranca de MainApp
      4. Registre os metodos em ACTIONS no config.py
    """

    def __init__(self):
        super().__init__()