from app.app import *

class Network(App):
	def __init__(self):
		super().__init__(self)

	def run_ipconfig(self):
		self.run_command("Executando IPConfig", "ipconfig /all")

	def reset_winsock(self):
		self.run_command(
			"Resetando Winsock",
			"netsh winsock reset"
		)

	def ping_google(self):
		self.run_command("Ping Google", "ping google.com")

	def run_tracert(self):
		self.run_command("Traceroute Google", "tracert google.com")

	def run_nslookup(self):
		self.run_command("NSLookup Google", "nslookup google.com")

	def run_netstat(self):
		self.run_command("Netstat", "netstat -ano")

	def run_arp(self):
		self.run_command("Tabela ARP", "arp -a")

	def run_route(self):
		self.run_command("Tabela de Rotas", "route print")